"""
Music Bot
A feature-rich Discord music bot with modular architecture
"""
import asyncio
import discord
from discord.ext import commands
from config import config
from utils.logger import logger
from audio.manager import audio_manager
from utils.stats_manager import stats_manager

# ---------------------------------------------------------------------------
# Per-guild prefix cache  (Change 8)
# Guild ID -> prefix string.  Populated at startup and on !setprefix.
# ---------------------------------------------------------------------------
_prefix_cache: dict[int, str] = {}


async def get_prefix(bot, message):
    """
    Dynamic prefix resolver used as command_prefix= callable.
    Priority: in-memory cache → SQLite → config.default_prefix.
    Always also accepts a @mention so `@Bot help` works on every server.
    """
    # DMs always use the default prefix
    if not message.guild:
        prefix = config.default_prefix
    else:
        guild_id = message.guild.id
        if guild_id in _prefix_cache:
            prefix = _prefix_cache[guild_id]
        else:
            # Cold-cache miss — read from DB
            try:
                from utils import db
                prefix = await db.get_prefix(guild_id)
            except Exception as e:
                logger.warning(f"get_prefix DB error for guild {guild_id}: {e}")
                prefix = config.default_prefix
            _prefix_cache[guild_id] = prefix

    return [
        prefix,
        f'<@{bot.user.id}> ',
        f'<@!{bot.user.id}> ',
    ]


