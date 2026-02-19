# Music Bot

Music Bot is a feature-rich Discord music bot built with Python, `discord.py`, and `yt-dlp`. It provides an intuitive music experience with **AI-powered recommendations**, **persistent interactive UI**, **smart autoplay mode**, advanced queue management, and seamless playback across multiple Discord servers simultaneously. The bot features modern UI controls, intelligent music discovery, and comprehensive music management capabilities.

## ✨ Key Features

### 🤖 **AI-Powered Music Discovery**
- **Smart Autoplay**: Automatically plays related songs when your queue ends, powered by listening history
- **Personalized Recommendations**: Get song suggestions tailored to your music taste
- **Learning Algorithm**: Improves recommendations based on what you and your server listen to
- **Seamless Experience**: Never run out of music with intelligent queue management

### 🎵 **Modern Interactive Music Player**
- **Persistent Player UI**: Interactive "Now Playing" interface that updates in place for seamless experience
- **Smart Button Controls**: Previous, Play/Pause, and Next buttons with real-time state updates
- **Queue Integration**: Live queue display with current song highlighting (▶️ icon)
- **Intelligent Navigation**: Previous/Next buttons automatically enable/disable based on queue position

### 🎛️ **Advanced Music Management**
- **Multi-Server Support**: Play music in multiple Discord servers simultaneously without interference
- **YouTube and Spotify Integration**: Full support for individual songs, playlists, and albums
- **Smart Queue System**: Advanced queue management with position tracking and seamless navigation
- **Jump to Any Song**: Instantly jump to any song in the queue by number
- **Lazy Loading**: Efficient YouTube URL resolution for faster playlist processing

### 🎮 **Intuitive Controls**
- **Interactive Buttons**: Click-to-control interface for all playback functions
- **Command Flexibility**: Multiple aliases for common commands (`!q`, `!skip`, `!next`, etc.)
- **Smart UI Updates**: Player and queue always appear together at the bottom of chat
- **Error Prevention**: Intelligent button states prevent invalid operations

### 📊 **Management & Monitoring**
- **Web Dashboard**: Flask-based dashboard for real-time statistics and monitoring
- **Admin Controls**: Server-specific settings and permissions
- **Comprehensive Logging**: Detailed error tracking and debugging capabilities
- **Usage Statistics**: Track songs played, queue activity, and user engagement

## 🎯 Commands

### 🎮 **Basic Controls**
| Command | Aliases | Description |
|---|---|---|
| `!join` | | Joins your voice channel |
| `!play <song/URL>` | `!p` | Plays a song, playlist, or album from YouTube/Spotify |
| `!pause` | | Pauses current playback |
| `!resume` | `!start` | Resumes paused playback |
| `!stop` | | Stops playback, clears queue, and disables autoplay |
| `!leave` | `!bye`, `!exit`, `!quit`, `!dc`, `!disconnect`, `!out` | Disconnects bot from voice channel |

### ⏭️ **Navigation & Queue Control**
| Command | Aliases | Description |
|---|---|---|
| `!skip` | `!next` | Skip to next song |
| `!jump <number>` | `!goto`, `!jumpto` | Jump to specific song number in queue |
| `!queue` | `!q` | Display current queue with pagination |
| `!remove <number>` | | Remove song at specified position |
| `!move <from> <to>` | | Move song from one position to another |
| `!shuffle` | | Randomly shuffle the queue |
| `!repeat` | | Toggle repeat for current song |
| `!cleanqueue` | `!cleanup`, `!clean`, `!clear` | Remove invalid/broken songs from the queue |

### 🤖 **AI-Powered Features**
| Command | Aliases | Description |
|---|---|---|
| `!autoplay [on/off]` | `!ap`, `!auto` | **NEW**: Toggle autoplay mode - automatically plays related songs when queue ends |
| `!recommend [count]` | | **NEW**: Get song recommendations based on listening history (1-10 songs) |

### 🔧 **Audio & Search**
| Command | Aliases | Description |
|---|---|---|
| `!volume <0.1-2.0>` | | Set playback volume |
| `!volume <0.1-2.0>` | | Set playback volume |
| `!help` | | Show beautifully formatted help with categories |

### 👑 **Admin-Only Commands**
| Command | Description |
|---|---|
| `!setprefix <prefix>` | Set custom command prefix for server |
| `!setvolume <volume>` | Set default playback volume for server |
| `!stats` | Show song statistics for this server |
| `!forceleave` | Force the bot to leave voice channel and clean up |
| `!clearqueue` | Clear the entire music queue |
| `!resetstats` | Reset server statistics |

