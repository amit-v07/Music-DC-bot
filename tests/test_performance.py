
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
        """Test LRU+TTL cache eviction with cachetools"""
        # New API: maxsize= and ttl= (not max_size/ttl_seconds)
        cache = SongCache(maxsize=3, ttl=3600)
        
        # Add 3 items (fills cache)
        await cache.set("1", {"title": "1", "webpage_url": "u1", "duration": 1})
        await cache.set("2", {"title": "2", "webpage_url": "u2", "duration": 2})
        await cache.set("3", {"title": "3", "webpage_url": "u3", "duration": 3})
        
        self.assertEqual(len(cache._cache), 3)
        
        # Access "1" to make it recently used
        await cache.get("1")
        
        # Add 4th item — maxsize=3 so one entry (LRU) will be evicted
        await cache.set("4", {"title": "4", "webpage_url": "u4", "duration": 4})
        
        # Size must remain capped at 3
        self.assertEqual(len(cache._cache), 3)
        # "1" was just accessed so it should survive
        self.assertIsNotNone(await cache.get("1"))
        # "4" was just added so it should be present
        self.assertIsNotNone(await cache.get("4"))
        
    def test_cache_eviction_wrapper(self):
        """Wrapper to run async test"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.test_cache_eviction())
        loop.close()

if __name__ == '__main__':
    unittest.main()
