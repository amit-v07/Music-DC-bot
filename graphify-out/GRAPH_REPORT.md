# Graph Report - .  (2026-04-18)

## Corpus Check
- Corpus is ~26,824 words - fits in a single context window. You may not need a graph.

## Summary
- 600 nodes · 1302 edges · 30 communities detected
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 581 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Admin broadcast and moderation|Admin broadcast and moderation]]
- [[_COMMUNITY_Dashboard remote control and rate limits|Dashboard remote control and rate limits]]
- [[_COMMUNITY_Guild lifecycle and voice monitoring|Guild lifecycle and voice monitoring]]
- [[_COMMUNITY_Discord UI views and controls|Discord UI views and controls]]
- [[_COMMUNITY_Circuit breaker and playback core|Circuit breaker and playback core]]
- [[_COMMUNITY_Docs, Docker, and AI persona|Docs, Docker, and AI persona]]
- [[_COMMUNITY_MusicBot core and entrypoint|MusicBot core and entrypoint]]
- [[_COMMUNITY_Gemini AI brain|Gemini AI brain]]
- [[_COMMUNITY_Stream URL cache|Stream URL cache]]
- [[_COMMUNITY_YouTube Music recommendations|YouTube Music recommendations]]
- [[_COMMUNITY_Standalone web HTTP API|Standalone web HTTP API]]
- [[_COMMUNITY_Listening history store|Listening history store]]
- [[_COMMUNITY_Flask dashboard realtime|Flask dashboard realtime]]
- [[_COMMUNITY_Package exports wiring|Package exports wiring]]
- [[_COMMUNITY_Web player JavaScript|Web player JavaScript]]
- [[_COMMUNITY_BotConfig and env loading|BotConfig and env loading]]
- [[_COMMUNITY_Admin cog and owner checks|Admin cog and owner checks]]
- [[_COMMUNITY_Landing page favicon brand|Landing page favicon brand]]
- [[_COMMUNITY_Dashboard favicon brand|Dashboard favicon brand]]
- [[_COMMUNITY_Admin prefix command|Admin prefix command]]
- [[_COMMUNITY_Admin audio quality command|Admin audio quality command]]
- [[_COMMUNITY_Admin default volume command|Admin default volume command]]
- [[_COMMUNITY_Per-server song statistics|Per-server song statistics]]
- [[_COMMUNITY_Force leave voice cleanup|Force leave voice cleanup]]
- [[_COMMUNITY_Clear music queue|Clear music queue]]
- [[_COMMUNITY_Owner multi-server broadcast|Owner multi-server broadcast]]
- [[_COMMUNITY_Owner guild listing|Owner guild listing]]
- [[_COMMUNITY_Reset server statistics|Reset server statistics]]
- [[_COMMUNITY_User playback volume|User playback volume]]
- [[_COMMUNITY_yt-dlp integration test|yt-dlp integration test]]

## God Nodes (most connected - your core abstractions)
1. `AudioManager` - 43 edges
2. `Song` - 42 edges
3. `CircuitBreakerOpen` - 32 edges
4. `log_command_usage()` - 29 edges
5. `log_audio_event()` - 26 edges
6. `play_current_song()` - 22 edges
7. `handle_song_end()` - 19 edges
8. `play()` - 17 edges
9. `MusicBot` - 15 edges
10. `YouTubeMusicRecommendationEngine` - 15 edges

## Surprising Connections (you probably didn't know these)
- `run_dashboard()` --calls--> `init_db()`  [INFERRED]
  dashboard.py → utils\db.py
- `_extract_video_id()` --calls--> `search()`  [INFERRED]
  audio\cache.py → music_web_app\services\audio_provider.py
- `Utility modules for Music Bot` --uses--> `Song`  [INFERRED]
  utils\__init__.py → audio\manager.py
- `MusicCog` --uses--> `Song`  [INFERRED]
  commands\music.py → audio\manager.py
- `Join the user's voice channel` --uses--> `Song`  [INFERRED]
  commands\music.py → audio\manager.py