### 🔧 **Bot Owner Only Commands**
| Command | Description |
|---|---|
| `!broadcast <message>` | Send a message to all servers |
| `!servers` | List all servers the bot is in |

## 🚀 What's New in Latest Version

### 🤖 **AI-Powered Music Discovery**
- **Autoplay Mode**: `!autoplay` (aliases: `!ap`, `!auto`) - Automatically plays related songs when your queue ends
  - Smart recommendations based on your listening history
  - Instant recommendations when queue is empty
  - Toggle on/off with simple commands
- **Manual Recommendations**: `!recommend [count]` - Get 1-10 song recommendations based on your preferences
  - Personalized suggestions from your listening patterns
  - Add directly to queue with one command
  - Powered by AI learning from your music taste

### 🎵 **Persistent Music Player**
- **Always-visible controls**: Player UI stays consistent across all songs
- **Smart positioning**: Player and queue always appear together at bottom of chat
- **Real-time updates**: No more message spam - everything updates in place

### 🎯 **Enhanced Navigation**
- **Jump Commands**: `!jump 5`, `!goto 3`, `!jumpto 10` - instantly go to any song
- **Smart Button States**: Previous/Next buttons intelligently enable/disable
- **Queue Position Tracking**: See exactly which song is playing with ▶️ indicator

### 🛠️ **Command Improvements**
- **More Aliases**: Added convenient shortcuts for common commands
  - `!resume` now also works as `!start`
  - `!leave` now supports `!bye`, `!exit`, `!quit`, `!dc`, `!disconnect`, `!out`
  - `!cleanqueue` also works as `!cleanup`, `!clean`, `!clear`
- **Queue Maintenance**: New `!cleanqueue` command to remove broken/invalid songs
- **Enhanced Stop**: `!stop` now also disables autoplay and clears queue

### 💎 **Improved User Experience**
- **Error Prevention**: Buttons prevent invalid operations (no "previous" on first song)
- **Visual Feedback**: Clear indication of current song in queue list
- **Organized Help**: New categorized help system with emojis and better formatting
- **Seamless Flow**: No interruption to music experience with UI updates

## 🛠️ Setup and Installation

### Prerequisites

- Python 3.8 or higher
- FFmpeg
- yt-dlp

#### Windows Installation

For Windows users, install `FFmpeg` and `yt-dlp` using `winget`:

```sh
winget install --id=Gyan.FFmpeg -e
winget install --id=yt-dlp.yt-dlp -e
```

#### Other Operating Systems

Please refer to the official documentation for `FFmpeg` and `yt-dlp` installation.

### Bot Setup

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
    cd music-bot
    ```

2.  **Install Python dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

3.  **Create a Discord Bot Application:**
    - Go to the [Discord Developer Portal](https://discord.com/developers/applications)
    - Create a new application and bot
    - Enable the `Message Content Intent` under the "Bot" tab
    - Copy the bot's token

4.  **Create a Spotify Application (Optional):**
    - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
    - Create a new application and get Client ID and Client Secret

5.  **Configure Environment Variables:**
    Create a `.env` file in the project root:

    ```env
    DISCORD_TOKEN=your_discord_bot_token_here

    # Optional for Spotify support
    SPOTIPY_CLIENT_ID=your_spotify_client_id
    SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

    # Required for Dashboard Remote Control
    ADMIN_PIN=your_secret_pin_here  # Min 6 chars
    ```

6.  **Run the Bot:**
    ```sh
    python bot.py
    ```

7.  **Run the Dashboard (optional, in separate terminal):**
    ```sh
    python dashboard.py
    ```
    Dashboard available at `http://127.0.0.1:5000`

## 🔗 Inviting Your Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Navigate to **OAuth2** → **URL Generator**
3. Select `bot` scope
4. Required permissions:
   - **Send Messages**
   - **Embed Links**
   - **Read Message History**
   - **Connect**
   - **Speak**
   - **Use Slash Commands** (for future features)
5. Copy and use the generated URL

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 🚀 Deployment

### 🐳 Docker Deployment (Recommended)

The easiest way to deploy Music Bot is using Docker. This method handles all dependencies automatically and works on any platform.

#### Quick Start

