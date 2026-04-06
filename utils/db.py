"""
utils/db.py — Async SQLite backend for Music Bot
Provides all persistent storage: guild stats, command usage, listening history,
guild settings (prefix, audio quality).

DB file: /data/music_bot.db  (Docker named volume `bot-data` mounted at /data)
"""
import asyncio
import os
import json
import aiosqlite
from typing import Dict, List, Optional, Tuple
from utils.logger import logger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.getenv("DB_PATH", "/data/music_bot.db")

# Module-level connection — initialised by init_db(), shared across all callers.
_db: Optional[aiosqlite.Connection] = None
_db_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_stats (
    guild_id    INTEGER,
    song_id     TEXT,
    title       TEXT,
    play_count  INTEGER DEFAULT 0,
    last_played REAL,
    PRIMARY KEY (guild_id, song_id)
);

CREATE TABLE IF NOT EXISTS command_usage (
    guild_id INTEGER,
    command  TEXT,
    count    INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, command)
);

CREATE TABLE IF NOT EXISTS listening_history (
    guild_id  INTEGER,
    song_id   TEXT,
    title     TEXT,
    played_at REAL
);

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id       INTEGER PRIMARY KEY,
    audio_quality  TEXT    DEFAULT 'medium',
    command_prefix TEXT    DEFAULT '!'
);

CREATE INDEX IF NOT EXISTS idx_history_guild
    ON listening_history (guild_id, played_at DESC);