## Hyperedges (group relationships)
- **Single favicon composition: gradient disc plus white note glyph defines Music Bot visual identity** — static_favicon_svg, static_favicon_gradient_circle, static_favicon_music_glyph [EXTRACTED 1.00]
- **h_discord_playback_pipeline** —  [INFERRED 0.94]
- **h_discord_autoplay_chain** —  [INFERRED 0.93]
- **h_dashboard_bot_remote_control** —  [INFERRED 0.90]
- **h_web_streaming_stack** —  [INFERRED 0.93]
- **h_web_client_autoplay** —  [INFERRED 0.91]
- **h_manual_test_coverage** —  [INFERRED 0.88]
- **Logging and analytics hooks: logger helpers + DB/stats recording + UI error paths** —  [EXTRACTED]
- **Protecting YouTube/yt-dlp path from overload: breaker + pooled extractions + rate limits** —  [EXTRACTED]
- **Persistent state: SQLite authoritative for stats/settings/history rows; JSON files for autoplay recent tracks + dashboard action queue; legal docs omit SQLite** —  [EXTRACTED]
- **Optional cloud LLM persona layered on bot UX; depends on API key and google-genai** —  [EXTRACTED]
- **Operations story: Docker guide + dashboard port + landing invite funnel** —  [EXTRACTED]

## Communities

### Community 0 - "Admin broadcast and moderation"
Cohesion: 0.05
Nodes (66): broadcast(), broadcast_error(), clearqueue_error(), forceleave(), forceleave_error(), quality(), Admin commands for Music Bot Server administration and configuration commands, resetstats() (+58 more)

### Community 1 - "Dashboard remote control and rate limits"
Cohesion: 0.07
Nodes (46): clearqueue(), Generate a response based on an action and context.                  Args:, Background task to process remote control actions from dashboard, Check if user is within rate limit                  Args:             user_id, log_audio_event(), log_command_usage(), Log audio-related events, Log warning message with optional context (+38 more)

### Community 2 - "Guild lifecycle and voice monitoring"
Cohesion: 0.04
Nodes (33): Periodic task to clean up stale timers and monitor memory, Handle bot leaving a guild, Monitor voice channel changes for auto-leave functionality, Record when a song is played (non-blocking)                  Args:             g, Log info message with optional context, AudioManager, Get currently playing song, Remove song at index from queue (+25 more)

### Community 3 - "Discord UI views and controls"
Cohesion: 0.08
Nodes (21): Format duration as MM:SS or HH:MM:SS, Check if autoplay is enabled for a guild, Check if autoplay is enabled for a guild, NowPlayingView, QueueView, Interactive controls for currently playing song, Handle repeat toggle button, Handle autoplay toggle button (+13 more)

### Community 4 - "Circuit breaker and playback core"
Cohesion: 0.08
Nodes (31): CircuitBreaker, CircuitBreakerOpen, Exception raised when circuit breaker is open, Exception, Enhanced song data structure, Song, Music commands for Music Bot Handles all music-related commands and playback, Handle what happens when a song ends (+23 more)

### Community 5 - "Docs, Docker, and AI persona"
Cohesion: 0.07
Nodes (23): AI Brain Module for Music Bot Uses Google GenAI SDK (new unified SDK) for dynam, Docker/Compose deployment: prerequisites, .env (DISCORD_TOKEN required; Spotify optional), volumes bot-logs/bot-stats/bot-cache, dashboard on :5000, resource limits, backup/restore, troubleshooting (FFmpeg, yt-dlp, DNS)., Utility modules for Music Bot, Landing page docs: static HTML/CSS marketing site; deploy via GitHub Pages/Vercel/Netlify/local; customization (gradients, bot name, OAuth invite URL); optional GA; UTM on invite links; support links., robots.txt: Allow all user-agents; sitemap URL points to Netlify-hosted sitemap., Listening History Manager for Music Bot Tracks recently played songs per server, BotLogger, log_error_with_context() (+15 more)

### Community 6 - "MusicBot core and entrypoint"
Cohesion: 0.06
Nodes (20): get_prefix(), help_command(), main(), MusicBot, Music Bot A feature-rich Discord music bot with modular architecture, Periodic task to clean up expired cache entries, Dynamic prefix resolver used as command_prefix= callable.     Priority: in-memor, Record successful command usage (+12 more)

