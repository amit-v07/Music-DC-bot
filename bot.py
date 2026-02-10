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


class MusicBot(commands.Bot):
    """Enhanced Discord bot with improved architecture"""
    
    def __init__(self):
        # Use fixed prefix since we no longer have database settings
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True  # For voice state monitoring
        
        super().__init__(
            command_prefix=config.default_prefix,
            intents=intents,
            help_command=None  # We'll create our own help command
        )
        
        # Store startup time
        self.startup_time = None
    
    async def setup_hook(self):
        """Initialize bot components"""
        logger.info("Starting bot setup...")
        
        try:
            # Load all command cogs
            await self.load_extension('commands.music')
            await self.load_extension('commands.admin')
            
            logger.info("All command modules loaded successfully")
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error("setup_hook", e)
            raise
    
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
            logger.warning("Opus library is NOT loaded! Voice features may fail.")
            try:
                # Try to find library using ctypes
                import ctypes.util
                opus_path = ctypes.util.find_library('opus')
                
                if opus_path:
                    logger.info(f"Found Opus library at: {opus_path}")
                    discord.opus.load_opus(opus_path)
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
                        logger.error("Could not load Opus library. Voice will not work.")
            
            except Exception as e:
                logger.error("opus_load_error", e)
        else:
            logger.info("Opus library is successfully loaded")
        
        # One-time broadcast for new feature
        import os
        if not os.path.exists("broadcast_done.flag"):
            logger.info("Starting one-time broadcast...")
            message = (
                "📢 **Hiii Friends!** 👋\n\n"
                "Main wapas aa gayi hoon ek naye dhamakedaar update ke saath! 💃\n"
                "Music ab non-stop chalega kyunki maine **Autoplay Mode** seekh liya hai! 🔥\n\n"
                "Jab queue khatam hogi, main khud hi mast gaane bajaungi. Boriyat ka the end! 😎\n\n"
                "**Try karo:** `!autoplay on`\n\n"
                "Enjoy karo guys! 🎵✨"
            )
            
            count = 0
            for guild in self.guilds:
                try:
                    target = guild.system_channel
                    if not target:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                target = channel
                                break
                    
                    if target:
                        await target.send(message)
                        count += 1
                        logger.info(f"Broadcast sent to {guild.name}")
                        # Small delay to avoid rate limits
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Broadcast failed for {guild.name}: {e}")
            
            logger.info(f"Broadcast completed. Sent to {count} servers.")
            
            # Create flag file
            with open("broadcast_done.flag", "w") as f:
                f.write("done")
    
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
            await ctx.send(f"⏱️ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
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
            "`play <song/URL>` (alias: `p`) — Play music\n"
            "`pause` — Pause current song\n"
            "`resume` — Resume playback\n"
            "`stop` — Stop and clear queue\n"
            "`leave` — Leave voice channel\n"
            "`nowplaying` — Show current song with controls"
        ),
        inline=False
    )
    
    # Navigation & Queue
    embed.add_field(
        name="⏭️ **Navigation & Queue**",
        value=(
            "`skip` (alias: `next`) — Skip current song\n"
            "`jump <number>` — Jump to specific song\n"
            "`queue` (alias: `q`) — Show current queue\n"
            "`shuffle` — Shuffle the queue\n"
            "`repeat` — Toggle repeat current song\n"
            "`remove <number>` — Remove song from queue\n"
            "`move <from> <to>` — Move song position\n"
            "`clear` (aliases: `cleanup`, `clean`) — Clear entire queue"
        ),
        inline=False
    )
    
    # Smart Features
    embed.add_field(
        name="🤖 **Smart Features**",
        value=(
            "`autoplay [on/off]` (aliases: `ap`, `auto`) — Auto-add songs when queue ends\n"
            "`volume <0.1-2.0>` — Set playback volume\n"
            "`stats` — Show server music statistics"
        ),
        inline=False
    )
    
    # Admin Commands
    embed.add_field(
        name="🔧 **Admin Commands**",
        value=(
            "`forceleave` — Force disconnect bot\n"
            "`broadcast <message>` — Send message to all servers\n"
            "`servers` — List all connected servers\n"
            "`resetstats` — Reset server statistics"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 **Tips**",
        value=(
            f"• Use `{config.default_prefix}` as the command prefix\n"
            "• Click the buttons on the player for quick controls\n"
            "• Supports YouTube links, playlists, and Spotify URLs\n"
            "• Auto-leave if alone for 1 minute\n"
            "• Queue supports hundreds of songs!\n"
            "• AI-powered Hinglish responses! 🎉"
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
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("main_execution", e)
        print(f"Fatal error: {e}") 