"""

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """
    Open the SQLite connection and apply the schema.
    Must be called once during bot startup (setup_hook).
    """
    global _db

    # Ensure the data directory exists (important for first run inside Docker)
    data_dir = os.path.dirname(DB_PATH)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)

    async with _db_lock:
        if _db is not None:
            return  # Already initialised

        try:
            conn = await aiosqlite.connect(DB_PATH)
            conn.row_factory = aiosqlite.Row
            # WAL mode: much better concurrent read performance
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.executescript(_SCHEMA)
            await conn.commit()
            _db = conn
            logger.info(f"SQLite database initialised at {DB_PATH}")
        except Exception as e:
            logger.error("db_init", e)
            raise


async def close_db() -> None:
    """Close the database connection gracefully."""
    global _db
    async with _db_lock:
        if _db is not None:
            await _db.close()
            _db = None


def _conn() -> aiosqlite.Connection:
    """Return the active connection, raising if not initialised."""
    if _db is None:
        raise RuntimeError("Database not initialised — call await db.init_db() first")
    return _db


# ---------------------------------------------------------------------------
# Guild settings — prefix
# ---------------------------------------------------------------------------


async def get_prefix(guild_id: int) -> str:
    """Return the command prefix configured for this guild (default '!')."""
    try:
        async with _conn().execute(
            "SELECT command_prefix FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
            return row["command_prefix"] if row else "!"
    except Exception as e:
        logger.error("db_get_prefix", e, guild_id=guild_id)
        return "!"


async def set_prefix(guild_id: int, prefix: str) -> None:
    """Persist a per-guild command prefix."""
    try:
        await _conn().execute(
            """
            INSERT INTO guild_settings (guild_id, command_prefix)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET command_prefix = excluded.command_prefix
            """,
            (guild_id, prefix),
        )
        await _conn().commit()
    except Exception as e:
        logger.error("db_set_prefix", e, guild_id=guild_id)


async def get_all_prefixes() -> Dict[int, str]:
    """Load all stored guild prefixes — used to warm the in-memory cache on startup."""
    prefixes: Dict[int, str] = {}
    try:
        async with _conn().execute(
            "SELECT guild_id, command_prefix FROM guild_settings"
        ) as cur:
            async for row in cur:
                prefixes[row["guild_id"]] = row["command_prefix"]
    except Exception as e:
        logger.error("db_get_all_prefixes", e)
    return prefixes


# ---------------------------------------------------------------------------
# Guild settings — audio quality
# ---------------------------------------------------------------------------


async def get_audio_quality(guild_id: int) -> str:
    """Return the audio quality tier for this guild (default 'medium')."""
    try:
        async with _conn().execute(
            "SELECT audio_quality FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
            return row["audio_quality"] if row else "medium"
    except Exception as e:
        logger.error("db_get_audio_quality", e, guild_id=guild_id)
        return "medium"


async def set_audio_quality(guild_id: int, quality: str) -> None:
    """Persist per-guild audio quality."""
    try:
        await _conn().execute(
            """
            INSERT INTO guild_settings (guild_id, audio_quality)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET audio_quality = excluded.audio_quality
            """,
            (guild_id, quality),
        )
        await _conn().commit()
    except Exception as e:
        logger.error("db_set_audio_quality", e, guild_id=guild_id)


# ---------------------------------------------------------------------------
# Stats — recording
# ---------------------------------------------------------------------------


async def record_play(
    guild_id: int,
    song_id: str,
    title: str,
    played_at: float,
) -> None:
    """Upsert a song-play into guild_stats and append to listening_history."""
    try:
        conn = _conn()
        await conn.execute(
            """
            INSERT INTO guild_stats (guild_id, song_id, title, play_count, last_played)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(guild_id, song_id) DO UPDATE
                SET play_count  = play_count + 1,
                    last_played = excluded.last_played,
                    title       = excluded.title
            """,
            (guild_id, song_id, title, played_at),
        )
        await conn.execute(
            "INSERT INTO listening_history (guild_id, song_id, title, played_at) VALUES (?, ?, ?, ?)",
            (guild_id, song_id, title, played_at),
        )
        await conn.commit()
    except Exception as e:
        logger.error("db_record_play", e, guild_id=guild_id)


async def record_command(guild_id: int, command: str) -> None:
    """Increment a command usage counter."""
    try:
        await _conn().execute(
            """
            INSERT INTO command_usage (guild_id, command, count) VALUES (?, ?, 1)
            ON CONFLICT(guild_id, command) DO UPDATE SET count = count + 1
            """,
            (guild_id, command),
        )
        await _conn().commit()
    except Exception as e:
        logger.error("db_record_command", e, guild_id=guild_id)


# ---------------------------------------------------------------------------
# Stats — querying
# ---------------------------------------------------------------------------


async def get_server_stats(guild_id: int) -> Dict:
    """Return aggregated stats for one guild."""
    stats = {
        "guild_id": guild_id,
        "total_plays": 0,
        "most_played": {},
        "recent_plays": 0,
        "command_usage": {},
        "last_updated": None,
    }
    try:
        conn = _conn()
        import time

        # Total plays + most-played map
        async with conn.execute(
            "SELECT song_id, title, play_count, last_played FROM guild_stats WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            async for row in cur:
                stats["total_plays"] += row["play_count"]
                stats["most_played"][row["title"]] = row["play_count"]
                if stats["last_updated"] is None or (row["last_played"] and row["last_played"] > stats["last_updated"]):
                    stats["last_updated"] = row["last_played"]

        # Recent plays in last 24 h
        cutoff = time.time() - 86400
        async with conn.execute(
            "SELECT COUNT(*) AS cnt FROM listening_history WHERE guild_id = ? AND played_at > ?",
            (guild_id, cutoff),
        ) as cur:
            row = await cur.fetchone()
            stats["recent_plays"] = row["cnt"] if row else 0

        # Command usage
        async with conn.execute(
            "SELECT command, count FROM command_usage WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            async for row in cur:
                stats["command_usage"][row["command"]] = row["count"]

    except Exception as e:
        logger.error("db_get_server_stats", e, guild_id=guild_id)

    return stats


async def get_server_top_songs(guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
    """Return (title, play_count) tuples sorted by play_count desc."""
    results = []
    try:
        async with _conn().execute(
            """
            SELECT title, play_count FROM guild_stats
            WHERE guild_id = ?
            ORDER BY play_count DESC
            LIMIT ?
            """,
            (guild_id, limit),
        ) as cur:
            async for row in cur:
                results.append((row["title"], row["play_count"]))
    except Exception as e:
        logger.error("db_get_server_top_songs", e, guild_id=guild_id)
    return results


async def get_global_stats() -> Dict:
    """Return combined stats across all guilds."""
    stats = {
        "total_plays": 0,
        "active_guilds": 0,
        "recent_plays": 0,
        "most_played": {},
        "command_usage": {},
    }
    try:
        import time

        conn = _conn()

        # Total plays per guild + most played
        async with conn.execute(
            "SELECT guild_id, title, play_count FROM guild_stats"
        ) as cur:
            async for row in cur:
                stats["total_plays"] += row["play_count"]
                title = row["title"]
                stats["most_played"][title] = stats["most_played"].get(title, 0) + row["play_count"]

        # Active guilds (those with at least one play)
        async with conn.execute(
            "SELECT COUNT(DISTINCT guild_id) AS cnt FROM guild_stats"
        ) as cur:
            row = await cur.fetchone()
            stats["active_guilds"] = row["cnt"] if row else 0

        # Recent plays across all guilds
        cutoff = time.time() - 86400
        async with conn.execute(
            "SELECT COUNT(*) AS cnt FROM listening_history WHERE played_at > ?",
            (cutoff,),
        ) as cur:
            row = await cur.fetchone()
            stats["recent_plays"] = row["cnt"] if row else 0

        # Command usage
        async with conn.execute("SELECT command, SUM(count) AS total FROM command_usage GROUP BY command") as cur:
            async for row in cur:
                stats["command_usage"][row["command"]] = row["total"]

        # Sort most_played
        stats["most_played"] = dict(
            sorted(stats["most_played"].items(), key=lambda x: x[1], reverse=True)[:20]
        )

    except Exception as e:
        logger.error("db_get_global_stats", e)

    return stats


async def reset_server_stats(guild_id: int) -> None:
    """Delete all stats rows for a guild."""
    try:
        conn = _conn()
        await conn.execute("DELETE FROM guild_stats WHERE guild_id = ?", (guild_id,))
        await conn.execute("DELETE FROM command_usage WHERE guild_id = ?", (guild_id,))
        await conn.execute("DELETE FROM listening_history WHERE guild_id = ?", (guild_id,))
        await conn.commit()
    except Exception as e:
        logger.error("db_reset_server_stats", e, guild_id=guild_id)


# ---------------------------------------------------------------------------
# JSON migration  (runs once on first startup)
# ---------------------------------------------------------------------------

_MIGRATION_FLAG = os.path.join(os.path.dirname(DB_PATH), ".json_migrated")


async def migrate_from_json(stats_dir: str = "stats") -> None:
    """
    One-time migration of legacy JSON stats files into the SQLite DB.
    Writes a sentinel file to /data/.json_migrated so it only runs once.
    """
    if os.path.exists(_MIGRATION_FLAG):
        return  # Already done

    import time as _time

    server_stats_file = os.path.join(stats_dir, "server_stats.json")
    plays_file = os.path.join(stats_dir, "song_plays.json")

    migrated = False

    # Migrate server_stats.json -> guild_stats + command_usage
    if os.path.exists(server_stats_file):
        try:
            with open(server_stats_file, "r", encoding="utf-8") as f:
                server_data: dict = json.load(f)

            for guild_id_str, stats in server_data.items():
                try:
                    guild_id = int(guild_id_str)
                except ValueError:
                    continue

                # most_played -> guild_stats
                for title, count in stats.get("most_played", {}).items():
                    song_id = title[:200]  # use truncated title as surrogate ID
                    await record_play(guild_id, song_id, title, _time.time())
                    # Overwrite play_count directly since record_play increments by 1 each call
                    await _conn().execute(
                        "UPDATE guild_stats SET play_count = ? WHERE guild_id = ? AND song_id = ?",
                        (count, guild_id, song_id),
                    )

                # command_usage -> command_usage table
                for cmd, count in stats.get("command_usage", {}).items():
                    await _conn().execute(
                        """
                        INSERT INTO command_usage (guild_id, command, count) VALUES (?, ?, ?)
                        ON CONFLICT(guild_id, command) DO UPDATE SET count = excluded.count
                        """,
                        (guild_id, cmd, count),
                    )

            await _conn().commit()
            logger.info("Migrated server_stats.json -> SQLite")
            migrated = True
        except Exception as e:
            logger.error("migrate_server_stats", e)

    # Migrate song_plays.json -> listening_history
    if os.path.exists(plays_file):
        try:
            with open(plays_file, "r", encoding="utf-8") as f:
                plays: list = json.load(f)

            for play in plays:
                try:
                    from datetime import datetime as _dt
                    guild_id = int(play.get("guild_id", 0))
                    title = play.get("title", "")
                    ts_str = play.get("timestamp", "")
                    ts = _dt.fromisoformat(ts_str).timestamp() if ts_str else _time.time()
                    song_id = title[:200]
                    await _conn().execute(
                        "INSERT OR IGNORE INTO listening_history (guild_id, song_id, title, played_at) VALUES (?, ?, ?, ?)",
                        (guild_id, song_id, title, ts),
                    )
                except Exception:
                    continue

            await _conn().commit()
            logger.info(f"Migrated {len(plays)} play records -> listening_history")
            migrated = True
        except Exception as e:
            logger.error("migrate_song_plays", e)

    if migrated or not (os.path.exists(server_stats_file) or os.path.exists(plays_file)):
        # Write the sentinel so we never run this again
        try:
            with open(_MIGRATION_FLAG, "w") as f:
                f.write("migrated\n")
        except Exception:
            pass
