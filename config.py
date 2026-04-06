"""
Configuration management for Music Bot
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Main bot configuration"""
    # Discord settings
    discord_token: str
    owner_id: Optional[int] = None
    default_prefix: str = '!'
    
    # Audio settings
    default_volume: float = 0.5
    max_volume: float = 2.0
    min_volume: float = 0.1
    idle_timeout: int = 300  # 5 minutes
    alone_timeout: int = 60   # 1 minute
    
    # Spotify settings
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    google_api_key: Optional[str] = None
    
    # File paths
    error_log_file: str = 'bot_errors.log'
    
    # Audio quality settings
    ffmpeg_options: dict = None
    ydl_options: dict = None
    
    # UI settings
    queue_per_page: int = 10
    search_results_limit: int = 10
    
    # Rate limiting
    command_cooldown: float = 1.0
    api_request_delay: float = 0.1
    
    # Autoplay settings
    autoplay_songs_per_batch: int = 5  # How many songs to add when queue ends
    autoplay_max_history: int = 20  # Max recent songs to track per server
    autoplay_enabled_by_default: bool = False
    
    # Resource Management
    max_memory_mb: int = 500  # Max memory before forced GC
    resource_cleanup_interval: int = 300  # Seconds between resource checks
    max_concurrent_streams: int = 4  # Max simultaneous FFmpeg voice streams
    default_audio_quality: str = 'medium'  # Per-guild quality default

    # Audio quality presets (Change 10)
    AUDIO_QUALITY_PRESETS: dict = None
    
    def __post_init__(self):
        """Initialize default options after dataclass creation"""
        if self.AUDIO_QUALITY_PRESETS is None:
            self.AUDIO_QUALITY_PRESETS = {
                'low':    {'bitrate': '64k',  'format': 'bestaudio[abr<=64]/bestaudio'},
                'medium': {'bitrate': '128k', 'format': 'bestaudio[abr<=128]/bestaudio'},
                'high':   {'bitrate': '192k', 'format': 'bestaudio[abr<=192]/bestaudio'},
            }
        
        if self.ffmpeg_options is None:
            self.ffmpeg_options = {
                # -thread_queue_size prevents input buffer overrun warnings;
                # +nobuffer reduces latency in the stream pipeline.
                'before_options': (
                    '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
                    '-reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx '
                    '-rw_timeout 15000000 '
                    '-thread_queue_size 512 -fflags +nobuffer'
                ),
                # -threads 1: one decode thread per stream keeps CPU usage predictable
                # on a dual-core host.  -b:a injected per-guild by create_audio_source.
                'options': '-vn -threads 1',
            }
        
        if self.ydl_options is None:
            self.ydl_options = {
                # Prefer streams that are already Opus-encoded so FFmpeg just
                # copies the audio without re-encoding (huge CPU saving).
                'format': (
                    'bestaudio[ext=webm][acodec=opus]'
                    '/bestaudio[ext=ogg]'
                    '/bestaudio'
                ),
                'quiet': True,
                'extract_flat': False,
                'noplaylist': True,
                'default_search': 'ytsearch',
                'source_address': '0.0.0.0',
                'ignoreerrors': True,
                'playlistend': 50,
                'skip_unavailable_fragments': True,
                'retries': 3,
                'fragment_retries': 3,
                'no_warnings': True,
                'socket_timeout': 15,           # Drop stalled connections quickly
                'http_chunk_size': 10485760,    # 10 MB chunks for smoother streaming
                
                # YouTube bot detection bypass
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',
                'nocheckcertificate': True,
                'prefer_insecure': False,
                'geo_bypass': True,
                'age_limit': None,
                
                # Additional anti-bot measures
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'configs'],
                    }
                },
            }


def load_config() -> BotConfig:
    """Load configuration from environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    
    return BotConfig(
        discord_token=discord_token,
        owner_id=int(os.getenv('OWNER_ID')) if os.getenv('OWNER_ID') else None,
        # Support both SPOTIFY_* and SPOTIPY_* env var names for compatibility
        spotify_client_id=(os.getenv('SPOTIFY_CLIENT_ID') or os.getenv('SPOTIPY_CLIENT_ID')),
        spotify_client_secret=(os.getenv('SPOTIFY_CLIENT_SECRET') or os.getenv('SPOTIPY_CLIENT_SECRET')),
        default_prefix=os.getenv('DEFAULT_PREFIX', '!'),
        default_volume=float(os.getenv('DEFAULT_VOLUME', '0.5')),
        idle_timeout=int(os.getenv('IDLE_TIMEOUT', '300')),
        alone_timeout=int(os.getenv('ALONE_TIMEOUT', '60')),
        google_api_key=os.getenv('GOOGLE_API_KEY'),
    )


# Global config instance
config = load_config() 