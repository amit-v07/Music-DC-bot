# 🎵 Music Bot (2026 Pro Edition)

Music Bot is a high-performance, feature-rich Discord music bot designed for resource-constrained self-hosting. Built with Python 3.11+, `discord.py`, and `yt-dlp`, it delivers a premium listening experience with **gapless playback**, **SQLite persistence**, and **smart search** capabilities.

## 🚀 2026 Performance Upgrades

This version has been re-engineered for maximum efficiency on low-power hardware (like Mac Mini/Air or Raspberry Pi):

- **⚡ Blazing Fast Event Loop**: Powered by `uvloop` for C-accelerated async I/O.
- **🎧 Gapless Transitions**: Background pre-resolution of the next song in the queue eliminates buffering pauses.
- **💾 SQLite Backend**: Robust data persistence for all server settings, prefixes, and listening stats using `aiosqlite` with WAL mode.
- **🚦 Concurrency Control**: Intelligent stream management with `asyncio.Semaphore` prevents CPU spikes on dual-core hosts.
- **🔍 Smart Auto-Select**: Search scoring algorithm that automatically picks the best match (official videos, top views, exact title match).
- **📶 Audio Quality Tiers**: Per-server `!quality` command to toggle between Low (64k), Medium (128k), and High (192k) bitrates.
- **🧠 Intelligent Caching**: Thread-safe `TTLCache` for instant resolution of recently played songs.

## ✨ Key Features

### 🤖 **AI & Smart Logic**
- **Smart Autoplay**: Automatically plays related songs when your queue ends, powered by listening history.
- **Intelligent Search**: Scoring system that prioritizes official tracks and high-quality uploads.
- **Personalized Recommendations**: `!recommend` based on your server's unique music taste.

### 🎵 **Premium Player Experience**
- **Persistent Player UI**: A sleek, interactive "Now Playing" interface including a live progress bar.
- **Zero Latency Controls**: Button-based controls (Play/Pause, Skip, Stop) with instant feedback.
- **Dynamic Prefix**: Change the bot prefix per-server with `!setprefix` (persists across restarts).

### 🛠️ **Production-Ready Deployment**
- **Docker First**: Optimized single-stage Docker images with non-root security.
- **Resource Limiting**: Built-in CPU/Memory caps in Docker Compose for stable background operation.
- **Health Monitoring**: Integrated health checks for both the Bot and the Web Dashboard.

## 🎯 Commands

### 🎮 **Basic Controls**
| Command | Aliases | Description |
|---|---|---|
| `!join` | | Joins your voice channel |
| `!play <query/URL>` | `!p` | Plays music using Smart Auto-Select or direct URL |
| `!pause` | | Pauses current playback |
| `!resume` | `!start` | Resumes playback |
| `!stop` | | Stops playback, clears queue, and disables autoplay |
| `!leave` | `!dc`, `!bye` | Disconnects and cleans up |

### ⏭️ **Queue & Navigation**
| Command | Aliases | Description |
|---|---|---|
| `!skip` | `!next` | Skip to the next song |
| `!jump <number>` | `!goto` | Jump to a specific position in the queue |
| `!queue` | `!q` | Show the current queue with pagination |
| `!shuffle` | | Randomly reorder the queue |
| `!cleanqueue` | `!clear` | Remove duplicates or broken streams |

### 👑 **Admin Commands**
| Command | Description |
|---|---|
| `!setprefix <p>` | Permanently change the command prefix for this server |
| `!quality <level>` | Set audio bitrate: `low` (64k), `medium` (128k), `high` (192k) |
| `!stats` | View listening analytics for the current server |
| `!resetstats` | Wipe all stats for this server (Admin only) |

## 🐳 Docker Deployment (Recommended)

This is the only officially supported deployment method for production environments.

1. **Clone & Configure**:
   ```bash
   git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
   cd Music-DC-bot
   cp .env.example .env
   # Edit .env with your DISCORD_TOKEN
   ```

2. **Launch**:
   ```bash
   docker-compose up -d
   ```

3. **Status**:
   ```bash
   docker-compose ps
   docker-compose logs -f bot
   ```

## 📊 Web Dashboard
Monitor your bot's global performance at `http://localhost:5000`.
- Real-time CPU/RAM metrics
- Global listening trends
- Remote command queueing (for server owners)

## 🛠️ Performance Stack
- **Core**: Python 3.11, `discord.py` 2.3+
- **Audio**: `yt-dlp` (Streamer), `FFmpeg` (Transcoder)
- **Engine**: `uvloop` (Event Loop), `aiosqlite` (Database)
- **Web**: `FastAPI` + `python-socketio` (ASGI) + `Uvicorn`