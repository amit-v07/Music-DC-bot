"""
Music commands for Music Bot
Handles all music-related commands and playback
"""
import asyncio
import discord
from discord.ext import commands
import yt_dlp
from typing import List, Optional
from config import config
from utils.logger import logger, log_command_usage, log_audio_event
from utils.stats_manager import stats_manager
from audio.manager import audio_manager, Song
from ui.views import ui_manager


class MusicCog(commands.Cog):
    """Music-related commands cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def join(self, ctx):
        """Join the user's voice channel"""
        log_command_usage(ctx, "join")
        
        if not ctx.author.voice:
            await ctx.send("❌ Arre, pehle voice channel join karo na!")
            return
        
        if ctx.voice_client:
            if ctx.voice_client.channel == ctx.author.voice.channel:
                await ctx.send("✅ Main toh yahin hoon, enjoy karo!")
                return
            else:
                await ctx.voice_client.move_to(ctx.author.voice.channel)
                await ctx.send(f"🔄 Okay, aa gayi {ctx.author.voice.channel.name} mein")
        else:
            channel = ctx.author.voice.channel
            await channel.connect()
            await ctx.send(f"✅ Aa gayi main {channel.name} mein, music shuru karein?")
        
        # Check if bot is alone and start timer if needed
        if audio_manager.is_bot_alone_in_vc(ctx.guild):
            await audio_manager.start_alone_timer(ctx.guild)
        
        log_audio_event(ctx.guild.id, "joined_voice_channel")
    
    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """Play a song or add to queue"""
        log_command_usage(ctx, "play", query)
        
        if not query.strip():
            await ctx.send("❌ Please provide a song name or URL!")
            return
        
        # Join voice channel if not already connected
        if not ctx.voice_client:
            if not ctx.author.voice:
                await ctx.send("❌ You need to be in a voice channel!")
                return
            await ctx.author.voice.channel.connect()
            
            # Check if bot is alone after joining
            if audio_manager.is_bot_alone_in_vc(ctx.guild):
                await audio_manager.start_alone_timer(ctx.guild)
        
        try:
            # Show processing message for potential playlists
            is_potential_playlist = ('list=' in query or 'playlist' in query.lower() or 
                                   audio_manager._is_spotify_url(query))
            
            processing_msg = None
            if is_potential_playlist:
                processing_msg = await ctx.send("🔄 Processing playlist... This may take a moment.")
            
            # For playlists, use batch processing
            if is_potential_playlist:
                await self._process_playlist_batch(ctx, query, processing_msg)
            else:
                # Single song processing (fast)
                songs = await self._process_query(query, ctx.author.id)
                
                if not songs:
                    await ctx.send("❌ Couldn't find anything to play with that query.")
                    return
                
                # Add songs to queue
                queue_position = audio_manager.add_songs(ctx.guild.id, songs)
                
                # Start playing if nothing is currently playing
                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    await play_current_song(ctx)
                
                # Send feedback to user
                song = songs[0]
                if queue_position == 0:
                    await ctx.send(f"🎵 Lo, suno: **{song.title}**")
                else:
                    await ctx.send(f"➕ Iske baad ye bajega: **{song.title}**")
                
                # Update UI
                await ui_manager.update_all_ui(ctx)
                
                log_audio_event(ctx.guild.id, "songs_added", f"{len(songs)} songs")
            
        except Exception as e:
            logger.error("play_command", e, guild_id=ctx.guild.id, user_id=ctx.author.id)
            error_msg = str(e)
            if "Spotify support is not configured" in error_msg:
                await ctx.send("❌ Spotify integration is not configured. Please set up SPOTIFY_CLIENT_ID and SPOTIPY_CLIENT_SECRET environment variables.")
            elif "playlist" in error_msg.lower():
                await ctx.send(f"❌ Error processing playlist: {error_msg}")
            else:
                await ctx.send(f"❌ An error occurred while processing your request: {error_msg}")
    
    async def _process_query(self, query: str, user_id: int) -> List[Song]:
        """Process user query and return list of songs"""
        songs = []
        
        # Handle Spotify URLs
        if audio_manager._is_spotify_url(query):
            if not audio_manager.spotify_client:
                raise ValueError("Spotify support is not configured.")
            
            songs = await audio_manager.get_spotify_tracks(query)
            
            if not songs:
                raise ValueError("Couldn't find any tracks in that Spotify link.")
            
            # Set requester for all songs
            for song in songs:
                song.requester_id = user_id
            
            return songs
        
        # Handle YouTube/other URLs and search queries
        ydl_opts = config.ydl_options.copy()
        
        if audio_manager._is_http_url(query):
            # It's a URL - check if it's a playlist
            if 'list=' in query or 'playlist' in query.lower():
                # Faster playlist extraction and higher limit
                ydl_opts['noplaylist'] = False
                ydl_opts['extract_flat'] = True  # speed up by not resolving each entry now
                ydl_opts['playlistend'] = 50     # ensure at least 50 items are pulled
                # Remove any single search constraints for playlists
                if 'default_search' in ydl_opts:
                    del ydl_opts['default_search']
            else:
                ydl_opts['noplaylist'] = True
        else:
            # It's a search query - single video only
            ydl_opts['default_search'] = 'ytsearch1'
            ydl_opts['noplaylist'] = True
        
        def _extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                entries = info.get('entries', [info]) if 'entries' in info else [info]
                
                extracted_songs = []
                for entry in entries:
                    if entry:
                        extracted_songs.append(Song(
                            title=entry.get('title', 'Unknown'),
                            webpage_url=entry.get('webpage_url') or entry.get('url'),
                            duration=entry.get('duration'),
                            thumbnail=entry.get('thumbnail'),
                            requester_id=user_id,
                            is_lazy=True
                        ))
                
                return extracted_songs
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        songs = await loop.run_in_executor(None, _extract_info)
        
        return songs
    
    async def _process_playlist_batch(self, ctx, query: str, processing_msg):
        """Process playlists in batches with progress updates"""
        try:
            # First, get playlist info quickly
            songs = await self._process_query(query, ctx.author.id)
            
            if not songs:
                await processing_msg.edit(content="❌ Couldn't find anything to play with that query.")
                return
            
            total_songs = len(songs)
            playlist_type = "Spotify" if audio_manager._is_spotify_url(query) else "YouTube"
            
            # If it's a small playlist, process normally
            if total_songs <= 5:
                queue_position = audio_manager.add_songs(ctx.guild.id, songs)
                
                # Start playing if nothing is currently playing
                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    await play_current_song(ctx)
                
                await processing_msg.edit(
                    content=f"✅ Added **{total_songs}** songs from {playlist_type} playlist to the queue"
                )
                await ui_manager.update_all_ui(ctx)
                log_audio_event(ctx.guild.id, "songs_added", f"{total_songs} songs")
                return
            
            # For large playlists, process in batches
            batch_size = 5
            added_count = 0
            
            # Add first batch immediately
            first_batch = songs[:batch_size]
            queue_position = audio_manager.add_songs(ctx.guild.id, first_batch)
            added_count += len(first_batch)
            
            # Start playing if nothing is currently playing
            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await play_current_song(ctx)
            
            # Update progress
            await processing_msg.edit(
                content=f"🎵 Playing first song! Adding remaining **{total_songs - added_count}** songs in background..."
            )
            await ui_manager.update_all_ui(ctx)
            
            # Process remaining songs in background
            remaining_songs = songs[batch_size:]
            asyncio.create_task(self._background_playlist_add(ctx, remaining_songs, total_songs, playlist_type))
            
        except Exception as e:
            logger.error("process_playlist_batch", e, guild_id=ctx.guild.id)
            await processing_msg.edit(content="❌ Error processing playlist. Please try again.")
    
    async def _background_playlist_add(self, ctx, remaining_songs: List[Song], total_songs: int, playlist_type: str):
        """Add remaining playlist songs in background"""
        try:
            batch_size = 10
            added_count = total_songs - len(remaining_songs)  # Already added first batch
            
            for i in range(0, len(remaining_songs), batch_size):
                batch = remaining_songs[i:i + batch_size]
                audio_manager.add_songs(ctx.guild.id, batch)
                added_count += len(batch)
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.5)
            
            # Final update
            await ctx.send(f"✅ Finished adding all **{total_songs}** songs from {playlist_type} playlist!")
            await ui_manager.update_queue(ctx)  # Update queue UI
            log_audio_event(ctx.guild.id, "playlist_completed", f"{total_songs} songs")
            
        except Exception as e:
            logger.error("background_playlist_add", e, guild_id=ctx.guild.id)
    
    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        """Show the current queue"""
        log_command_usage(ctx, "queue")
        await ui_manager.update_queue(ctx)
    
    @commands.command()
    async def pause(self, ctx):
        """Pause the current song"""
        log_command_usage(ctx, "pause")
        
        if not ctx.voice_client:
            await ctx.send("❌ Main voice channel mein nahi hoon!")
            return
        
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Gaana pause ho gaya. `!resume` se wapas chalu karna.")
            log_audio_event(ctx.guild.id, "paused")
        else:
            await ctx.send("❌ Kuch baj hi nahi raha hai, kya pause karun?")
    
    @commands.command()
    async def resume(self, ctx):
        """Resume the current song"""
        log_command_usage(ctx, "resume")
        
        if not ctx.voice_client:
            await ctx.send("❌ Main voice channel mein nahi hoon!")
            return
        
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Chalo, music wapas on!")
            log_audio_event(ctx.guild.id, "resumed")
        else:
            await ctx.send("❌ Gaana toh pehle se hi chal raha hai, dear!")
    
    @commands.command(aliases=['next'])
    async def skip(self, ctx):
        """Skip to the next song"""
        log_command_usage(ctx, "skip")
        
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return
        
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped to next song")
            log_audio_event(ctx.guild.id, "skipped")
        else:
            await ctx.send("❌ Nothing is currently playing!")
    
    @commands.command()
    async def stop(self, ctx):
        """Stop playback and clear the queue"""
        log_command_usage(ctx, "stop")
        
        if not ctx.voice_client:
            await ctx.send("❌ Arre, main toh kisi voice channel mein hi nahi hoon!")
            return
        
        audio_manager.clear_queue(ctx.guild.id)
        
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
        
        await ctx.send("⏹️ Music band aur queue bhi clear kar di!")
        await ui_manager.update_all_ui(ctx)
        log_audio_event(ctx.guild.id, "stopped")
    
    @commands.command()
    async def leave(self, ctx):
        """Leave the voice channel"""
        log_command_usage(ctx, "leave")
        
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return
        
        # Clean up
        audio_manager.clear_queue(ctx.guild.id)
        audio_manager.cancel_alone_timer(ctx.guild.id)
        await ui_manager.cleanup_all_messages(ctx.guild.id)
        
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Okay, main chali. Phir milte hain!")
        log_audio_event(ctx.guild.id, "left_voice_channel")
    
    @commands.command(aliases=['goto', 'jumpto'])
    async def jump(self, ctx, position: int):
        """Jump to a specific song in the queue"""
        log_command_usage(ctx, "jump", str(position))
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if not queue:
            await ctx.send("❌ The queue is empty!")
            return
        
        # Convert to 0-based index
        target_index = position - 1
        
        if not (0 <= target_index < len(queue)):
            await ctx.send(f"❌ Invalid position! Choose between 1 and {len(queue)}")
            return
        
        if audio_manager.jump_to_song(ctx.guild.id, target_index):
            # Stop current song if playing
            if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                ctx.voice_client.stop()
            
            # Play the selected song
            await play_current_song(ctx)
            
            song_title = queue[target_index].title
            await ctx.send(f"⏭️ Jumped to position {position}: **{song_title}**")
            log_audio_event(ctx.guild.id, "jumped_to_song", song_title)
        else:
            await ctx.send("❌ Failed to jump to that position")
    
    @commands.command()
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        log_command_usage(ctx, "shuffle")
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if len(queue) <= 1:
            await ctx.send("❌ Not enough songs in the queue to shuffle")
            return
        
        audio_manager.shuffle_queue(ctx.guild.id)
        await ctx.send("🔀 Queue shuffled!")
        await ui_manager.update_queue(ctx)
        log_audio_event(ctx.guild.id, "shuffled_queue")
    
    @commands.command()
    async def remove(self, ctx, position: int):
        """Remove a song from the queue"""
        log_command_usage(ctx, "remove", str(position))
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if not queue:
            await ctx.send("❌ The queue is empty!")
            return
        
        # Convert to 0-based index
        index = position - 1
        
        if not (0 <= index < len(queue)):
            await ctx.send(f"❌ Invalid position! Choose between 1 and {len(queue)}")
            return
        
        # Handle removing currently playing song
        current_idx = audio_manager.guild_current_index.get(ctx.guild.id, 0)
        if index == current_idx:
            if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                ctx.voice_client.stop()
            await ctx.send(f"⏭️ Skipped currently playing song")
        else:
            removed_song = audio_manager.remove_song(ctx.guild.id, index)
            if removed_song:
                await ctx.send(f"🗑️ Removed: **{removed_song.title}**")
                await ui_manager.update_queue(ctx)
            else:
                await ctx.send("❌ Failed to remove song")
        
        log_audio_event(ctx.guild.id, "removed_song")
    
    @commands.command()
    async def move(self, ctx, from_pos: int, to_pos: int):
        """Move a song from one position to another"""
        log_command_usage(ctx, "move", f"{from_pos} {to_pos}")
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if len(queue) <= 1:
            await ctx.send("❌ Not enough songs in the queue to move")
            return
        
        # Convert to 0-based indices
        from_idx = from_pos - 1
        to_idx = to_pos - 1
        
        if not (0 <= from_idx < len(queue) and 0 <= to_idx < len(queue)):
            await ctx.send(f"❌ Invalid positions! Choose between 1 and {len(queue)}")
            return
        
        if audio_manager.move_song(ctx.guild.id, from_idx, to_idx):
            song_title = queue[to_idx].title
            await ctx.send(f"🔄 Moved **{song_title}** to position {to_pos}")
            await ui_manager.update_queue(ctx)
            log_audio_event(ctx.guild.id, "moved_song")
        else:
            await ctx.send("❌ Failed to move song")
    
    @commands.command()
    async def repeat(self, ctx):
        """Toggle repeat for current song"""
        log_command_usage(ctx, "repeat")
        
        current_repeat = audio_manager.is_repeat(ctx.guild.id)
        new_repeat = not current_repeat
        audio_manager.set_repeat(ctx.guild.id, new_repeat)
        
        status = "ON" if new_repeat else "OFF"
        emoji = "🔂" if new_repeat else "🔁"
        await ctx.send(f"{emoji} Repeat is now **{status}**")
        log_audio_event(ctx.guild.id, f"repeat_{status.lower()}")
    
    @commands.command()
    async def volume(self, ctx, vol: float):
        """Set the playback volume (0.1 - 2.0)"""
        log_command_usage(ctx, "volume", str(vol))
        
        if not (config.min_volume <= vol <= config.max_volume):
            await ctx.send(f"❌ Volume must be between {config.min_volume} and {config.max_volume}")
            return
        
        audio_manager.set_volume(ctx.guild.id, vol)
        
        # Apply to current source if playing
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = vol
        
        await ctx.send(f"🔊 Volume set to **{vol}** (session only)")
        log_audio_event(ctx.guild.id, "volume_changed", str(vol))
    
    @commands.command(aliases=['cleanup', 'clean'])
    async def cleanqueue(self, ctx):
        """Remove invalid/broken songs from the queue"""
        log_command_usage(ctx, "cleanqueue")
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if not queue:
            await ctx.send("❌ The queue is empty!")
            return
        
        initial_count = len(queue)
        removed_count = await audio_manager.validate_queue_songs(ctx.guild.id, max_check=50)
        
        if removed_count > 0:
            await ctx.send(f"🧹 Cleaned queue: Removed **{removed_count}** invalid songs")
            await ui_manager.update_queue(ctx)
        else:
            await ctx.send("✅ Queue looks clean - no invalid songs found")
        
        log_audio_event(ctx.guild.id, "queue_cleaned", f"{removed_count} songs removed")
    
    # Error handlers
    @play.error
    async def play_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ You need to provide a song name or URL!\nUsage: `!play <song name or URL>`")
        else:
            logger.error("play_command_error", error, guild_id=ctx.guild.id, user_id=ctx.author.id)
            await ctx.send("❌ An error occurred while processing the play command.")
    
    @jump.error
    async def jump_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ You need to specify a song number!\nUsage: `!jump <number>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Please provide a valid number!\nUsage: `!jump <number>`")
        else:
            logger.error("jump_command_error", error, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred with the jump command.")
    
    @volume.error
    async def volume_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ You need to specify a volume level!\nUsage: `!volume <{config.min_volume}-{config.max_volume}>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Please provide a valid number!\nUsage: `!volume <{config.min_volume}-{config.max_volume}>`")
        else:
            logger.error("volume_command_error", error, guild_id=ctx.guild.id)
            await ctx.send("❌ An error occurred with the volume command.")


