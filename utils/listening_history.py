"""
Listening History Manager for Music Bot
Tracks recently played songs per server to provide context for recommendations
"""
import json
import os
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import dataclass, asdict
from utils.logger import logger


@dataclass
class HistoryEntry:
    """Single history entry"""
    title: str
    url: str
    played_at: str  # ISO format timestamp
    requester_id: int
    duration: Optional[int] = None


class ListeningHistoryManager:
    """Lightweight tracker for recent songs per server"""
    
    def __init__(self, history_dir: str = "autoplay_data"):
        self.history_dir = history_dir
        self.max_history_size = 20  # Keep last 20 songs per server
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure the history directory exists"""
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)
            logger.info(f"Created history directory: {self.history_dir}")
    
    def _get_history_file(self, guild_id: int) -> str:
        """Get the history file path for a guild"""
        return os.path.join(self.history_dir, f"{guild_id}_history.json")
    
    def record_play(self, guild_id: int, title: str, url: str, requester_id: int, duration: Optional[int] = None):
        """
        Record when a song is played
        
        Args:
            guild_id: Discord guild ID
            title: Song title
            url: YouTube video URL
            requester_id: User ID who requested the song
            duration: Song duration in seconds
        """
        try:
            # Load existing history
            history = self._load_history(guild_id)
            
            # Create new entry
            entry = HistoryEntry(
                title=title,
                url=url,
                played_at=datetime.now().isoformat(),
                requester_id=requester_id,
                duration=duration
            )
            
            # Add to beginning of list (most recent first)
            history.insert(0, entry)
            
            # Keep only the most recent entries
            if len(history) > self.max_history_size:
                history = history[:self.max_history_size]
            
            # Save updated history
            self._save_history(guild_id, history)
            
            logger.info(f"Recorded play history for guild {guild_id}: {title}")
            
        except Exception as e:
            logger.error("record_play", e, guild_id=guild_id)
    
    def get_recent_tracks(self, guild_id: int, count: int = 10) -> List[HistoryEntry]:
        """
        Get N most recent songs
        
        Args:
            guild_id: Discord guild ID
            count: Number of recent tracks to return
            
        Returns:
            List of HistoryEntry objects (most recent first)
        """
        try:
            history = self._load_history(guild_id)
            return history[:count]
        except Exception as e:
            logger.error("get_recent_tracks", e, guild_id=guild_id)
            return []
    
    def get_last_played_url(self, guild_id: int) -> Optional[str]:
        """
        Get the last video URL that was played (for recommendations)
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            YouTube video URL or None
        """
        try:
            history = self._load_history(guild_id)
            if history:
                return history[0].url
            return None
        except Exception as e:
            logger.error("get_last_played_url", e, guild_id=guild_id)
            return None
    
    def clear_history(self, guild_id: int):
        """Clear all history for a guild"""
        try:
            history_file = self._get_history_file(guild_id)
            if os.path.exists(history_file):
                os.remove(history_file)
                logger.info(f"Cleared history for guild {guild_id}")
        except Exception as e:
            logger.error("clear_history", e, guild_id=guild_id)
    
    def _load_history(self, guild_id: int) -> List[HistoryEntry]:
        """Load history from JSON file"""
        history_file = self._get_history_file(guild_id)
        
        if not os.path.exists(history_file):
            return []
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [HistoryEntry(**entry) for entry in data]
        except json.JSONDecodeError:
            logger.warning(f"Corrupted history file for guild {guild_id}, resetting")
            return []
        except Exception as e:
            logger.error("_load_history", e, guild_id=guild_id)
            return []
    
    def _save_history(self, guild_id: int, history: List[HistoryEntry]):
        """Save history to JSON file"""
        history_file = self._get_history_file(guild_id)
        
        try:
            # Convert to dict for JSON serialization
            data = [asdict(entry) for entry in history]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error("_save_history", e, guild_id=guild_id)


# Global listening history manager instance
listening_history = ListeningHistoryManager()