### Community 7 - "Gemini AI brain"
Cohesion: 0.09
Nodes (24): AIBrain, Handles AI text generation for the bot, Constructs the prompt for the AI, Fallback static responses if AI fails, autoplay(), The core streaming endpoint.     1. Gets current song from Queue.     2. Resol, stream_audio(), AudioProvider (+16 more)

### Community 8 - "Stream URL cache"
Cohesion: 0.09
Nodes (18): _extract_video_id(), Song resolution cache for Music Bot Uses cachetools TTLCache (maxsize=200, TTL=4, Synchronous get-or-populate helper, safe to call from a         ThreadPoolExecut, Extract YouTube video ID if present, otherwise normalise key., Thread-safe LRU+TTL cache for yt-dlp stream URL resolutions.      * maxsize=200, Cache resolved song data., Return cache statistics., SongCache (+10 more)

### Community 9 - "YouTube Music recommendations"
Cohesion: 0.09
Nodes (18): YouTube Music Recommendation Service for Music Bot Uses ytmusicapi for high-qua, Fetch recommendations using YouTube Music API, Fallback: Fetch recommendations using yt-dlp search, Recommended song data structure, Check if recommendations are cached and valid, Fetches music recommendations using YouTube Music API, Move item to end of cache (LRU implementation), Remove item from cache (+10 more)

### Community 10 - "Standalone web HTTP API"
Cohesion: 0.12
Nodes (7): add_to_queue(), control(), home(), jump_queue(), search(), QueueManager, TestQueueLogic

### Community 11 - "Listening history store"
Cohesion: 0.12
Nodes (12): HistoryEntry, ListeningHistoryManager, Get the last video URL that was played (for recommendations)                  Ar, Clear all history for a guild, Load history from JSON file, Save history to JSON file (synchronous), Load history from JSON file without blocking the event loop, Save history to JSON file without blocking the event loop (+4 more)

### Community 12 - "Flask dashboard realtime"
Cohesion: 0.13
Nodes (17): background_stats_push(), check_auth(), _fetch_stats(), get_stats(), health_check(), Flask-SocketIO dashboard for Music Bot. Runs in a SEPARATE container with gevent, Lightweight health endpoint (checked by docker-compose healthcheck)., Detailed system resource snapshot. (+9 more)

### Community 13 - "Package exports wiring"
Cohesion: 0.17
Nodes (20): audio package export, SongCache, AudioManager, YouTube recommendation engine, Discord bot process, commands package, AdminCog, MusicCog + playback orchestration (+12 more)

### Community 14 - "Web player JavaScript"
Cohesion: 0.21
Nodes (14): addToQueue(), fetchAutoplay(), fetchHomeData(), fetchQueueState(), formatTime(), handleAutoplay(), jumpToQueue(), loadStream() (+6 more)

### Community 15 - "BotConfig and env loading"
Cohesion: 0.29
Nodes (6): BotConfig, load_config(), Configuration management for Music Bot, Main bot configuration, Load configuration from environment variables, Initialize default options after dataclass creation

### Community 16 - "Admin cog and owner checks"
Cohesion: 0.25
Nodes (5): AdminCog, Admin commands for bot management, Global check for admin cog commands, Custom check for bot owner, setup()

### Community 17 - "Landing page favicon brand"
Cohesion: 1.0
Nodes (3): Brand background: circle filled with linearGradient grad1 (#FF0080 → #7928CA), Foreground mark: white path forming a stylized beamed eighth-note shape, Landing-page favicon (512×512 SVG): circular badge with magenta-to-violet gradient and a white music-note glyph

### Community 18 - "Dashboard favicon brand"
Cohesion: 1.0
Nodes (3): Brand backdrop: circle (r=240) filled with linearGradient grad1 from #FF0080 to #7928CA (hot pink → purple), Foreground mark: white filled path suggesting a beamed eighth-note shape, contrasting on the gradient for legibility at small sizes, Music Bot favicon (512×512 SVG): circular badge with magenta-to-violet linear gradient and a white stylized music-note glyph for browser/app branding

### Community 19 - "Admin prefix command"
Cohesion: 1.0
Nodes (1): Set a custom command prefix for this server (Admin only)

### Community 20 - "Admin audio quality command"
Cohesion: 1.0
Nodes (1): Set audio quality for this server: low / medium / high (Admin only)

### Community 21 - "Admin default volume command"
Cohesion: 1.0
Nodes (1): Set the default volume for this server (session only)

### Community 22 - "Per-server song statistics"
Cohesion: 1.0
Nodes (1): Show song statistics for this server

### Community 23 - "Force leave voice cleanup"
Cohesion: 1.0
Nodes (1): Force the bot to leave voice channel and clean up

### Community 24 - "Clear music queue"
Cohesion: 1.0
Nodes (1): Clear the entire music queue

### Community 25 - "Owner multi-server broadcast"
Cohesion: 1.0
Nodes (1): Send a message to all servers (Bot Owner only)         Usage: !broadcast [optio

### Community 26 - "Owner guild listing"
Cohesion: 1.0
Nodes (1): List all servers the bot is in (Bot Owner only)

### Community 27 - "Reset server statistics"
Cohesion: 1.0
Nodes (1): Reset server statistics (Admin only)

### Community 28 - "User playback volume"
Cohesion: 1.0
Nodes (1): Set the playback volume (0.1 - 2.0)

### Community 29 - "yt-dlp integration test"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **195 isolated node(s):** `Music Bot A feature-rich Discord music bot with modular architecture`, `Dynamic prefix resolver used as command_prefix= callable.     Priority: in-memor`, `Enhanced Discord bot with improved architecture`, `Initialize bot components`, `Periodic task to clean up expired cache entries` (+190 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Admin prefix command`** (1 nodes): `Set a custom command prefix for this server (Admin only)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Admin audio quality command`** (1 nodes): `Set audio quality for this server: low / medium / high (Admin only)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Admin default volume command`** (1 nodes): `Set the default volume for this server (session only)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Per-server song statistics`** (1 nodes): `Show song statistics for this server`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Force leave voice cleanup`** (1 nodes): `Force the bot to leave voice channel and clean up`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Clear music queue`** (1 nodes): `Clear the entire music queue`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Owner multi-server broadcast`** (1 nodes): `Send a message to all servers (Bot Owner only)         Usage: !broadcast [optio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Owner guild listing`** (1 nodes): `List all servers the bot is in (Bot Owner only)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Reset server statistics`** (1 nodes): `Reset server statistics (Admin only)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `User playback volume`** (1 nodes): `Set the playback volume (0.1 - 2.0)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `yt-dlp integration test`** (1 nodes): `test_ytdlp.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AudioManager` connect `Guild lifecycle and voice monitoring` to `Dashboard remote control and rate limits`, `Discord UI views and controls`, `Circuit breaker and playback core`, `Docs, Docker, and AI persona`, `Stream URL cache`, `Standalone web HTTP API`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `Song` connect `Circuit breaker and playback core` to `Dashboard remote control and rate limits`, `Guild lifecycle and voice monitoring`, `Discord UI views and controls`, `Docs, Docker, and AI persona`, `Stream URL cache`, `Standalone web HTTP API`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `stream_audio()` connect `Gemini AI brain` to `Standalone web HTTP API`, `Guild lifecycle and voice monitoring`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `AudioManager` (e.g. with `Utility modules for Music Bot` and `TestCircuitBreaker`) actually correct?**
  _`AudioManager` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Song` (e.g. with `Utility modules for Music Bot` and `MusicCog`) actually correct?**
  _`Song` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `CircuitBreakerOpen` (e.g. with `MusicCog` and `Music commands for Music Bot Handles all music-related commands and playback`) actually correct?**
  _`CircuitBreakerOpen` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `log_command_usage()` (e.g. with `setprefix()` and `quality()`) actually correct?**
  _`log_command_usage()` has 26 INFERRED edges - model-reasoned connections that need verification._