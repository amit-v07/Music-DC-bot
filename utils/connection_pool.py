"""
Connection pool for yt-dlp to prevent resource exhaustion
Limits concurrent resolutions and provides better rate limit handling
"""
import asyncio
from typing import Optional
import yt_dlp
from utils.logger import logger


class YTDLPPool:
    """Connection pool for yt-dlp operations"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.total_requests = 0
        self.failed_requests = 0
    
    async def execute(self, ydl_opts: dict, url: str, download: bool = False):
        """
        Execute yt-dlp extraction with connection pooling
        
        Args:
            ydl_opts: yt-dlp options dictionary
            url: URL or search query
            download: Whether to download (default: False for extract_info only)
            
        Returns:
            Extracted info dict or None on failure
        """
        async with self.semaphore:
            self.active_count += 1
            self.total_requests += 1
            
            try:
                def _extract():
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(url, download=download)
                    except yt_dlp.DownloadError as e:
                        logger.warning(f"yt-dlp DownloadError: {str(e)}")
                        raise
                    except Exception as e:
                        logger.error("ytdlp_pool_extract", e, url=url)
                        raise
                
                # Run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, _extract)
                return result
                
            except yt_dlp.DownloadError:
                self.failed_requests += 1
                raise
            except Exception as e:
                self.failed_requests += 1
                logger.error("ytdlp_pool_execute", e, url=url)
                raise
            finally:
                self.active_count -= 1
    
    def get_stats(self) -> dict:
        """Get pool statistics"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = ((self.total_requests - self.failed_requests) / self.total_requests) * 100
        
        return {
            'active': self.active_count,
            'max_concurrent': self.max_concurrent,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{success_rate:.1f}%"
        }


# Global pool instance
ytdlp_pool = YTDLPPool(max_concurrent=5)
