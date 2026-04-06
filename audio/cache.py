"""
Song resolution cache for Music Bot
Uses cachetools TTLCache (maxsize=200, TTL=4h) backed by a threading.Lock
for thread safety when called from multiple ThreadPoolExecutor workers.
"""
import threading
import re
from typing import Optional, Callable, Any
from cachetools import TTLCache
from utils.logger import logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YT_VIDEO_ID_RE = re.compile(
    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{11})'
)


def _extract_video_id(url_or_key: str) -> str:
    """Extract YouTube video ID if present, otherwise normalise key."""
    if url_or_key and url_or_key.startswith('http'):
        m = _YT_VIDEO_ID_RE.search(url_or_key)
        if m:
            return m.group(1)
    return url_or_key.lower().strip()


# ---------------------------------------------------------------------------
# Cache class
# ---------------------------------------------------------------------------

class SongCache:
    """
    Thread-safe LRU+TTL cache for yt-dlp stream URL resolutions.

    * maxsize=200  — enough for a typical music session across multiple servers
    * ttl=14400    — 4 hours (YouTube signed URLs expire ~6 h)
    * threading.Lock instead of asyncio.Lock so it can be used safely from
      both async code and ThreadPoolExecutor workers.
    """

    def __init__(self, maxsize: int = 200, ttl: int = 14400):
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------
    # Public async API (unchanged signatures — manager.py calls these)
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[dict]:
        """Return cached song data, or None on miss/expiry."""
        cache_key = _extract_video_id(key)
        with self._lock:
            data = self._cache.get(cache_key)
            if data is not None:
                self.hits += 1
                return data
            self.misses += 1
            return None

    async def set(self, key: str, data: dict) -> None:
        """Cache resolved song data."""
        cache_key = _extract_video_id(key)
        with self._lock:
            try:
                self._cache[cache_key] = data
            except ValueError:
                # TTLCache raises ValueError if trying to set an already-expired key
                pass

    async def clear(self) -> None:
        """Evict all entries."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    async def cleanup_expired(self) -> None:
        """
        cachetools.TTLCache evicts lazily on access.
        Calling this manually forces a sweep — useful for the periodic cleanup task.
        """
        with self._lock:
            # expire() is the internal method that prunes stale entries
            self._cache.expire()

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        with self._lock:
            size = len(self._cache)
        return {
            'size': size,
            'max_size': self._cache.maxsize,
            'ttl_seconds': self._cache.ttl,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'total_requests': total,
        }

    # ------------------------------------------------------------------
    # Synchronous helper for executor workers
    # ------------------------------------------------------------------

    def get_or_fetch(self, video_id: str, fetch_fn: Callable[[], Any]) -> Any:
        """
        Synchronous get-or-populate helper, safe to call from a
        ThreadPoolExecutor worker.

        1. Check cache under lock.
        2. If miss, call fetch_fn() (blocking) outside the lock.
        3. Store result back in cache under lock.
        4. Return result.
        """
        cache_key = _extract_video_id(video_id)

        # Fast path — cache hit
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self.hits += 1
                return cached

        # Slow path — fetch (done outside lock to avoid blocking other threads)
        self.misses += 1
        try:
            result = fetch_fn()
        except Exception:
            raise

        if result is not None:
            with self._lock:
                try:
                    self._cache[cache_key] = result
                except ValueError:
                    pass

        return result


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

# 200 entries × ~2 KB avg = ~400 KB RAM — well within budget
# TTL=14400 s (4 h) gives a comfortable margin before YouTube URLs expire (≈6 h)
song_cache = SongCache(maxsize=200, ttl=14400)
