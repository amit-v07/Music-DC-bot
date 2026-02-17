
import unittest
import time
import asyncio
from utils.limiter import RateLimiter
from audio.cache import SongCache
from audio.manager import Song

class TestPerformance(unittest.TestCase):
    def test_rate_limiter(self):
        """Test rate limiter logic"""
        limiter = RateLimiter(rate=2, per=1)
        user_id = 12345
        
        # Should allow 2 requests
        self.assertTrue(limiter.check(user_id))
        self.assertTrue(limiter.check(user_id))
        
        # Should block 3rd request
        self.assertFalse(limiter.check(user_id))
        
        # Wait for window to pass
        time.sleep(1.1)
        
        # Should allow again
        self.assertTrue(limiter.check(user_id))

    async def test_cache_eviction(self):
        """Test LRU cache eviction"""
        cache = SongCache(max_size=3, ttl_seconds=3600)
        
        # Add 3 items
        await cache.set("1", {"title": "1", "webpage_url": "u1", "duration": 1})
        await cache.set("2", {"title": "2", "webpage_url": "u2", "duration": 2})
        await cache.set("3", {"title": "3", "webpage_url": "u3", "duration": 3})
        
        self.assertEqual(len(cache.cache), 3)
        
        # Access "1" to make it specifically used recently
        await cache.get("1")
        
        # Add 4th item, should evict LRU (which is "2" now because "1" was just used)
        await cache.set("4", {"title": "4", "webpage_url": "u4", "duration": 4})
        
        self.assertEqual(len(cache.cache), 3)
        self.assertIsNone(await cache.get("2")) # 2 should be gone
        self.assertIsNotNone(await cache.get("1")) # 1 should be present
        self.assertIsNotNone(await cache.get("4")) # 4 should be present
        
    def test_cache_eviction_wrapper(self):
        """Wrapper to run async test"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.test_cache_eviction())
        loop.close()

if __name__ == '__main__':
    unittest.main()
