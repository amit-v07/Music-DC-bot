import unittest
import asyncio
import time
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from audio.manager import AudioManager, Song
from config import config

class TestCircuitBreaker(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

    def test_initial_state(self):
        self.assertEqual(self.cb.state, "CLOSED")

    async def test_failure_counting_and_opening(self):
        # Fail 1
        with self.assertRaises(Exception):
            await self.cb.call(self._failing_func)
        self.assertEqual(self.cb.failures, 1)
        self.assertEqual(self.cb.state, "CLOSED")

        # Fail 2 (Threshold reached)
        with self.assertRaises(Exception):
            await self.cb.call(self._failing_func)
        self.assertEqual(self.cb.failures, 2)
        self.assertEqual(self.cb.state, "OPEN")
        
        # Verify it raises CircuitBreakerOpen immediately
        with self.assertRaises(CircuitBreakerOpen):
            await self.cb.call(self._success_func)

    async def test_recovery(self):
        # Force open state
        self.cb.failures = 2
        self.cb.state = "OPEN"
        self.cb.last_failure_time = time.time() - 2  # Older than recovery_timeout (1s)

        # Should be HALF_OPEN on next call (handled inside call)
        # If we call success_func, it should succeed, reset failures, and close the circuit.
        
        result = await self.cb.call(self._success_func)
        self.assertEqual(result, "Success")
        self.assertEqual(self.cb.state, "CLOSED")
        self.assertEqual(self.cb.failures, 0)

    async def _failing_func(self):
        raise Exception("Simulated Failure")

    async def _success_func(self):
        return "Success"

class TestRequestDeduplication(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.audio_manager = AudioManager()

    async def test_pending_resolution_set(self):
        song = Song(title="Test Song", webpage_url="http://example.com/song")
        
        # Manually add to pending
        self.audio_manager._pending_resolutions.add(song.webpage_url)
        self.assertIn(song.webpage_url, self.audio_manager._pending_resolutions)
        
        # Create a task that removes it from pending after delay
        async def resolve_simulation():
            await asyncio.sleep(0.1)
            self.audio_manager._pending_resolutions.discard(song.webpage_url)
            
        asyncio.create_task(resolve_simulation())
        
        # Simulate the wait loop logic from manager.py
        start_time = time.time()
        while song.webpage_url in self.audio_manager._pending_resolutions:
            await asyncio.sleep(0.05)
            if time.time() - start_time > 1:
                self.fail("Timed out waiting for resolution")
                
        self.assertNotIn(song.webpage_url, self.audio_manager._pending_resolutions)


class TestQueueLogic(unittest.TestCase):
    def setUp(self):
        self.audio_manager = AudioManager()
        self.guild_id = 123
        self.audio_manager.ensure_queue(self.guild_id)

    def test_queue_flow_add_after_finish(self):
        # 1. Add Song A
        song_a = Song(title="A", webpage_url="url_a")
        self.audio_manager.add_songs(self.guild_id, [song_a])
        
        # Verify index 0
        self.assertEqual(self.audio_manager.guild_current_index[self.guild_id], 0)
        self.assertEqual(self.audio_manager.get_current_song(self.guild_id).title, "A")
        
        # 2. Simulate playback finish (next_song)
        # New logic: returns False (no next song YET), but increments index to 1
        has_next = self.audio_manager.next_song(self.guild_id)
        self.assertFalse(has_next)
        
        # Index should be 1 now (waiting for next song)
        self.assertEqual(self.audio_manager.guild_current_index[self.guild_id], 1) 
        
        # 3. Add Song B
        song_b = Song(title="B", webpage_url="url_b")
        self.audio_manager.add_songs(self.guild_id, [song_b])
        
        # 4. Attempt to get current song (what play_current_song does)
        # Should return B (index 1)
        current = self.audio_manager.get_current_song(self.guild_id)
        self.assertIsNotNone(current)
        self.assertEqual(current.title, "B")
        
    def test_fix_index_increment(self):
        # Setup similar to above
        song_a = Song(title="A", webpage_url="url_a")
        self.audio_manager.add_songs(self.guild_id, [song_a])
        
        # Simulate finish
        self.audio_manager.next_song(self.guild_id)
        
        # Add B
        song_b = Song(title="B", webpage_url="url_b")
        self.audio_manager.add_songs(self.guild_id, [song_b])
        
        # Should point to B (index 1)
        self.assertEqual(self.audio_manager.guild_current_index[self.guild_id], 1)
        self.assertEqual(self.audio_manager.get_current_song(self.guild_id).title, "B")

if __name__ == '__main__':
    unittest.main()