1. **Prerequisites**: Install [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

2. **Clone Repository**:
   ```sh
   git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
   cd Music-DC-bot
   ```

3. **Configure Environment**:
   ```sh
   cp .env.example .env
   # Edit .env and add your DISCORD_TOKEN (required)
   # Optionally add Spotify credentials
   ```

4. **Start Services**:
   ```sh
   docker-compose up -d
   ```

5. **View Logs**:
   ```sh
   docker-compose logs -f bot        # Bot logs
   docker-compose logs -f dashboard  # Dashboard logs
   ```

6. **Access Dashboard**: Open `http://localhost:5000`

#### Docker Commands

| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start services in background |
| `docker-compose down` | Stop and remove containers |
| `docker-compose restart` | Restart services |
| `docker-compose logs -f` | View real-time logs |
| `docker-compose ps` | Check service status |
| `docker-compose pull` | Update images |

#### Persistent Data

Docker volumes automatically store persistent data:
- **logs**: Bot error and info logs
- **stats**: Usage statistics and song data
- **audio_cache**: Temporary audio files

To backup data:
```sh
docker-compose down
docker run --rm -v music-dc-bot_bot-stats:/data -v $(pwd):/backup alpine tar czf /backup/stats-backup.tar.gz -C /data .
```

#### Production Deployment

For production, use a process manager or Docker orchestration:

**Option 1: Docker with Auto-Restart**
```sh
# Already configured in docker-compose.yml
docker-compose up -d  # Services auto-restart on failure
```

**Option 2: Deploy to Cloud with Docker**
- **Railway**: Push to GitHub and deploy
- **DigitalOcean App Platform**: Use Dockerfile
- **AWS ECS/Fargate**: Use provided Dockerfile
- **Google Cloud Run**: Supports Dockerfile deployment

#### Troubleshooting

**Bot won't start**:
```sh
# Check logs for errors
docker-compose logs bot

# Verify environment variables
docker-compose config

# Rebuild if needed
docker-compose build --no-cache
```

**Dashboard controls disabled**:
```sh
# Set ADMIN_PIN in .env
ADMIN_PIN=your_secure_pin
```

**Dashboard not accessible**:
```sh
# Check if port 5000 is available
docker-compose ps

# Try rebuilding
docker-compose up -d --force-recreate dashboard
```

**Audio issues**:
```sh
# Clear audio cache
docker volume rm music-dc-bot_bot-cache
docker-compose up -d
```

---

### Render (Cloud Hosting)


Render offers persistent disk storage on free tier, perfect for maintaining stats and logs.

1. **Create Render Account**: [Render.com](https://render.com/)
2. **Connect GitHub**: Link your repository
3. **Create Web Service**:
   - Repository: Your bot repository
   - Start Command: `gunicorn dashboard:app`
4. **Create Background Worker**:
   - Repository: Same repository
   - Start Command: `python bot.py`
5. **Add Persistent Disk** (for Worker):
   - Mount Path: `/var/data`
   - Update file paths in code accordingly
6. **Set Environment Variables**: Add Discord and Spotify credentials
7. **Deploy**: Both services deploy automatically

### VPS Deployment (Ubuntu/Debian)

1. **Connect to VPS:**
   ```sh
   ssh root@your_server_ip
   ```

2. **Install Dependencies:**
   ```sh
   apt update && apt upgrade -y
   apt install git python3-pip ffmpeg -y
   ```

3. **Clone and Setup:**
   ```sh
   git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
   cd Music-DC-bot
   pip3 install -r requirements.txt
   ```

4. **Configure Environment:**
   ```sh
   nano .env
   # Add your Discord and Spotify credentials
   ```

5. **Create systemd Services:**
   
   **Bot Service** (`/etc/systemd/system/discord-bot.service`):
   ```ini
   [Unit]
   Description=Discord Music Bot
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/Music-DC-bot
   ExecStart=/usr/bin/python3 bot.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   **Dashboard Service** (`/etc/systemd/system/dashboard.service`):
   ```ini
   [Unit]
   Description=Music Bot Dashboard
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/Music-DC-bot
   ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 0.0.0.0:80 dashboard:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

6. **Start Services:**
   ```sh
   systemctl enable discord-bot dashboard
   systemctl start discord-bot dashboard
   ```

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 🎵 Enjoy Your Music!

Music Bot provides a premium Discord music experience with modern UI, intelligent controls, and seamless playback. Perfect for communities that love music! 🎶 