async def play_current_song(ctx):
    """Play the current song in the queue with improved error handling"""
    guild_id = ctx.guild.id
    max_retries = 5  # Maximum number of songs to try before giving up
    retry_count = 0
    
    while retry_count < max_retries:
        current_song = audio_manager.get_current_song(guild_id)
        
        if not current_song:
            await ctx.send("❌ No more songs to play!")
            await ui_manager.update_all_ui(ctx)
            return
        
        if not ctx.voice_client:
            await ctx.send("❌ I'm not in a voice channel!")
            return
        
        # Check if already playing to avoid "Already playing audio" error
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            logger.warning("play_current_song called while already playing", guild_id=guild_id)
            return
        
        try:
            # Create audio source
            source = await audio_manager.create_audio_source(current_song, guild_id)
            
            def after_playing(error):
                if error:
                    logger.error("audio_playback", Exception(str(error)), guild_id=guild_id)
                
                # Schedule next song
                if ctx.voice_client:
                    fut = asyncio.run_coroutine_threadsafe(handle_song_end(ctx), ctx.bot.loop)
                    try:
                        fut.result()
                    except Exception as e:
                        logger.error("after_playing_future", e, guild_id=guild_id)
            
            # Start playback
            ctx.voice_client.play(source, after=after_playing)
            
            # Record song play in stats
            await stats_manager.record_song_play(
                guild_id=guild_id,
                title=current_song.title,
                requester_id=current_song.requester_id,
                duration=current_song.duration,
                guild_name=ctx.guild.name
            )
            
            # Update UI
            await ui_manager.update_all_ui(ctx)
            
            log_audio_event(guild_id, "song_started", current_song.title)
            return  # Successfully started playing
            
        except Exception as e:
            retry_count += 1
            logger.error("play_current_song", e, guild_id=guild_id, song_title=current_song.title)
            
            # Remove the failed song from queue to prevent infinite loop
            current_idx = audio_manager.guild_current_index.get(guild_id, 0)
            audio_manager.remove_song(guild_id, current_idx)
            
            # Send error message (but less spammy for multiple failures)
            if retry_count == 1:
                await ctx.send(f"❌ Failed to play: **{current_song.title}**. Trying next song...")
            elif retry_count <= 3:
                await ctx.send(f"❌ Skipping unplayable song: **{current_song.title}**")
            elif retry_count == 4:
                await ctx.send("⚠️ Multiple songs failed to play. Checking remaining queue...")
            
            # Small delay to prevent rapid failures
            await asyncio.sleep(0.5)
            
            # Continue to next song without incrementing the index (since we removed the failed song)
            continue
    
    # If we get here, we've failed to play multiple songs
    await ctx.send(
        "❌ **Multiple songs failed to play.** This might be due to:\n"
        "• Region-blocked content\n"
        "• Deleted/unavailable videos\n"
        "• Playlist issues\n\n"
        "🔧 Try adding individual songs or different playlists."
    )
    await ui_manager.update_all_ui(ctx)


