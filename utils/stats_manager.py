"""
Simple stats tracking system for song plays per server.
Uses JSON files for persistence without database complexity.
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from utils.logger import logger

@dataclass
class SongPlay:
    """Represents a song play record"""
    title: str
    requester_id: int
    guild_id: int
    timestamp: str
    duration: int = None

@dataclass
class ServerStats:
    """Stats for a specific server"""
    guild_id: int
    guild_name: str = "Unknown Server"
    total_plays: int = 0
    most_played: Dict[str, int] = None
    recent_plays: int = 0  # Last 24 hours
    last_updated: str = None
    
    def __post_init__(self):
        if self.most_played is None:
            self.most_played = {}
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()

class StatsManager:
    """Manages song play statistics using JSON files"""
    
    def __init__(self, stats_dir: str = "stats"):
        self.stats_dir = stats_dir
        self.plays_file = os.path.join(stats_dir, "song_plays.json")
        self.server_stats_file = os.path.join(stats_dir, "server_stats.json")
        self._ensure_stats_dir()
        self._lock = asyncio.Lock()
        # In-memory caches to minimize disk I/O
        self._plays_cache: List[dict] = []
        self._server_stats_cache: Dict[str, dict] = {}
        self._last_persist_ts: float = 0.0
        self._persist_interval_sec: float = 5.0
        self._pending_writes: int = 0
        # Load existing data into memory
        self._load_existing()
    
    def _ensure_stats_dir(self):
        """Create stats directory if it doesn't exist"""
        if not os.path.exists(self.stats_dir):
            os.makedirs(self.stats_dir)
    
    async def record_song_play(self, guild_id: int, title: str, requester_id: int, duration: int = None, guild_name: str = None):
        """Record a song play"""
        async with self._lock:
            try:
                # Create song play record
                play = SongPlay(
                    title=title,
                    requester_id=requester_id,
                    guild_id=guild_id,
                    timestamp=datetime.now().isoformat(),
                    duration=duration
                )
                
                # Update in-memory plays cache
                self._plays_cache.append(asdict(play))
                self._pending_writes += 1
                
                # Update server stats in-memory
                self._update_server_stats_in_memory(guild_id, title, guild_name)
                
                # Persist periodically to reduce disk churn
                await self._maybe_persist()
                
                logger.info(f"Recorded song play: {title} in guild {guild_id} ({guild_name})")
                
            except Exception as e:
                logger.error("record_song_play", e, guild_id=guild_id)
    
    def _load_existing(self):
        """Load existing stats into memory (best-effort)."""
        # Load plays cache
        if os.path.exists(self.plays_file):
            try:
                with open(self.plays_file, 'r', encoding='utf-8') as f:
                    self._plays_cache = json.load(f) or []
            except Exception:
                self._plays_cache = []
        # Cap size to avoid excessive memory
        if len(self._plays_cache) > 10000:
            self._plays_cache = self._plays_cache[-10000:]
        
        # Load server stats cache
        if os.path.exists(self.server_stats_file):
            try:
                with open(self.server_stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._server_stats_cache = data
            except Exception:
                self._server_stats_cache = {}
        
    async def _maybe_persist(self):
        """Persist caches to disk if interval or batch threshold reached."""
        import time
        now = time.time()
        if (now - self._last_persist_ts) >= self._persist_interval_sec or self._pending_writes >= 20:
            await self._persist_to_disk()
            self._last_persist_ts = now
            self._pending_writes = 0
    
    async def _persist_to_disk(self):
        """Write in-memory caches to disk (atomic best-effort)."""
        try:
            # Persist plays
            plays = self._plays_cache
            if len(plays) > 10000:
                plays = plays[-10000:]
            with open(self.plays_file, 'w', encoding='utf-8') as f:
                json.dump(plays, f, indent=2, ensure_ascii=False)
            
            # Persist server stats
            with open(self.server_stats_file, 'w', encoding='utf-8') as f:
                json.dump(self._server_stats_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("persist_to_disk", e)
    
    def _update_server_stats_in_memory(self, guild_id: int, title: str, guild_name: str = None):
        """Update aggregated server statistics in memory."""
        key = str(guild_id)
        if key in self._server_stats_cache:
            stats_dict = self._server_stats_cache[key]
            stats = ServerStats(**stats_dict)
        else:
            stats = ServerStats(guild_id=guild_id)
        
        # Update guild name if provided
        if guild_name and guild_name != "Unknown Server":
            stats.guild_name = guild_name
        
        # Update total plays
        stats.total_plays += 1
        
        # Update most played
        stats.most_played[title] = stats.most_played.get(title, 0) + 1
        
        # Update recent plays (last 24 hours) using plays cache
        stats.recent_plays = self._count_recent_plays_from_cache(guild_id)
        
        # Update timestamp
        stats.last_updated = datetime.now().isoformat()
        
        # Save back to cache
        self._server_stats_cache[key] = asdict(stats)
    
    async def get_server_stats(self, guild_id: int) -> ServerStats:
        """Get stats for a specific server"""
        try:
            key = str(guild_id)
            if key in self._server_stats_cache:
                stats_dict = self._server_stats_cache[key]
                if 'guild_name' not in stats_dict:
                    stats_dict['guild_name'] = "Unknown Server"
                return ServerStats(**stats_dict)
            return ServerStats(guild_id=guild_id)
        except Exception as e:
            logger.error("get_server_stats", e, guild_id=guild_id)
            return ServerStats(guild_id=guild_id)
    
    # Saving handled by periodic persistence of the in-memory cache
    
    def _count_recent_plays_from_cache(self, guild_id: int) -> int:
        """Count plays in the last 24 hours using in-memory cache."""
        try:
            cutoff = datetime.now() - timedelta(hours=24)
            recent_count = 0
            for play in self._plays_cache:
                if play.get('guild_id') == guild_id:
                    try:
                        play_time = datetime.fromisoformat(play.get('timestamp'))
                        if play_time > cutoff:
                            recent_count += 1
                    except Exception:
                        continue
            return recent_count
        except Exception as e:
            logger.error("count_recent_plays_cache", e, guild_id=guild_id)
            return 0
    
    async def get_all_servers(self) -> List[Dict]:
        """Get information about all servers"""
        try:
            servers = []
            
            if os.path.exists(self.server_stats_file):
                with open(self.server_stats_file, 'r', encoding='utf-8') as f:
                    all_stats = json.load(f)
                
                for guild_id, stats in all_stats.items():
                    # Ensure guild_name exists for backwards compatibility
                    guild_name = stats.get('guild_name', 'Unknown Server')
                    
                    servers.append({
                        'guild_id': int(guild_id),
                        'guild_name': guild_name,
                        'total_plays': stats.get('total_plays', 0),
                        'recent_plays': stats.get('recent_plays', 0),
                        'last_updated': stats.get('last_updated', '')
                    })
            
            # Sort by total plays (most active first)
            servers.sort(key=lambda x: x['total_plays'], reverse=True)
            return servers
            
        except Exception as e:
            logger.error("get_all_servers", e)
            return []

    async def get_global_stats(self) -> Dict:
        """Get combined stats across all servers"""
        try:
            total_plays = 0
            total_guilds = 0
            combined_most_played = {}
            total_recent = 0
            
            if os.path.exists(self.server_stats_file):
                with open(self.server_stats_file, 'r', encoding='utf-8') as f:
                    all_stats = json.load(f)
                
                for guild_id, stats in all_stats.items():
                    total_plays += stats.get('total_plays', 0)
                    total_recent += stats.get('recent_plays', 0)
                    total_guilds += 1
                    
                    # Combine most played songs
                    for song, count in stats.get('most_played', {}).items():
                        if song in combined_most_played:
                            combined_most_played[song] += count
                        else:
                            combined_most_played[song] = count
            
            # Get server information
            servers = await self.get_all_servers()
            
            return {
                'total_plays': total_plays,
                'active_guilds': total_guilds,
                'recent_plays': total_recent,
                'most_played': dict(sorted(combined_most_played.items(), 
                                         key=lambda x: x[1], reverse=True)[:20]),
                'servers': servers
            }
            
        except Exception as e:
            logger.error("get_global_stats", e)
            return {
                'total_plays': 0,
                'active_guilds': 0,
                'recent_plays': 0,
                'most_played': {},
                'servers': []
            }
    
    async def get_server_top_songs(self, guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top songs for a specific server"""
        try:
            stats = await self.get_server_stats(guild_id)
            sorted_songs = sorted(stats.most_played.items(), 
                                key=lambda x: x[1], reverse=True)
            return sorted_songs[:limit]
            
        except Exception as e:
            logger.error("get_server_top_songs", e, guild_id=guild_id)
            return []

# Global stats manager instance
stats_manager = StatsManager() 