class MusicBot(commands.Bot):
    """Enhanced Discord bot with improved architecture"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True  # For voice state monitoring
        
        super().__init__(
            command_prefix=get_prefix,  # Dynamic per-guild prefix (Change 8)
            intents=intents,
            help_command=None  # We'll create our own help command
        )
        
        # Store startup time
        self.startup_time = None
        self.bg_task = None
    
    async def setup_hook(self):
        """Initialize bot components"""
        logger.info("Starting bot setup...")
        
        try:
            # Initialise SQLite DB and run JSON migration (Change 5)
            await stats_manager.init()
            
            # Preload all guild prefixes into the in-memory cache (Change 8)
            try:
                from utils import db
                stored_prefixes = await db.get_all_prefixes()
                _prefix_cache.update(stored_prefixes)
                logger.info(f"Preloaded {len(stored_prefixes)} guild prefix(es) into cache")
            except Exception as e:
                logger.warning(f"Could not preload prefixes: {e}")
            
            # Load all command cogs
            await self.load_extension('commands.music')
            await self.load_extension('commands.admin')
            
            # Set bot instance in stats_manager so it can access all guilds
            stats_manager.set_bot(self)
            
            # Start background task for remote control actions
            self.bg_task = self.loop.create_task(self.process_remote_actions())
            
            # Start periodic cache cleanup task
            self.cache_cleanup_task = self.loop.create_task(self.periodic_cache_cleanup())
            
            # Start periodic resource cleanup task
            self.resource_cleanup_task = self.loop.create_task(self.periodic_resource_cleanup())
            
            logger.info("All command modules loaded successfully")
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error("setup_hook", e)
            raise
    
    async def periodic_cache_cleanup(self):
        """Periodic task to clean up expired cache entries"""
        await self.wait_until_ready()
        logger.info("Cache cleanup task started")
        
        while not self.is_closed():
            try:
                # Clean up song cache
                try:
                    from audio.cache import song_cache
                    await song_cache.cleanup_expired()
                    stats = song_cache.get_stats()
                    logger.info(f"Cache cleanup completed. Stats: {stats}")
                except ImportError:
                    pass
                except Exception as e:
                    logger.error("cache_cleanup", e)
                
                # Wait 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("Cache cleanup task cancelled")
                break
            except Exception as e:
                logger.error("periodic_cache_cleanup", e)
                await asyncio.sleep(600)

    async def periodic_resource_cleanup(self):
        """Periodic task to clean up stale timers and monitor memory"""
        await self.wait_until_ready()
        logger.info("Resource cleanup task started")
        
        import psutil
        import os
        
        while not self.is_closed():
            try:
                # 1. Clean up stale timers
                active_guilds = set(g.id for g in self.guilds)
                
                # Snapshot keys to avoid runtime errors during iteration
                for guild_id in list(audio_manager.alone_timers.keys()):
                    if guild_id not in active_guilds:
                        audio_manager.cancel_alone_timer(guild_id)
                        
                for guild_id in list(audio_manager.idle_timers.keys()):
                    if guild_id not in active_guilds:
                        audio_manager.cancel_idle_timer(guild_id)

                # 2. Memory Monitoring
                process = psutil.Process(os.getpid())
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                
                logger.info(f"Resource Check: Memory: {memory_usage:.2f} MB | Guilds: {len(self.guilds)}")
                
                # 3. Aggressive GC if memory is too high
                if memory_usage > config.max_memory_mb:
                    import gc
                    gc.collect()
                    logger.warning(f"High memory usage detected ({memory_usage:.2f} MB > {config.max_memory_mb} MB). Forcing GC.")
                
                # Run periodically based on config
                await asyncio.sleep(config.resource_cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("resource_cleanup", e)
                await asyncio.sleep(60)
    
    async def process_remote_actions(self):
        """Background task to process remote control actions from dashboard"""
        await self.wait_until_ready()
        logger.info("Remote control action processor started")
        
        while not self.is_closed():
            try:
                actions = await stats_manager.get_pending_actions()
                
                for action in actions:
                    guild_id = int(action['guild_id'])
                    cmd = action['action']
                    
                    guild = self.get_guild(guild_id)
                    if not guild or not guild.voice_client:
                        continue
                        
                    vc = guild.voice_client
                    
                    if cmd == 'pause':
                        if vc.is_playing():
                            vc.pause()
                            logger.info(f"Remote action: Paused in {guild.name}")
                    elif cmd == 'resume':
                        if vc.is_paused():
                            vc.resume()
                            logger.info(f"Remote action: Resumed in {guild.name}")
                    elif cmd == 'skip':
                        if vc.is_playing() or vc.is_paused():
                            vc.stop()
                            logger.info(f"Remote action: Skipped in {guild.name}")
                    elif cmd == 'stop':
                        # Use audio_manager to clean up properly
                        audio_manager.clear_queue(guild_id)
                        audio_manager.disable_autoplay(guild_id)
                        if vc.is_playing() or vc.is_paused():
                            vc.stop()
                        logger.info(f"Remote action: Stopped in {guild.name}")
                
                await asyncio.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                logger.error("process_remote_actions", e)
                await asyncio.sleep(5)

    async def on_command_completion(self, ctx):
        """Record successful command usage"""
        if ctx.guild:
            await stats_manager.record_command_usage(ctx.guild.id, ctx.command.name)

    async def on_ready(self):
        """Bot ready event"""
        self.startup_time = discord.utils.utcnow()
        
        logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info(f"Serving {sum(guild.member_count for guild in self.guilds)} users")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"music in {len(self.guilds)} servers | {config.default_prefix}help"
        )
        await self.change_presence(activity=activity)
        
        # Check for Opus library (critical for voice)
        if not discord.opus.is_loaded():
            logger.info("Opus not pre-loaded, attempting to find and load...")
            try:
                # Try to find library using ctypes
                import ctypes.util
                opus_path = ctypes.util.find_library('opus')
                
                if opus_path:
                    discord.opus.load_opus(opus_path)
                    logger.info(f"Successfully loaded Opus from: {opus_path}")
                else:
                    # Fallback for specific Linux architectures (including the user's aarch64)
                    possible_paths = [
                        "libopus.so.0",
                        "libopus.so",
                        "/usr/lib/aarch64-linux-gnu/libopus.so.0",
                        "/usr/lib/x86_64-linux-gnu/libopus.so.0"
                    ]
                    
                    loaded = False
                    for path in possible_paths:
                        try:
                            discord.opus.load_opus(path)
                            logger.info(f"Successfully loaded Opus from: {path}")
                            loaded = True
                            break
                        except Exception:
                            continue
                    
                    if not loaded:
                        logger.error("Could not load Opus library. Voice will NOT work!")
            
            except Exception as e:
                logger.error("opus_load_error", e)
        else:
            logger.info("Opus library is successfully loaded")
        


    
    async def on_guild_join(self, guild):
        """Handle bot joining a new guild"""
        logger.info(f"Joined new guild: {guild.name} ({guild.id}) with {guild.member_count} members")
        
        # Find a channel to send welcome message
        welcome_channel = None
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            welcome_channel = guild.system_channel
        else:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    welcome_channel = channel
                    break
        
        if welcome_channel:
            embed = discord.Embed(
                title="🎵 Thanks for adding Music Bot!",
                description=(
                    f"I'm ready to play music in **{guild.name}**!\n\n"
                    f"🎮 **Get started:** `{config.default_prefix}play <song name>`\n"
                    f"📋 **See all commands:** `{config.default_prefix}help`\n\n"
                    "🎵 **Features:**\n"
                    "• YouTube & Spotify support\n"
                    "• Interactive player controls\n"
                    "• Queue management\n"
                    "• High-quality audio\n"
                    "• Multi-server support"
                ),
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.user.display_avatar.url)
            try:
                await welcome_channel.send(embed=embed)
            except Exception as e:
                logger.error("guild_join_welcome", e, guild_id=guild.id)
    
    async def on_guild_remove(self, guild):
        """Handle bot leaving a guild"""
        logger.info(f"Left guild: {guild.name} ({guild.id})")
        
        # Evict from prefix cache (Change 8)
        _prefix_cache.pop(guild.id, None)
        
        # Clean up guild data
        try:
            audio_manager.clear_queue(guild.id)
            audio_manager.cancel_alone_timer(guild.id)
            
        except Exception as e:
            logger.error("guild_leave_cleanup", e, guild_id=guild.id)
    
    async def on_voice_state_update(self, member, before, after):
        """Monitor voice channel changes for auto-leave functionality"""
        try:
            guild = member.guild
            
            # Check if the BOT was disconnected
            if member.id == self.user.id:
                if before.channel is not None and after.channel is None:
                    logger.info(f"Bot was disconnected from guild {guild.name}")
                    audio_manager.clear_queue(guild.id)
                    audio_manager.disable_autoplay(guild.id)
                    audio_manager.cancel_alone_timer(guild.id)
                    return

            # Only process if bot is in a voice channel
            if not guild.voice_client or not guild.voice_client.channel:
                return
            
            bot_channel = guild.voice_client.channel
            
            # Check if the change affects the bot's channel
            member_was_in_bot_channel = before.channel == bot_channel
            member_is_in_bot_channel = after.channel == bot_channel
            
            if member_was_in_bot_channel or member_is_in_bot_channel:
                # Someone joined or left the bot's channel
                if audio_manager.is_bot_alone_in_vc(guild):
                    # Bot is now alone, start timer
                    await audio_manager.start_alone_timer(guild)
                else:
                    # Bot is not alone, cancel any existing timer
                    audio_manager.cancel_alone_timer(guild.id)
                    
        except Exception as e:
            logger.error("voice_state_update", e, guild_id=member.guild.id)
    
    async def on_command_error(self, ctx, error):
        """Global command error handler"""
        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Handle cooldown errors
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏱️ Slow down! Try again in {error.retry_after:.1f}s")
            return
        
        # Handle missing permissions
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
            return
        
        # Handle bot missing permissions
        if isinstance(error, commands.BotMissingPermissions):
            missing_perms = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ I need the following permissions: {missing_perms}")
            return
        
        # Handle other command errors
        if isinstance(error, commands.CommandError):
            await ctx.send(f"❌ Command error: {str(error)}")
            logger.error("command_error", error, guild_id=ctx.guild.id if ctx.guild else None)
            return
        
        # Log unexpected errors
        logger.error("unexpected_command_error", error, guild_id=ctx.guild.id if ctx.guild else None)
        await ctx.send("❌ An unexpected error occurred. The error has been logged.")
    
    async def close(self):
        """Clean shutdown of the bot"""
        logger.info("Bot is shutting down...")
        
        try:
            # Clean up all voice connections
            for guild in self.guilds:
                if guild.voice_client:
                    audio_manager.clear_queue(guild.id)
                    audio_manager.cancel_alone_timer(guild.id)
                    await guild.voice_client.disconnect()
            
            logger.info("Bot shutdown completed")
            
        except Exception as e:
            logger.error("bot_shutdown", e)
        
        await super().close()


# Help command implementation
@commands.command(name='help')
async def help_command(ctx):
    """Enhanced help command with beautiful formatting"""
    # Determine the current guild's actual prefix
    if ctx.guild:
        from bot import _prefix_cache
        prefix = _prefix_cache.get(ctx.guild.id, config.default_prefix)
    else:
        prefix = config.default_prefix
    
    embed = discord.Embed(
        title="🎵 Music Bot Commands",
        description="Complete guide to all available commands",
        color=0x9B59B6  # Modern purple theme
    )
    
    # Basic Controls
    embed.add_field(
        name="🎮 **Basic Controls**",
        value=(
            "`join` — Join your voice channel\n"
            f"`play <song/URL>` (alias: `p`) — Play music\n"
            "`pause` — Pause current song\n"
            f"`resume` (alias: `start`) — Resume playback\n"
            "`stop` — Stop, clear queue & disable autoplay\n"
            f"`leave` (aliases: `bye`, `exit`, `quit`, `dc`, `disconnect`, `out`) — Leave voice channel"
        ),
        inline=False
    )
    
    # Navigation & Queue
    embed.add_field(
        name="⏭️ **Navigation & Queue**",
        value=(
            "`skip` (alias: `next`) — Skip current song\n"
            "`jump <number>` (aliases: `goto`, `jumpto`) — Jump to specific song\n"
            "`queue` (alias: `q`) — Show current queue\n"
            "`shuffle` — Shuffle the queue\n"
            "`repeat` — Toggle repeat current song\n"
            "`remove <number>` — Remove song from queue\n"
            "`move <from> <to>` — Move song position\n"
            "`cleanqueue` (aliases: `cleanup`, `clean`, `clear`) — Remove invalid songs"
        ),
        inline=False
    )
    
    # AI-Powered Features
    embed.add_field(
        name="🤖 **AI-Powered Features**",
        value=(
            "`autoplay [on/off]` (aliases: `ap`, `auto`) — **NEW!** Auto-plays related songs when queue ends\n"
            "`recommend [count]` — **NEW!** Get 1-10 song recommendations based on your listening history"
        ),
        inline=False
    )
    
    # Audio & Other
    embed.add_field(
        name="🔧 **Audio & Other**",
        value=(
            "`volume <0.1-2.0>` — Set playback volume\n"
            "`nowplaying` — Show current song with controls\n"
            "`stats` — Show server listening statistics"
        ),
        inline=False
    )
    
    # Admin Commands
    embed.add_field(
        name="👑 **Admin Commands**",
        value=(
            f"`setprefix <prefix>` — Change the bot prefix for this server\n"
            f"`quality <low|medium|high>` — Toggle audio quality bitrate\n"
            "`clearqueue` — Clear the entire queue\n"
            "`resetstats` — Reset server listening statistics"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 **Tips**",
        value=(
            f"• Your prefix for this server: `{prefix}`\n"
            "• Click the buttons on the player for quick controls\n"
            "• Supports YouTube links, playlists, and Spotify URLs\n"
            "• Auto-leave if alone for 1 minute\n"
            "• Queue supports hundreds of songs!\n"
            "• Try autoplay mode for endless music! 🎉"
        ),
        inline=False
    )
    
    embed.set_footer(
        text=f"Music Bot 2026 Edition | In {len(ctx.bot.guilds)} servers",
        icon_url=ctx.bot.user.display_avatar.url
    )
    
    await ctx.send(embed=embed)


async def main():
    """Main bot startup function"""
    try:
        # Create bot instance
        bot = MusicBot()
        
        # Add the help command
        bot.add_command(help_command)
        
        # Start the bot
        logger.info("Starting Music Bot...")
        await bot.start(config.discord_token)
        
    except Exception as e:
        logger.error("bot_startup", e)
        raise


if __name__ == "__main__":
    try:
        # Activate uvloop for better event loop performance on Linux/macOS
        # Falls back gracefully on Windows (development machines)
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("uvloop event loop policy activated")
        except ImportError:
            logger.info("uvloop not available, using default asyncio event loop")
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("main_execution", e)
        print(f"Fatal error: {e}") 