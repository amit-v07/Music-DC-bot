"""
Stats manager for Music Bot.
Public API is unchanged — all reads/writes now go to SQLite via utils.db.
The JSON files in stats/ are kept intact so they can be inspected, but they
are no longer the source of truth after the first run.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from utils.logger import logger


# ---------------------------------------------------------------------------
# Data structures (kept for backward compat with callers that import them)
# ---------------------------------------------------------------------------

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
    recent_plays: int = 0
    last_updated: str = None
    command_usage: Dict[str, int] = None

    def __post_init__(self):
        if self.most_played is None:
            self.most_played = {}
        if self.command_usage is None:
            self.command_usage = {}
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Action queue (still JSON-file based — dashboard polls this)
# ---------------------------------------------------------------------------

class StatsManager:
    """Manages song play statistics — delegates persistence to SQLite via utils.db."""

    def __init__(self, stats_dir: str = "stats"):
        self.stats_dir = stats_dir
        self.actions_file = os.path.join(stats_dir, "actions_queue.json")
        self._ensure_stats_dir()
        self._lock = asyncio.Lock()
        self.bot = None

        # DB initialisation is deferred to first async call / explicit init
        self._db_ready = False

    def _ensure_stats_dir(self):
        if not os.path.exists(self.stats_dir):
            os.makedirs(self.stats_dir, exist_ok=True)

    def set_bot(self, bot):
        """Set bot instance for accessing guild information."""
        self.bot = bot
        logger.info("Bot instance set in stats_manager")

    # ------------------------------------------------------------------
    # DB bootstrap (called from setup_hook after asyncio loop is running)
    # ------------------------------------------------------------------

    async def init(self):
        """Initialise the SQLite database and run JSON migration once."""
        try:
            from utils import db
            await db.init_db()
            await db.migrate_from_json(self.stats_dir)
            self._db_ready = True
            logger.info("StatsManager: SQLite backend ready")
        except Exception as e:
            logger.error("stats_manager_init", e)
            # Non-fatal: bot will continue without persistent stats

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_song_play(
        self,
        guild_id: int,
        title: str,
        requester_id: int,
        duration: int = None,
        guild_name: str = None,
        requester_name: str = "Unknown",
    ):
        """Record a song play."""
        try:
            from utils import db
            song_id = title[:200]  # Use title as surrogate ID (keeps compat)
            await db.record_play(guild_id, song_id, title, time.time())
            logger.info(f"Recorded song play: {title} in guild {guild_id}")
        except Exception as e:
            logger.error("record_song_play", e, guild_id=guild_id)

    async def record_command_usage(self, guild_id: int, command: str):
        """Record usage of a command."""
        try:
            from utils import db
            await db.record_command(guild_id, command)
        except Exception as e:
            logger.error("record_command_usage", e, guild_id=guild_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def get_server_stats(self, guild_id: int) -> ServerStats:
        """Get stats for a specific server."""
        try:
            from utils import db
            raw = await db.get_server_stats(guild_id)
            last_ts = raw.get("last_updated")
            last_str = datetime.fromtimestamp(last_ts).isoformat() if last_ts else datetime.now().isoformat()
            return ServerStats(
                guild_id=guild_id,
                total_plays=raw["total_plays"],
                most_played=raw["most_played"],
                recent_plays=raw["recent_plays"],
                last_updated=last_str,
                command_usage=raw["command_usage"],
            )
        except Exception as e:
            logger.error("get_server_stats", e, guild_id=guild_id)
            return ServerStats(guild_id=guild_id)

    async def reset_server_stats(self, guild_id: int):
        """Reset all statistics for a specific server."""
        try:
            from utils import db
            await db.reset_server_stats(guild_id)
            logger.info(f"Reset stats for guild {guild_id}")
        except Exception as e:
            logger.error("reset_server_stats", e, guild_id=guild_id)

    async def get_server_top_songs(self, guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top songs for a specific server."""
        try:
            from utils import db
            return await db.get_server_top_songs(guild_id, limit)
        except Exception as e:
            logger.error("get_server_top_songs", e, guild_id=guild_id)
            return []

    async def get_all_servers(self) -> List[Dict]:
        """Get information about all servers the bot is in."""
        try:
            servers = []
            bot = getattr(self, "bot", None)

            if bot:
                from utils import db
                for guild in bot.guilds:
                    raw = await db.get_server_stats(guild.id)
                    servers.append({
                        "guild_id": guild.id,
                        "guild_name": guild.name,
                        "total_plays": raw["total_plays"],
                        "recent_plays": raw["recent_plays"],
                        "last_updated": (
                            datetime.fromtimestamp(raw["last_updated"]).isoformat()
                            if raw.get("last_updated") else ""
                        ),
                        "command_count": sum(raw["command_usage"].values()),
                        "in_voice": guild.voice_client is not None,
                        "voice_channel": (
                            guild.voice_client.channel.name
                            if guild.voice_client and guild.voice_client.channel
                            else None
                        ),
                    })

            servers.sort(key=lambda x: x["total_plays"], reverse=True)
            return servers

        except Exception as e:
            logger.error("get_all_servers", e)
            return []

    async def get_global_stats(self) -> Dict:
        """Get combined stats across all servers."""
        try:
            from utils import db
            base = await db.get_global_stats()

            # Supplement with server list from bot guilds
            servers = await self.get_all_servers()

            # Rebuild top_listeners from listening_history is expensive;
            # return empty list here — dashboard can add a dedicated endpoint later.
            return {
                "total_plays": base["total_plays"],
                "active_guilds": base["active_guilds"],
                "recent_plays": base["recent_plays"],
                "most_played": base["most_played"],
                "command_usage": base["command_usage"],
                "top_listeners": [],
                "peak_activity": [0] * 24,
                "servers": servers,
            }
        except Exception as e:
            logger.error("get_global_stats", e)
            return {
                "total_plays": 0,
                "active_guilds": 0,
                "recent_plays": 0,
                "most_played": {},
                "servers": [],
            }

    # ------------------------------------------------------------------
    # Remote Control Action Queue (still file-based — simple and fast)
    # ------------------------------------------------------------------

    async def queue_action(self, guild_id: int, action: str, data: dict = None):
        """Queue an action for the bot to execute."""
        async with self._lock:
            try:
                new_action = {
                    "guild_id": guild_id,
                    "action": action,
                    "data": data or {},
                    "timestamp": datetime.now().isoformat(),
                    "id": os.urandom(4).hex(),
                }

                def _write_action():
                    actions = []
                    if os.path.exists(self.actions_file):
                        try:
                            with open(self.actions_file, "r", encoding="utf-8") as f:
                                actions = json.load(f)
                        except Exception:
                            actions = []
                    actions.append(new_action)
                    with open(self.actions_file, "w", encoding="utf-8") as f:
                        json.dump(actions, f, indent=2)

                await asyncio.to_thread(_write_action)
                logger.info(f"Queued action '{action}' for guild {guild_id}")
                return True
            except Exception as e:
                logger.error("queue_action", e)
                return False

    async def get_pending_actions(self) -> List[Dict]:
        """Get and clear pending actions for the bot to execute."""
        async with self._lock:
            try:
                def _read_and_clear():
                    if not os.path.exists(self.actions_file):
                        return []
                    with open(self.actions_file, "r", encoding="utf-8") as f:
                        actions = json.load(f)
                    if not actions:
                        return []
                    with open(self.actions_file, "w", encoding="utf-8") as f:
                        json.dump([], f)
                    return actions

                return await asyncio.to_thread(_read_and_clear)
            except Exception as e:
                logger.error("get_pending_actions", e)
                return []


# Global stats manager instance
stats_manager = StatsManager()