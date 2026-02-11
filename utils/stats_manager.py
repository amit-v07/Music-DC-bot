"""
Simple stats tracking system for song plays per server.
Uses JSON files for persistence without database complexity.
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
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
    requester_name: str = "Unknown"

@dataclass
class ServerStats:
    """Stats for a specific server"""
    guild_id: int
    guild_name: str = "Unknown Server"
    total_plays: int = 0
    most_played: Dict[str, int] = None
    recent_plays: int = 0  # Last 24 hours
    last_updated: str = None
    command_usage: Dict[str, int] = None
    
    def __post_init__(self):
        if self.most_played is None:
            self.most_played = {}
        if self.command_usage is None:
            self.command_usage = {}
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()

class StatsManager:
    """Manages song play statistics using JSON files"""
    
    def __init__(self, stats_dir: str = "stats"):
        self.stats_dir = stats_dir
        self.plays_file = os.path.join(stats_dir, "song_plays.json")
        self.server_stats_file = os.path.join(stats_dir, "server_stats.json")
        self.actions_file = os.path.join(stats_dir, "actions_queue.json")
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
    
    async def record_song_play(self, guild_id: int, title: str, requester_id: int, duration: int = None, guild_name: str = None, requester_name: str = "Unknown"):
        """Record a song play"""
        async with self._lock:
            try:
                # Create song play record
                play = SongPlay(
                    title=title,
                    requester_id=requester_id,
                    guild_id=guild_id,
                    timestamp=datetime.now().isoformat(),
                    duration=duration,
                    requester_name=requester_name
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

    async def record_command_usage(self, guild_id: int, command: str):
        """Record usage of a command"""
        async with self._lock:
            try:
                key = str(guild_id)
                self._ensure_server_stats_entry(guild_id)
                
                stats_dict = self._server_stats_cache[key]
                if 'command_usage' not in stats_dict:
                    stats_dict['command_usage'] = {}
                
                cmd_usage = stats_dict['command_usage']
                cmd_usage[command] = cmd_usage.get(command, 0) + 1
                
                self._pending_writes += 1
                await self._maybe_persist()
            except Exception as e:
                logger.error("record_command_usage", e, guild_id=guild_id)
    
    def _ensure_server_stats_entry(self, guild_id: int):
        """Ensure server stats entry exists in cache"""
        key = str(guild_id)
        if key not in self._server_stats_cache:
            self._server_stats_cache[key] = asdict(ServerStats(guild_id=guild_id))

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
            # Handle potential missing fields in old data
            if 'command_usage' not in stats_dict:
                stats_dict['command_usage'] = {}
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
                if 'command_usage' not in stats_dict:
                    stats_dict['command_usage'] = {}
                return ServerStats(**stats_dict)
            return ServerStats(guild_id=guild_id)
        except Exception as e:
            logger.error("get_server_stats", e, guild_id=guild_id)
            return ServerStats(guild_id=guild_id)
    
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
            
            # Use cached stats
            for guild_id, stats in self._server_stats_cache.items():
                guild_name = stats.get('guild_name', 'Unknown Server')
                
                servers.append({
                    'guild_id': int(guild_id),
                    'guild_name': guild_name,
                    'total_plays': stats.get('total_plays', 0),
                    'recent_plays': stats.get('recent_plays', 0),
                    'last_updated': stats.get('last_updated', ''),
                    'command_count': sum(stats.get('command_usage', {}).values())
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
            combined_command_usage = {}
            
            # Use cached stats
            for guild_id, stats in self._server_stats_cache.items():
                total_plays += stats.get('total_plays', 0)
                total_recent += stats.get('recent_plays', 0)
                total_guilds += 1
                
                # Combine most played songs
                for song, count in stats.get('most_played', {}).items():
                    combined_most_played[song] = combined_most_played.get(song, 0) + count
                
                # Combine command usage
                for cmd, count in stats.get('command_usage', {}).items():
                    combined_command_usage[cmd] = combined_command_usage.get(cmd, 0) + count
            
            # Get server information
            servers = await self.get_all_servers()
            
            # Get top listeners & activity
            top_listeners = self._get_global_top_listeners()
            peak_activity = self._get_peak_activity()
            
            return {
                'total_plays': total_plays,
                'active_guilds': total_guilds,
                'recent_plays': total_recent,
                'most_played': dict(sorted(combined_most_played.items(), 
                                         key=lambda x: x[1], reverse=True)[:20]),
                'command_usage': dict(sorted(combined_command_usage.items(),
                                           key=lambda x: x[1], reverse=True)),
                'top_listeners': top_listeners,
                'peak_activity': peak_activity,
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
    
    def _get_global_top_listeners(self, limit: int = 10) -> List[Dict]:
        """Get top listeners across all servers"""
        listeners = {}
        for play in self._plays_cache:
            name = play.get('requester_name', 'Unknown')
            if name != 'Unknown':
                listeners[name] = listeners.get(name, 0) + 1
        
        sorted_listeners = sorted(listeners.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{'name': name, 'count': count} for name, count in sorted_listeners]

    def _get_peak_activity(self) -> List[int]:
        """Get activity by hour of day (0-23) based on all plays"""
        # Returns simple list of 24 integers
        hours = [0] * 24
        for play in self._plays_cache:
            try:
                # Assuming timestamp is ISO format
                ts = datetime.fromisoformat(play.get('timestamp'))
                hours[ts.hour] += 1
            except Exception:
                continue
        return hours

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

    # --- Remote Control Action Queue ---

    async def queue_action(self, guild_id: int, action: str, data: dict = None):
        """Queue an action for the bot to execute"""
        async with self._lock:
            try:
                actions = []
                if os.path.exists(self.actions_file):
                    try:
                        with open(self.actions_file, 'r', encoding='utf-8') as f:
                            actions = json.load(f)
                    except Exception:
                        actions = []
                
                new_action = {
                    'guild_id': guild_id,
                    'action': action,
                    'data': data or {},
                    'timestamp': datetime.now().isoformat(),
                    'id': str(os.urandom(4).hex()) 
                }
                
                actions.append(new_action)
                
                with open(self.actions_file, 'w', encoding='utf-8') as f:
                    json.dump(actions, f, indent=2)
                    
                logger.info(f"Queued action '{action}' for guild {guild_id}")
                return True
            except Exception as e:
                logger.error("queue_action", e)
                return False

    async def get_pending_actions(self) -> List[Dict]:
        """Get and clear pending actions for the bot to execute"""
        async with self._lock:
            try:
                if not os.path.exists(self.actions_file):
                    return []
                
                with open(self.actions_file, 'r', encoding='utf-8') as f:
                    actions = json.load(f)
                
                if not actions:
                    return []
                
                # Clear the file (consume actions)
                with open(self.actions_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                
                return actions
            except Exception as e:
                logger.error("get_pending_actions", e)
                return []

# Global stats manager instance
stats_manager = StatsManager()