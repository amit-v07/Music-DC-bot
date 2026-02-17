"""
Audio management for Music Bot
Handles audio sources, playback, and queue management
"""
import asyncio
import discord
import yt_dlp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from config import config
from utils.logger import logger, log_audio_event
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials


@dataclass
class Song:
    """Enhanced song data structure"""
    title: str
    url: Optional[str] = None
    webpage_url: Optional[str] = None
    original_url: Optional[str] = None  # Preserve original YouTube URL for recommendations
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    requester_id: int = 0
    requester_name: str = "Unknown"
    is_lazy: bool = False
    added_at: datetime = field(default_factory=datetime.now)
    
    def format_duration(self) -> str:
        """Format duration as MM:SS or HH:MM:SS"""
        if not self.duration:
            return "?"
        try:
            seconds = int(self.duration)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except (ValueError, TypeError):
            return "?"


class AudioManager:
    """Manages audio operations for the bot"""
    
    def __init__(self):
        self.guild_queues: Dict[int, List[Song]] = {}
        self.guild_current_index: Dict[int, int] = {}
        self.guild_volumes: Dict[int, float] = {}
        self.repeat_flags: Dict[int, bool] = {}
        self.alone_timers: Dict[int, asyncio.Task] = {}
        self.idle_timers: Dict[int, asyncio.Task] = {}
        
        # Autoplay state
        self.autoplay_enabled: Dict[int, bool] = {}
        
        # Initialize Spotify client if credentials are available
        self.spotify_client = None
        if config.spotify_client_id and config.spotify_client_secret:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=config.spotify_client_id,
                    client_secret=config.spotify_client_secret
                )
                self.spotify_client = Spotify(auth_manager=auth_manager)
                logger.info("Spotify integration initialized successfully")
            except Exception as e:
                logger.error("spotify_init", e)
    
    def ensure_queue(self, guild_id: int):
        """Ensure guild has a queue initialized"""
        if guild_id not in self.guild_queues:
            self.guild_queues[guild_id] = []
        if guild_id not in self.guild_current_index:
            self.guild_current_index[guild_id] = 0
        if guild_id not in self.guild_volumes:
            self.guild_volumes[guild_id] = config.default_volume
    
    def get_queue(self, guild_id: int) -> List[Song]:
        """Get queue for a guild"""
        self.ensure_queue(guild_id)
        return self.guild_queues[guild_id]
    
    def get_current_song(self, guild_id: int) -> Optional[Song]:
        """Get currently playing song"""
        queue = self.get_queue(guild_id)
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if queue and 0 <= current_idx < len(queue):
            return queue[current_idx]
        return None
    
    def add_songs(self, guild_id: int, songs: List[Song]) -> int:
        """Add songs to queue and return starting position"""
        self.ensure_queue(guild_id)
        queue_length_before = len(self.guild_queues[guild_id])
        
        self.guild_queues[guild_id].extend(songs)
        
        # Handle current_index logic
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if queue_length_before == 0:
            # Queue was empty, start from beginning
            self.guild_current_index[guild_id] = 0
        
        return queue_length_before
    
    def remove_song(self, guild_id: int, index: int) -> Optional[Song]:
        """Remove song at index from queue"""
        queue = self.get_queue(guild_id)
        
        if 0 <= index < len(queue):
            removed_song = queue.pop(index)
            
            # Adjust current index if necessary
            current_idx = self.guild_current_index.get(guild_id, 0)
            if index <= current_idx and current_idx > 0:
                self.guild_current_index[guild_id] = current_idx - 1
            
            return removed_song
        return None
    
    def move_song(self, guild_id: int, from_idx: int, to_idx: int) -> bool:
        """Move song from one position to another"""
        queue = self.get_queue(guild_id)
        
        if not (0 <= from_idx < len(queue) and 0 <= to_idx < len(queue)):
            return False
        
        song = queue.pop(from_idx)
        queue.insert(to_idx, song)
        
        # Adjust current index if necessary
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if from_idx == current_idx:
            self.guild_current_index[guild_id] = to_idx
        elif from_idx < current_idx <= to_idx:
            self.guild_current_index[guild_id] = current_idx - 1
        elif to_idx <= current_idx < from_idx:
            self.guild_current_index[guild_id] = current_idx + 1
        
        return True
    
    def shuffle_queue(self, guild_id: int):
        """Shuffle the queue (except currently playing song)"""
        queue = self.get_queue(guild_id)
        
        if len(queue) <= 1:
            return
        
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if current_idx < len(queue):
            # Remove currently playing song
            current_song = queue.pop(current_idx)
            
            # Shuffle remaining songs
            import random
            random.shuffle(queue)
            
            # Put current song back at the beginning
            queue.insert(0, current_song)
            self.guild_current_index[guild_id] = 0
    
    def clear_queue(self, guild_id: int):
        """Clear the entire queue"""
        self.guild_queues[guild_id] = []
        self.guild_current_index[guild_id] = 0
    
    def set_volume(self, guild_id: int, volume: float):
        """Set volume for a guild"""
        self.guild_volumes[guild_id] = max(config.min_volume, min(config.max_volume, volume))
    
    def get_volume(self, guild_id: int) -> float:
        """Get volume for a guild"""
        return self.guild_volumes.get(guild_id, config.default_volume)
    
    def set_repeat(self, guild_id: int, repeat: bool):
        """Set repeat flag for a guild"""
        self.repeat_flags[guild_id] = repeat
    
    def is_repeat(self, guild_id: int) -> bool:
        """Check if repeat is enabled for a guild"""
        return self.repeat_flags.get(guild_id, False)
    
    def jump_to_song(self, guild_id: int, index: int) -> bool:
        """Jump to a specific song in the queue"""
        queue = self.get_queue(guild_id)
        
        if 0 <= index < len(queue):
            self.guild_current_index[guild_id] = index
            return True
        return False
    
    def next_song(self, guild_id: int) -> bool:
        """Move to next song, return True if successful"""
        queue = self.get_queue(guild_id)
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if current_idx < len(queue) - 1:
            self.guild_current_index[guild_id] = current_idx + 1
            return True
        return False
    
    def previous_song(self, guild_id: int) -> bool:
        """Move to previous song, return True if successful"""
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        if current_idx > 0:
            self.guild_current_index[guild_id] = current_idx - 1
            return True
        return False
    
    async def resolve_lazy_song(self, song: Song) -> Song:
        """Resolve a lazy-loaded song to get actual audio URL with improved error handling"""
        if not song.is_lazy:
            return song
        
        # Import cache
        try:
            from audio.cache import song_cache
        except ImportError:
            song_cache = None
        
        # Try cache first
        cache_key = song.webpage_url if song.webpage_url else song.title
        if song_cache:
            try:
                cached_data = await song_cache.get(cache_key)
                if cached_data:
                    # Restore song from cache
                    song.url = cached_data.get('url')
                    song.title = cached_data.get('title', song.title)
                    song.original_url = cached_data.get('original_url')
                    song.webpage_url = cached_data.get('webpage_url', song.webpage_url)
                    song.duration = cached_data.get('duration', song.duration)
                    song.thumbnail = cached_data.get('thumbnail', song.thumbnail)
                    song.is_lazy = False
                    log_audio_event(0, "song_resolved_from_cache", song.title)
                    return song
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}, continuing with API call")
        
        # Try multiple search strategies
        search_attempts = []
        
        # If we have a direct URL, try that first
        if song.webpage_url and self._is_http_url(song.webpage_url):
            search_attempts.append(song.webpage_url)
        
        # Add various search query formats for better success rate
        title_clean = song.title.replace(" - ", " ").replace("(", "").replace(")", "")
        search_attempts.extend([
            f"{title_clean} audio",
            f"{title_clean} official",
            f"{title_clean}",
            song.title  # Original title as fallback
        ])
        
        last_error = None
        
        for attempt, search_query in enumerate(search_attempts):
            try:
                ydl_opts = config.ydl_options.copy()
                ydl_opts['quiet'] = True  # Reduce noise in logs
                
                # Configure search method
                if self._is_http_url(search_query):
                    ydl_opts['noplaylist'] = True
                else:
                    ydl_opts['default_search'] = 'ytsearch1'
                    ydl_opts['noplaylist'] = True
                
                # Use connection pool to limit concurrent resolutions
                try:
                    from utils.connection_pool import ytdlp_pool
                    info = await ytdlp_pool.execute(ydl_opts, search_query, download=False)
                except ImportError:
                    # Fallback to direct execution if pool not available
                    def _extract_info():
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(search_query, download=False)
                    
                    loop = asyncio.get_event_loop()
                    info = await loop.run_in_executor(None, _extract_info)
                
                # Process info
                if info:
                    if 'entries' in info and info['entries']:
                        # Get the first valid entry
                        for entry in info['entries']:
                            if entry and entry.get('url'):
                                info = entry
                                break
                        else:
                            info = None
                
                if info and info.get('url'):
                    # Successfully resolved! Update song with resolved information
                    song.url = info['url']
                    song.title = info.get('title', song.title)
                    
                    # Preserve original YouTube URL before overwriting webpage_url
                    if info.get('webpage_url') and 'youtube.com' in info.get('webpage_url', ''):
                        song.original_url = info['webpage_url']
                    
                    song.webpage_url = info.get('webpage_url', song.webpage_url)
                    song.duration = info.get('duration', song.duration)
                    song.thumbnail = info.get('thumbnail', song.thumbnail)
                    
                    if not song.webpage_url or not song.webpage_url.startswith('http'):
                        song.webpage_url = info.get('webpage_url', song.webpage_url)
                    
                    song.is_lazy = False
                    
                    # Cache the successful resolution
                    if song_cache:
                        try:
                            cache_data = {
                                'url': song.url,
                                'title': song.title,
                                'original_url': song.original_url,
                                'webpage_url': song.webpage_url,
                                'duration': song.duration,
                                'thumbnail': song.thumbnail
                            }
                            await song_cache.set(cache_key, cache_data)
                        except Exception as e:
                            logger.warning(f"Failed to cache song: {e}")
                    
                    log_audio_event(0, "song_resolved", f"{song.title} (attempt {attempt + 1})")
                    return song
                else:
                    logger.warning(f"No valid URL found for: {search_query}")
                    
            except yt_dlp.DownloadError as e:
                last_error = e
                logger.warning(f"yt-dlp download error on attempt {attempt + 1} for '{search_query}': {str(e)}")
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"Resolution attempt {attempt + 1} failed for '{search_query}': {str(e)}")
                continue
        
        # All attempts failed
        error_msg = f"Failed to resolve song after {len(search_attempts)} attempts: {song.title}"
        if last_error:
            error_msg += f" (Last error: {str(last_error)})"
        
        logger.error("resolve_lazy_song_all_attempts_failed", Exception(error_msg), song_title=song.title)
        raise ValueError(error_msg)
    
    async def get_spotify_tracks(self, url: str) -> List[Song]:
        """Extract tracks from Spotify URL"""
        if not self.spotify_client:
            logger.warning("Spotify client not initialized, cannot fetch tracks")
            return []
        
        tracks = []
        
        try:
            if 'track' in url:
                track = self.spotify_client.track(url)
                if not track or not track.get('name'):
                    logger.warning(f"Invalid track data from Spotify: {url}")
                    return []
                    
                search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                tracks.append(Song(
                    title=f"{track['name']} - {track['artists'][0]['name']}",
                    webpage_url=search_query,
                    duration=track.get('duration_ms', 0) // 1000,
                    is_lazy=True
                ))
                
            elif 'playlist' in url:
                # Handle paginated playlist results
                results = self.spotify_client.playlist_tracks(url, limit=50)
                
                while results:
                    for item in results['items']:
                        track = item.get('track')
                        if track and track.get('name'):  # Ensure track exists and has a name
                            search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                            tracks.append(Song(
                                title=f"{track['name']} - {track['artists'][0]['name']}",
                                webpage_url=search_query,
                                duration=track.get('duration_ms', 0) // 1000,
                                is_lazy=True
                            ))
                    
                    # Get next page if available (limit to 100 songs to prevent overwhelming)
                    if results['next'] and len(tracks) < 100:
                        results = self.spotify_client.next(results)
                    else:
                        break
                        
            elif 'album' in url:
                # Handle paginated album results
                results = self.spotify_client.album_tracks(url, limit=50)
                
                while results:
                    for track in results['items']:
                        if track and track.get('name'):  # Ensure track exists and has a name
                            search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                            tracks.append(Song(
                                title=f"{track['name']} - {track['artists'][0]['name']}",
                                webpage_url=search_query,
                                duration=track.get('duration_ms', 0) // 1000,
                                is_lazy=True
                            ))
                    
                    # Get next page if available (limit to 100 songs to prevent overwhelming)
                    if results['next'] and len(tracks) < 100:
                        results = self.spotify_client.next(results)
                    else:
                        break
            else:
                logger.warning(f"Unsupported Spotify URL format: {url}")
                    
        except Exception as e:
            # Import specific Spotify exceptions if available
            try:
                from spotipy.exceptions import SpotifyException
                if isinstance(e, SpotifyException):
                    logger.error("spotify_api_error", e, url=url, status_code=getattr(e, 'http_status', 'N/A'))
                else:
                    logger.error("get_spotify_tracks", e, url=url)
            except ImportError:
                logger.error("get_spotify_tracks", e, url=url)
        
        return tracks
    
    def _is_http_url(self, url: str) -> bool:
        """Check if string is an HTTP URL"""
        return url.startswith(('http://', 'https://'))
    
    def _is_spotify_url(self, url: str) -> bool:
        """Check if string is a Spotify URL"""
        return 'open.spotify.com' in url
    
    async def create_audio_source(self, song: Song, guild_id: int) -> discord.AudioSource:
        """Create discord audio source from song"""
        if song.is_lazy:
            song = await self.resolve_lazy_song(song)
        
        if not song.url:
            raise ValueError(f"No playable URL found for {song.title}")
        
        # Create FFmpeg source with optimized options
        source = discord.FFmpegPCMAudio(song.url, **config.ffmpeg_options)
        
        # Apply volume
        volume = self.get_volume(guild_id)
        source = discord.PCMVolumeTransformer(source, volume=volume)
        
        return source
    
    # Auto-disconnect and timer management
    def is_bot_alone_in_vc(self, guild) -> bool:
        """Check if bot is alone in voice channel"""
        if not guild.voice_client or not guild.voice_client.channel:
            return False
        
        human_members = [
            member for member in guild.voice_client.channel.members 
            if not member.bot
        ]
        return len(human_members) == 0
    
    async def start_alone_timer(self, guild):
        """Start timer to leave if bot stays alone"""
        guild_id = guild.id
        
        # Cancel existing timer
        if guild_id in self.alone_timers:
            self.alone_timers[guild_id].cancel()
        
        async def alone_timer():
            try:
                await asyncio.sleep(config.alone_timeout)
                
                if self.is_bot_alone_in_vc(guild) and guild.voice_client:
                    # Find text channel to send message
                    text_channel = guild.system_channel
                    if not text_channel:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                text_channel = channel
                                break
                    
                    # Disconnect and clean up
                    await guild.voice_client.disconnect()
                    self.clear_queue(guild_id)
                    
                    if text_channel:
                        await text_channel.send(
                            "🚪 Koi nahi hai mere sath sab chore kar chale gaye, ab mai bhi ja rahi hu! 👋"
                        )
                    
                    log_audio_event(guild_id, "auto_disconnect_alone")
                    
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("alone_timer", e, guild_id=guild_id)
            finally:
                self.alone_timers.pop(guild_id, None)
        
        self.alone_timers[guild_id] = asyncio.create_task(alone_timer())
    
    async def start_idle_timer(self, ctx):
        """Start timer to leave if bot stays idle (paused/empty queue)"""
        guild = ctx.guild
        guild_id = guild.id
        
        # Cancel existing timer
        self.cancel_idle_timer(guild_id)
        
        async def idle_timer():
            try:
                logger.info(f"Starting idle timer for guild {guild_id} ({config.idle_timeout}s)")
                await asyncio.sleep(config.idle_timeout)
                
                # Double check conditions
                is_playing = ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused())
                queue = self.get_queue(guild_id)
                
                if not is_playing and not queue:
                    # Find text channel to send message (prefer ctx channel, fallback to system)
                    text_channel = ctx.channel
                    if not text_channel or not text_channel.permissions_for(guild.me).send_messages:
                        text_channel = guild.system_channel
                        if not text_channel:
                            for channel in guild.text_channels:
                                if channel.permissions_for(guild.me).send_messages:
                                    text_channel = channel
                                    break

                    # Disconnect and clean up
                    if ctx.voice_client:
                        await ctx.voice_client.disconnect()
                    
                    self.clear_queue(guild_id)
                    self.cancel_alone_timer(guild_id)
                    
                    # Import ui_manager here to avoid circular dependency
                    from ui.views import ui_manager
                    await ui_manager.cleanup_all_messages(guild_id)
                    
                    if text_channel:
                        try:
                            await text_channel.send(
                                "💤 **Idle Timeout** | Quite der se kuch nahi baja, isliye main ja rahi hoon. Business hai mera! 👋"
                            )
                        except Exception:
                            pass
                    
                    log_audio_event(guild_id, "auto_disconnect_idle")
                    
            except asyncio.CancelledError:
                logger.info(f"Idle timer cancelled for guild {guild_id}")
            except Exception as e:
                logger.error("idle_timer", e, guild_id=guild_id)
            finally:
                self.idle_timers.pop(guild_id, None)
        
        self.idle_timers[guild_id] = asyncio.create_task(idle_timer())
    
    def cancel_idle_timer(self, guild_id: int):
        """Cancel the idle timer"""
        if guild_id in self.idle_timers:
            self.idle_timers[guild_id].cancel()
            self.idle_timers.pop(guild_id, None)
            logger.info(f"Cancelled idle timer for guild {guild_id}")

    def cancel_alone_timer(self, guild_id: int):
        """Cancel the alone timer"""
        if guild_id in self.alone_timers:
            self.alone_timers[guild_id].cancel()
            self.alone_timers.pop(guild_id, None)
    
    async def validate_queue_songs(self, guild_id: int, max_check: int = 10) -> int:
        """Validate and clean up queue songs, return number of songs removed"""
        queue = self.get_queue(guild_id)
        if not queue:
            return 0
        
        removed_count = 0
        current_idx = self.guild_current_index.get(guild_id, 0)
        
        # Check a limited number of songs to avoid blocking
        check_count = min(max_check, len(queue))
        songs_to_remove = []
        
        for i in range(check_count):
            if i < len(queue):
                song = queue[i]
                # Skip currently playing song
                if i == current_idx:
                    continue
                
                # Check for obvious invalid songs
                if (not song.title or song.title.lower() in ['deleted video', 'private video', 'unavailable'] or
                    'deleted' in song.title.lower() or 'private' in song.title.lower()):
                    songs_to_remove.append(i)
        
        # Remove invalid songs (in reverse order to maintain indices)
        for idx in reversed(songs_to_remove):
            self.remove_song(guild_id, idx)
            removed_count += 1
        
        return removed_count
    
    # Autoplay functionality
    def enable_autoplay(self, guild_id: int):
        """Enable autoplay for a guild"""
        self.autoplay_enabled[guild_id] = True
        logger.info(f"Autoplay enabled for guild {guild_id}")
    
    def disable_autoplay(self, guild_id: int):
        """Disable autoplay for a guild"""
        self.autoplay_enabled[guild_id] = False
        logger.info(f"Autoplay disabled for guild {guild_id}")
    
    def is_autoplay_enabled(self, guild_id: int) -> bool:
        """Check if autoplay is enabled for a guild"""
        return self.autoplay_enabled.get(guild_id, False)
    
    async def get_autoplay_recommendations(self, guild_id: int, count: int = 5) -> List[Song]:
        """
        Fetch next batch of related songs from YouTube based on listening history
        
        Args:
            guild_id: Guild ID
            count: Number of songs to fetch
            
        Returns:
            List of Song objects
        """
        try:
            # Import here to avoid circular dependency
            from audio.recommendation_service import recommendation_manager
            from utils.listening_history import listening_history
            
            # Get the last played video URL
            last_url = listening_history.get_last_played_url(guild_id)
            
            if not last_url:
                logger.warning(f"No listening history found for guild {guild_id}")
                return []
            
            # Get current queue to avoid duplicates
            queue = self.get_queue(guild_id)
            
            # Create set of titles and URLs already in queue for fast lookup
            existing_titles = {song.title.lower() for song in queue if song.title}
            existing_urls = {song.webpage_url for song in queue if song.webpage_url}
            
            # Also track the current/last playing song URL to avoid re-adding it
            current_song = self.get_current_song(guild_id)
            if current_song and current_song.webpage_url:
                existing_urls.add(current_song.webpage_url)
            if current_song and current_song.original_url:
                existing_urls.add(current_song.original_url)
            
            # Fetch more recommendations than needed to account for filtering
            fetch_count = min(count * 3, 15)  # Fetch 3x what we need, max 15
            recommendations = await recommendation_manager.get_next_recommendations(
                last_url,
                count=fetch_count
            )
            
            if not recommendations:
                logger.warning(f"No recommendations returned for guild {guild_id}")
                return []
            
            # Filter out duplicates and convert to Song objects
            songs = []
            for rec in recommendations:
                # Skip if URL or title already exists in queue
                if rec.video_url in existing_urls:
                    logger.info(f"Skipping duplicate URL: {rec.title}")
                    continue
                
                if rec.title.lower() in existing_titles:
                    logger.info(f"Skipping duplicate title: {rec.title}")
                    continue
                
                # Add to result
                song = Song(
                    title=rec.title,
                    webpage_url=rec.video_url,
                    duration=rec.duration,
                    thumbnail=rec.thumbnail,
                    requester_id=0,  # Autoplay requester
                    is_lazy=True  # Will be resolved when played
                )
                songs.append(song)
                
                # Also add to existing sets to avoid dupes within this batch
                existing_urls.add(rec.video_url)
                existing_titles.add(rec.title.lower())
                
                # Stop once we have enough unique songs
                if len(songs) >= count:
                    break
            
            logger.info(f"Generated {len(songs)} unique autoplay recommendations for guild {guild_id}")
            return songs
            
        except Exception as e:
            logger.error("get_autoplay_recommendations", e, guild_id=guild_id)
            return []


# Global audio manager instance
audio_manager = AudioManager() 