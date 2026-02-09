"""
YouTube Music Recommendation Service for Music Bot
Uses ytmusicapi for high-quality song recommendations (like YouTube Music's autoplay)
Falls back to yt-dlp search if ytmusicapi fails
"""
import asyncio
import yt_dlp
import re
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
from utils.logger import logger

# Try to import ytmusicapi
try:
    from ytmusicapi import YTMusic
    YTMUSIC_AVAILABLE = True
except ImportError:
    YTMUSIC_AVAILABLE = False
    logger.warning("ytmusicapi not installed, using yt-dlp search fallback")


@dataclass
class RecommendedSong:
    """Recommended song data structure"""
    title: str
    video_url: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    relevance_score: float = 0.0


class YouTubeMusicRecommendationEngine:
    """Fetches music recommendations using YouTube Music API"""
    
    def __init__(self):
        self.ytmusic = None
        self.cache: Dict[str, List[RecommendedSong]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.cache_duration = timedelta(hours=1)
        
        # Initialize ytmusicapi if available
        if YTMUSIC_AVAILABLE:
            try:
                self.ytmusic = YTMusic()
                logger.info("YouTube Music API initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize YouTube Music API: {e}")
                self.ytmusic = None
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'([a-zA-Z0-9_-]{11})'  # Just the ID
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def get_related_songs(self, video_url: str, count: int = 5) -> List[RecommendedSong]:
        """
        Get related songs using YouTube Music API with yt-dlp fallback
        
        Args:
            video_url: YouTube video URL to get recommendations from
            count: Number of recommendations to return
            
        Returns:
            List of RecommendedSong objects
        """
        try:
            # Check cache first
            if self._is_cached(video_url):
                logger.info(f"Using cached recommendations for {video_url}")
                return self.cache[video_url][:count]
            
            recommendations = []
            
            # Try YouTube Music API first
            if self.ytmusic:
                recommendations = await self._fetch_ytmusic_recommendations(video_url)
            
            # Fallback to yt-dlp search if ytmusicapi fails or returns nothing
            if not recommendations:
                logger.info("Falling back to yt-dlp search")
                recommendations = await self._fetch_ytdlp_recommendations(video_url)
            
            # Cache results
            if recommendations:
                self._cache_results(video_url, recommendations)
            
            return recommendations[:count]
            
        except Exception as e:
            logger.error("get_related_songs", e, video_url=video_url)
            return []
    
    async def _fetch_ytmusic_recommendations(self, video_url: str) -> List[RecommendedSong]:
        """Fetch recommendations using YouTube Music API"""
        def _fetch():
            try:
                video_id = self._extract_video_id(video_url)
                if not video_id:
                    logger.warning(f"Could not extract video ID from: {video_url}")
                    return []
                
                logger.info(f"Fetching YouTube Music recommendations for: {video_id}")
                
                # Get watch playlist (song radio)
                watch_playlist = self.ytmusic.get_watch_playlist(videoId=video_id)
                
                if not watch_playlist or 'tracks' not in watch_playlist:
                    logger.warning("YouTube Music returned no tracks")
                    return []
                
                tracks = watch_playlist['tracks']
                logger.info(f"YouTube Music returned {len(tracks)} tracks")
                
                recommendations = []
                for i, track in enumerate(tracks):
                    # Skip the first track (it's usually the current song)
                    if i == 0 and track.get('videoId') == video_id:
                        continue
                    
                    video_id_track = track.get('videoId')
                    if not video_id_track:
                        continue
                    
                    title = track.get('title', 'Unknown')
                    artists = track.get('artists', [])
                    if artists:
                        artist_names = ' & '.join([a.get('name', '') for a in artists if a.get('name')])
                        if artist_names:
                            title = f"{title} - {artist_names}"
                    
                    duration = None
                    if track.get('length'):
                        # Parse duration string like "3:45"
                        try:
                            parts = track['length'].split(':')
                            if len(parts) == 2:
                                duration = int(parts[0]) * 60 + int(parts[1])
                            elif len(parts) == 3:
                                duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        except:
                            pass
                    
                    thumbnail = None
                    if track.get('thumbnail'):
                        thumbnails = track['thumbnail']
                        if isinstance(thumbnails, list) and thumbnails:
                            thumbnail = thumbnails[-1].get('url')  # Get highest quality
                    
                    recommendations.append(RecommendedSong(
                        title=title,
                        video_url=f"https://www.youtube.com/watch?v={video_id_track}",
                        duration=duration,
                        thumbnail=thumbnail,
                        relevance_score=1.0 - (i * 0.05)  # Higher score for earlier tracks
                    ))
                
                logger.info(f"Processed {len(recommendations)} YouTube Music recommendations")
                return recommendations
                
            except Exception as e:
                logger.warning(f"YouTube Music API failed: {e}")
                return []
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)
    
    async def _fetch_ytdlp_recommendations(self, video_url: str) -> List[RecommendedSong]:
        """Fallback: Fetch recommendations using yt-dlp search"""
        def _extract():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Get video info to extract title
                    logger.info(f"yt-dlp: Extracting info from {video_url}")
                    info = ydl.extract_info(video_url, download=False)
                    
                    if not info or 'title' not in info:
                        logger.warning("Could not get video title")
                        return []
                    
                    title = info['title']
                    video_id = info.get('id', '')
                    logger.info(f"yt-dlp: Got title: {title}")
                    
                    # Clean title for search
                    clean_title = title
                    for suffix in ['(Official Video)', '[Official Video]', '(Official Music Video)', 
                                   '(Lyric Video)', '(Audio)', '[Audio]', '(4K Remaster)',
                                   '(Lyrics)', '[Lyrics]', '| Official Video', '(Official Audio)']:
                        clean_title = clean_title.replace(suffix, '')
                    clean_title = clean_title.strip()
                    
                    # Search for similar songs
                    search_query = f"{clean_title} song"
                    logger.info(f"yt-dlp: Searching for: {search_query}")
                    
                    search_results = ydl.extract_info(f"ytsearch15:{search_query}", download=False)
                    
                    if not search_results or 'entries' not in search_results:
                        logger.warning("yt-dlp search returned no results")
                        return []
                    
                    entries = search_results['entries']
                    logger.info(f"yt-dlp: Found {len(entries)} search results")
                    
                    recommendations = []
                    for entry in entries:
                        if not entry:
                            continue
                        
                        entry_id = entry.get('id', '')
                        if entry_id == video_id:
                            continue  # Skip original video
                        
                        duration = entry.get('duration')
                        if duration and duration > 900:  # Skip videos > 15 min
                            continue
                        
                        url = entry.get('url') or f"https://www.youtube.com/watch?v={entry_id}"
                        if not url.startswith('http'):
                            url = f"https://www.youtube.com/watch?v={url}"
                        
                        recommendations.append(RecommendedSong(
                            title=entry.get('title', 'Unknown'),
                            video_url=url,
                            duration=duration,
                            thumbnail=entry.get('thumbnail'),
                            relevance_score=0.5
                        ))
                    
                    logger.info(f"yt-dlp: Processed {len(recommendations)} recommendations")
                    return recommendations
                    
                except Exception as e:
                    logger.error("_fetch_ytdlp_recommendations", e)
                    return []
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract)
    
    def _is_cached(self, video_url: str) -> bool:
        """Check if recommendations are cached and valid"""
        if video_url not in self.cache:
            return False
        timestamp = self.cache_timestamps.get(video_url)
        if not timestamp:
            return False
        return datetime.now() - timestamp < self.cache_duration
    
    def _cache_results(self, video_url: str, recommendations: List[RecommendedSong]):
        """Cache recommendation results"""
        self.cache[video_url] = recommendations
        self.cache_timestamps[video_url] = datetime.now()
        
        # Limit cache size
        if len(self.cache) > 50:
            oldest_url = min(self.cache_timestamps.items(), key=lambda x: x[1])[0]
            del self.cache[oldest_url]
            del self.cache_timestamps[oldest_url]


class RecommendationManager:
    """Main recommendation manager"""
    
    def __init__(self):
        self.engine = YouTubeMusicRecommendationEngine()
    
    async def get_next_recommendations(
        self, 
        last_video_url: str, 
        count: int = 5
    ) -> List[RecommendedSong]:
        """Get next song recommendations"""
        try:
            if not last_video_url:
                logger.warning("No video URL provided for recommendations")
                return []
            
            recommendations = await self.engine.get_related_songs(last_video_url, count=count)
            logger.info(f"Generated {len(recommendations)} recommendations from {last_video_url}")
            return recommendations
            
        except Exception as e:
            logger.error("get_next_recommendations", e, last_url=last_video_url)
            return []


# Global instance
recommendation_manager = RecommendationManager()
