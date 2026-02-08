"""
Admin commands for Music Bot
Server administration and configuration commands
"""
import discord
from discord.ext import commands
from config import config
from utils.logger import logger, log_command_usage
from utils.stats_manager import stats_manager
from audio.manager import audio_manager


class AdminCog(commands.Cog):
    """Admin commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx, prefix: str):
        """Set the command prefix for this server (session only)"""
        log_command_usage(ctx, "setprefix", prefix)
        
        await ctx.send(f"ℹ️ **Note:** This bot now uses a fixed prefix: `{config.default_prefix}`\n"
                      "Custom prefixes are no longer supported for simplicity.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setvolume(self, ctx, volume: float):
        """Set the default volume for this server (session only)"""
        log_command_usage(ctx, "setvolume", str(volume))
        
        if not (0.1 <= volume <= 2.0):
            await ctx.send("❌ Volume must be between 0.1 and 2.0!")
            return
        
        try:
            audio_manager.set_volume(ctx.guild.id, volume)
            
            # Apply to current source if playing
            if ctx.voice_client and ctx.voice_client.source:
                ctx.voice_client.source.volume = volume
            
            await ctx.send(f"✅ Default volume set to: **{volume}** (session only)\n"
                          "ℹ️ **Note:** Volume settings are no longer persistent and will reset when the bot restarts.")
        except Exception as e:
            logger.error("setvolume_command", e, guild_id=ctx.guild.id)
            await ctx.send("❌ Failed to update volume. Please try again.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def stats(self, ctx):
        """Show song statistics for this server"""
        log_command_usage(ctx, "stats")
        
        try:
            # Get server-specific stats
            server_stats = await stats_manager.get_server_stats(ctx.guild.id)
            top_songs = await stats_manager.get_server_top_songs(ctx.guild.id, 5)
            queue = audio_manager.get_queue(ctx.guild.id)
            
            embed = discord.Embed(
                title="📊 Server Music Statistics",
                color=0x2b2d31,
                description=f"Statistics for **{ctx.guild.name}**"
            )
            
            # Add server stats
            embed.add_field(
                name="🎵 Server Stats",
                value=(
                    f"Total songs played: **{server_stats.total_plays:,}**\n"
                    f"Recent plays (24h): **{server_stats.recent_plays}**\n"
                    f"Unique songs: **{len(server_stats.most_played)}**"
                ),
                inline=False
            )
            
            # Add current queue info
            embed.add_field(
                name="🎵 Current Session",
                value=(
                    f"Songs in queue: **{len(queue)}**\n"
                    f"Currently playing: {'✅ Yes' if ctx.voice_client and ctx.voice_client.is_playing() else '❌ No'}\n"
                    f"Voice channel: {ctx.voice_client.channel.name if ctx.voice_client else 'Not connected'}"
                ),
                inline=False
            )
            
            # Add top songs if available
            if top_songs:
                top_list = "\n".join([f"**{i+1}.** {song} ({plays} plays)" 
                                     for i, (song, plays) in enumerate(top_songs)])
                embed.add_field(
                    name="🏆 Top Songs (This Server)",
                    value=top_list,
                    inline=False
                )
            else:
                embed.add_field(
                    name="🏆 Top Songs",
                    value="No songs played yet in this server",
                    inline=False
                )
            
            # Add footer with last update
            if server_stats.last_updated:
                from datetime import datetime
                try:
                    last_update = datetime.fromisoformat(server_stats.last_updated)
                    embed.set_footer(text=f"Last updated: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    embed.set_footer(text="Statistics tracked via JSON files")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error("stats_command", e, guild_id=ctx.guild.id)
            await ctx.send("❌ Failed to fetch statistics. Please try again.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def forceleave(self, ctx):
        """Force the bot to leave voice channel and clean up"""
        log_command_usage(ctx, "forceleave")
        
        try:
            # Clean up everything
            audio_manager.clear_queue(ctx.guild.id)
            audio_manager.cancel_alone_timer(ctx.guild.id)
            
            # Disconnect from voice
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                await ctx.send("🚪 **Force disconnected** from voice channel and cleared all data")
            else:
                await ctx.send("ℹ️ Not currently in a voice channel, but cleared all data anyway")
            
        except Exception as e:
            logger.error("forceleave_command", e, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred while forcing leave")

    @commands.command()
    #@commands.has_permissions(administrator=True)
    async def clearqueue(self, ctx):
        """Clear the entire music queue"""
        log_command_usage(ctx, "clear")
        
        try:
            queue_size = len(audio_manager.get_queue(ctx.guild.id))
            
            if queue_size == 0:
                await ctx.send("ℹ️ Queue is already empty!")
                return
            
            # Stop current song and clear queue
            if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                ctx.voice_client.stop()
            
            audio_manager.clear_queue(ctx.guild.id)
            
            await ctx.send(f"🗑️ **Cleared queue** - Removed {queue_size} songs")
            
        except Exception as e:
            logger.error("clearqueue_command", e, guild_id=ctx.guild.id)
            await ctx.send("❌ Failed to clear queue. Please try again.")

    # Error handlers
    @setprefix.error
    async def setprefix_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to use this command!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ You need to specify a prefix!\nUsage: `!setprefix <prefix>`")
        else:
            logger.error("setprefix_error", error, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred with the setprefix command.")

    @setvolume.error
    async def setvolume_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to change volume!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Please provide a valid volume number!\nUsage: `!setvolume <volume>`")
        else:
            logger.error("setvolume_error", error, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred while setting the volume.")

    @stats.error
    async def stats_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to view statistics!")
        else:
            logger.error("stats_error", error, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred while fetching statistics.")

    @forceleave.error
    async def forceleave_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to force disconnect!")
        else:
            logger.error("forceleave_error", error, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred during force disconnect.")

    @clearqueue.error
    async def clearqueue_error(self, ctx, error):
        # No admin permission required; surface other errors
        logger.error("clearqueue_error", error, guild_id=ctx.guild.id)
        await ctx.send("❌ An error occurred while clearing the queue.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot)) 