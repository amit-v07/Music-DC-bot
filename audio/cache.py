"""
Song resolution cache for Music Bot
Implements LRU cache with TTL to reduce YouTube API calls
"""
import asyncio
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from collections import OrderedDict


@dataclass
class CacheEntry:
    """Cache entry with TTL support"""
    data: dict  # Resolved song info
    timestamp: float
    hit_count: int = 0


class SongCache:
    """Thread-safe LRU cache with TTL for song resolutions"""
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 21600):  # 6 hours default
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0
    
    def _make_key(self, query: str) -> str:
        """Create cache key from query"""
        # Normalize the query for consistent caching
        return query.lower().strip()
    
    async def get(self, query: str) -> Optional[dict]:
        """Get cached song info if available and not expired"""
        async with self.lock:
            key = self._make_key(query)
            
            if key not in self.cache:
                self.misses += 1
                return None
            
            entry = self.cache[key]
            
            # Check if expired
            if time.time() - entry.timestamp > self.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            entry.hit_count += 1
            self.hits += 1
            
            return entry.data
    
    async def set(self, query: str, data: dict):
        """Cache song resolution data"""
        async with self.lock:
            key = self._make_key(query)
            
            # Remove oldest if at capacity
            if key not in self.cache and len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)  # Remove oldest (FIFO)
            
            # Add or update entry
            self.cache[key] = CacheEntry(
                data=data,
                timestamp=time.time()
            )
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
    
    async def clear(self):
        """Clear all cached entries"""
        async with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    async def cleanup_expired(self):
        """Remove expired entries"""
        async with self.lock:
            current_time = time.time()
            keys_to_remove = []
            
            for key, entry in self.cache.items():
                if current_time - entry.timestamp > self.ttl_seconds:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
    
    def get_stats(self) -> Dict[str, any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'total_requests': total_requests
        }


# Global cache instance
song_cache = SongCache(max_size=500, ttl_seconds=21600)  # 6 hours TTL