async def handle_song_end(ctx):
    """Handle what happens when a song ends"""
    guild_id = ctx.guild.id
    
    try:
        # Check repeat mode
        if audio_manager.is_repeat(guild_id):
            # Replay current song
            await play_current_song(ctx)
            return
        
        # Move to next song
        if audio_manager.next_song(guild_id):
            # Preload next song in background to reduce gap
            try:
                next_song = audio_manager.get_current_song(guild_id)
                if next_song and next_song.is_lazy:
                    asyncio.create_task(audio_manager.resolve_lazy_song(next_song))
            except Exception:
                pass
            await play_current_song(ctx)
        else:
            # Queue finished
            await ctx.send("🎵 Queue finished! Add more songs or I'll leave in 5 minutes if inactive.")
            await ui_manager.update_all_ui(ctx)
            
            # Start idle timer
            asyncio.create_task(idle_disconnect(ctx))
            
            log_audio_event(guild_id, "queue_finished")
            
    except Exception as e:
        logger.error("handle_song_end", e, guild_id=guild_id)


async def idle_disconnect(ctx):
    """Disconnect after idle timeout if nothing is playing"""
    await asyncio.sleep(config.idle_timeout)
    
    if (ctx.voice_client and 
        not ctx.voice_client.is_playing() and 
        not audio_manager.get_queue(ctx.guild.id)):
        
        await ctx.send("💤 Disconnecting due to inactivity. See you later!")
        audio_manager.cancel_alone_timer(ctx.guild.id)
        await ui_manager.cleanup_all_messages(ctx.guild.id)
        await ctx.voice_client.disconnect()
        log_audio_event(ctx.guild.id, "idle_disconnect")


async def setup(bot):
    await bot.add_cog(MusicCog(bot)) 