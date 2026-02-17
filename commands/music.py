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
from utils.ai_brain import ai_brain
from utils.listening_history import listening_history
from utils.limiter import play_limiter, control_limiter


class MusicCog(commands.Cog):
    """Music-related commands cog"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def join(self, ctx):
        """Join the user's voice channel"""
        log_command_usage(ctx, "join")
        
        if not ctx.author.voice:
            await ctx.send("❌ Arre bhai, pehle voice channel toh join karo! Main hawa mein gaana bajau kya? 🤷‍♂️")
            return
        
        if ctx.voice_client:
            if ctx.voice_client.channel == ctx.author.voice.channel:
                await ctx.send("✅ Main toh yahin hoon, enjoy karo!")
                return
            else:
                await ctx.voice_client.move_to(ctx.author.voice.channel)
                await ctx.send(f"🔄 Aa gayi main **{ctx.author.voice.channel.name}** mein! Ab machega shor! 🔊")
        else:
            channel = ctx.author.voice.channel
            try:
                await channel.connect(timeout=60, reconnect=True)
            except asyncio.TimeoutError:
                await ctx.send("❌ Connection timed out! Discord voice servers are taking too long to respond. Try again.")
                return
            except Exception as e:
                await ctx.send(f"❌ Failed to connect to voice channel: {str(e)}")
                return
            await ctx.send(f"✅ **{channel.name}** mein entry maar li hai! Chalo music shuru karte hain! 🎵")
        
        # Check if bot is alone and start timer if needed
        if audio_manager.is_bot_alone_in_vc(ctx.guild):
            await audio_manager.start_alone_timer(ctx.guild)
        
        log_audio_event(ctx.guild.id, "joined_voice_channel")
    
    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """Play a song or add to queue"""
        log_command_usage(ctx, "play", query)
        
        # Rate limit check
        if not play_limiter.check(ctx.author.id):
            await ctx.send("⏱️ Oye hoye! Itni jaldi kya hai? Thoda saans le le bhai! 🛑")
            return
        
        if not query.strip():
            await ctx.send("❌ Arre, gaane ka naam toh batao! Ya main khud gaaun? 🎤")
            return
            
        if len(query) > 500:
            await ctx.send("❌ Itna lamba search? Novel likh rahe ho kya? Chota karo isse! (Max 500 chars)")
            return
            
        query = query.strip()
        
        # Join voice channel if not already connected
        if not ctx.voice_client:
            if not ctx.author.voice:
                await ctx.send("❌ Voice channel mein aao pehle, wahan party karenge!")
                return
            try:
                await ctx.author.voice.channel.connect(timeout=60, reconnect=True)
            except asyncio.TimeoutError:
                await ctx.send("❌ Connection timed out! Discord voice servers are taking too long to respond. Try again.")
                return
            except Exception as e:
                await ctx.send(f"❌ Failed to connect to voice channel: {str(e)}")
                return
            
            # Check if bot is alone after joining
            if audio_manager.is_bot_alone_in_vc(ctx.guild):
                await audio_manager.start_alone_timer(ctx.guild)
        
        try:
            # Show processing message for potential playlists
            is_potential_playlist = ('list=' in query or 'playlist' in query.lower() or 
                                   audio_manager._is_spotify_url(query))
            
            processing_msg = None
            if is_potential_playlist:
                processing_msg = await ctx.send("🔄 Playlist detected! Ruko, channi laga ke gaane nikaal rahi hoon... 🕵️‍♀️")
            
            # For playlists, use batch processing
            if is_potential_playlist:
                await self._process_playlist_batch(ctx, query, processing_msg)
            else:
                # Single song processing (fast)
                songs = await self._process_query(query, ctx.author.id)
                
                if not songs:
                    await ctx.send("❌ Kuch nahi mila yaar. Spelling check karo ya koi aur gaana try karo! 🔍")
                    return
                
                # Add songs to queue
                queue_position = audio_manager.add_songs(ctx.guild.id, songs)
                
                # Start playing if nothing is currently playing
                if ctx.voice_client and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    await play_current_song(ctx)
                
                # Active! Cancel any idle timers
                audio_manager.cancel_idle_timer(ctx.guild.id)
                audio_manager.cancel_alone_timer(ctx.guild.id)
                
                # Send feedback to user
                song = songs[0]
                if queue_position == 0:
                    await ctx.send(f"🎵 **Lo suno!** Ab baj raha hai: **{song.title}** 🎶")
                else:
                    await ctx.send(f"➕ **Line mein lag gaya:** **{song.title}** (#{queue_position})")
                
                # Update UI
                await ui_manager.update_all_ui(ctx)
                
                log_audio_event(ctx.guild.id, "songs_added", f"{len(songs)} songs")
            
        except Exception as e:
            logger.error("play_command", e, guild_id=ctx.guild.id, user_id=ctx.author.id)
            error_msg = str(e)
            if "Spotify support is not configured" in error_msg:
                await ctx.send("❌ Spotify setup nahi hai bhai. Owner ko bolo `SPOTIFY_CLIENT_ID` set kare!")
            elif "playlist" in error_msg.lower():
                await ctx.send(f"❌ Playlist mein locha hai: {error_msg}")
            else:
                await ctx.send(f"❌ Arre yaar, kuch gadbad ho gayi: {error_msg}")
    
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
                            is_lazy=True,
                            requester_name="Unknown" # Will be updated when actually played if we had context, but here we don't have ctx easily
                        ))
                
                return extracted_songs
        
        # Run in executor to avoid blocking, wrapped in circuit breaker
        try:
            from utils.circuit_breaker import youtube_circuit_breaker, CircuitBreakerOpen
            
            async def _safe_extract():
                if youtube_circuit_breaker.state == "OPEN":
                     # Check if recovery timeout passed
                    if time.time() - youtube_circuit_breaker.last_failure_time > youtube_circuit_breaker.recovery_timeout:
                        youtube_circuit_breaker.state = "HALF_OPEN"
                    else:
                        raise CircuitBreakerOpen("YouTube API circuit is OPEN. Please wait.")
                
                try:
                    result = await loop.run_in_executor(None, _extract_info)
                    
                    if youtube_circuit_breaker.state == "HALF_OPEN":
                         youtube_circuit_breaker.state = "CLOSED"
                         youtube_circuit_breaker.failures = 0
                    
                    return result
                except Exception as e:
                    youtube_circuit_breaker.failures += 1
                    youtube_circuit_breaker.last_failure_time = time.time()
                    if youtube_circuit_breaker.failures >= youtube_circuit_breaker.failure_threshold:
                        youtube_circuit_breaker.state = "OPEN"
                    raise e

            loop = asyncio.get_event_loop()
            songs = await _safe_extract()
            
        except CircuitBreakerOpen:
            raise ValueError("YouTube API is temporarily unavailable due to high error rate. Please try again in a minute.")
        except Exception as e:
            raise e
        
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
                # Check circuit breaker before processing batch
                from utils.circuit_breaker import youtube_circuit_breaker
                if youtube_circuit_breaker.state == "OPEN":
                     # API is down, stop adding song to prevent bans
                     logger.warning("YouTube API circuit OPEN. Stopping background playlist processing.")
                     break

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
            await ctx.send("⏸️ **Ruk gaya bhai!** Break le liya. `!resume` kar dena jab wapas aao.")
            log_audio_event(ctx.guild.id, "paused")
        else:
            await ctx.send("❌ Are kuch baj hi nahi raha, kise pause karu? Hawa ko? 😂")
    
    @commands.command(aliases=['start'])
    async def resume(self, ctx):
        """Resume the current song"""
        log_command_usage(ctx, "resume")
        
        if not ctx.voice_client:
            await ctx.send("❌ Main voice channel mein nahi hoon!")
            return
        
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ **Chalo bhai, wapas party shuru!** 🕺")
            log_audio_event(ctx.guild.id, "resumed")
        else:
            await ctx.send("❌ Gaana toh chal hi raha hai! Kya restart karu? 🤔")
    
    @commands.command(aliases=['next'])
    async def skip(self, ctx):
        """Skip to the next song"""
        log_command_usage(ctx, "skip")
        
        if not control_limiter.check(ctx.author.id):
            await ctx.send("⏱️ Too fast! Please wait before skipping again.")
            return
        
        if not ctx.voice_client:
            await ctx.send("❌ Bhai main voice channel mein nahi hoon, kis chiz ko skip karu?")
            return
        
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            # Get song info for AI context
            current_song = audio_manager.get_current_song(ctx.guild.id)
            song_title = current_song.title if current_song else "song"
            
            ctx.voice_client.stop()
            
            # AI Response
            reply = await ai_brain.get_response("skip", {
                "user": ctx.author.display_name,
                "song": song_title
            })
            await ctx.send(f"⏭️ **Skip kar diya!** {reply}")
            log_audio_event(ctx.guild.id, "skipped")
        else:
            await ctx.send("❌ Are kuch baj hi nahi raha, kise skip karu?")
    
    @commands.command()
    async def stop(self, ctx):
        """Stop playback, clear queue, and disable autoplay"""
        log_command_usage(ctx, "stop")
        
        if not control_limiter.check(ctx.author.id):
            return  # Silently ignore stop spam
        
        if not ctx.voice_client:
            await ctx.send("❌ Arre, main toh kisi voice channel mein hi nahi hoon! Kise roku?")
            return
        
        # 1. Clear Queue
        audio_manager.clear_queue(ctx.guild.id)
        
        # 2. Disable Autoplay
        audio_manager.disable_autoplay(ctx.guild.id)
        
        # 3. Stop Playback
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
        
        # AI Response
        reply = await ai_brain.get_response("stop", {"user": ctx.author.display_name})
        
        # Send comprehensive status message
        await ctx.send(
            f"⏹️ **Bas, khatam!** {reply}\n"
            "🗑️ Queue bhi saaf kar di.\n"
            "⏸️ Autoplay bhi band."
        )
        
        await ui_manager.update_all_ui(ctx)
        log_audio_event(ctx.guild.id, "stopped")
    
    @commands.command(aliases=['bye', 'exit', 'quit', 'dc', 'disconnect', 'out'])
    async def leave(self, ctx):
        """Leave the voice channel"""
        log_command_usage(ctx, "leave")
        
        if not ctx.voice_client:
            await ctx.send("❌ Main pehle se hi bahar hoon bhai!")
            return
        
        # Clean up
        audio_manager.clear_queue(ctx.guild.id)
        audio_manager.disable_autoplay(ctx.guild.id)
        audio_manager.cancel_alone_timer(ctx.guild.id)
        await ui_manager.cleanup_all_messages(ctx.guild.id)
        
        await ctx.voice_client.disconnect()
        await ctx.send("👋 **Chalo, main chalti hoon!** Phir milenge! Tata! byee! 👋")
        log_audio_event(ctx.guild.id, "left_voice_channel")
    
    @commands.command(aliases=['goto', 'jumpto'])
    async def jump(self, ctx, position: int):
        """Jump to a specific song in the queue"""
        log_command_usage(ctx, "jump", str(position))
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if not queue:
            await ctx.send("❌ Queue khaali hai! Kahan jump karu? Khayi mein? 😅")
            return
        
        # Convert to 0-based index
        target_index = position - 1
        
        if not (0 <= target_index < len(queue)):
            await ctx.send(f"❌ Galat number! 1 se {len(queue)} ke beech mein bolo.")
            return
        
        if audio_manager.jump_to_song(ctx.guild.id, target_index):
            # Stop current song if playing
            if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                ctx.voice_client.stop()
            
            # Play the selected song
            await play_current_song(ctx)
            
            song_title = queue[target_index].title
            await ctx.send(f"⏭️ **Chalo seedha wahan!** Ab bajega: **{song_title}** (#{position})")
            log_audio_event(ctx.guild.id, "jumped_to_song", song_title)
        else:
            await ctx.send("❌ Jump fail ho gaya yaar!")
    
    @commands.command()
    async def shuffle(self, ctx):
        """Shuffle the queue"""
        log_command_usage(ctx, "shuffle")
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if len(queue) <= 1:
            await ctx.send("❌ Ek gaane ko kya shuffle karu? Thode aur add karo!")
            return
        
        audio_manager.shuffle_queue(ctx.guild.id)
        await ctx.send("🔀 **Mix kar diya sab!** Ab suspense bana rahega! 🎲")
        await ui_manager.update_queue(ctx)
        log_audio_event(ctx.guild.id, "shuffled_queue")
    
    @commands.command()
    async def remove(self, ctx, position: int):
        """Remove a song from the queue"""
        log_command_usage(ctx, "remove", str(position))
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if not queue:
            await ctx.send("❌ Queue khaali hai bhai!")
            return
        
        # Convert to 0-based index
        index = position - 1
        
        if not (0 <= index < len(queue)):
            await ctx.send(f"❌ Galat number! 1 se {len(queue)} ke beech mein bolo.")
            return
        
        # Handle removing currently playing song
        current_idx = audio_manager.guild_current_index.get(ctx.guild.id, 0)
        if index == current_idx:
            if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                ctx.voice_client.stop()
            await ctx.send(f"⏭️ Jo baj raha tha usse hi uda diya!")
        else:
            removed_song = audio_manager.remove_song(ctx.guild.id, index)
            if removed_song:
                await ctx.send(f"🗑️ Uda diya: **{removed_song.title}**")
                await ui_manager.update_queue(ctx)
            else:
                await ctx.send("❌ Delete nahi ho paya!")
        
        log_audio_event(ctx.guild.id, "removed_song")
    
    @commands.command()
    async def move(self, ctx, from_pos: int, to_pos: int):
        """Move a song from one position to another"""
        log_command_usage(ctx, "move", f"{from_pos} {to_pos}")
        
        queue = audio_manager.get_queue(ctx.guild.id)
        
        if len(queue) <= 1:
            await ctx.send("❌ Akele gaane ko kahan le jaaun? 🤷‍♂️")
            return
        
        # Convert to 0-based indices
        from_idx = from_pos - 1
        to_idx = to_pos - 1
        
        if not (0 <= from_idx < len(queue) and 0 <= to_idx < len(queue)):
            await ctx.send(f"❌ Galat positions! 1 se {len(queue)} ke beech mein bolo.")
            return
        
        if audio_manager.move_song(ctx.guild.id, from_idx, to_idx):
            song_title = queue[to_idx].title
            await ctx.send(f"🔄 **{song_title}** ko position {to_pos} pe bhej diya!")
            await ui_manager.update_queue(ctx)
            log_audio_event(ctx.guild.id, "moved_song")
        else:
            await ctx.send("❌ Move nahi ho paya yaar!")
    
    @commands.command()
    async def repeat(self, ctx):
        """Toggle repeat for current song"""
        log_command_usage(ctx, "repeat")
        
        current_repeat = audio_manager.is_repeat(ctx.guild.id)
        new_repeat = not current_repeat
        audio_manager.set_repeat(ctx.guild.id, new_repeat)
        
        status = "ON" if new_repeat else "OFF"
        emoji = "🔂" if new_repeat else "🔁"
        msg = "Ab yahi bajta rahega!" if new_repeat else "Chalo, aage badhte hain!"
        await ctx.send(f"{emoji} Repeat **{status}** kar diya! {msg}")
        log_audio_event(ctx.guild.id, f"repeat_{status.lower()}")
    
    @commands.command()
    async def volume(self, ctx, vol: float):
        """Set the playback volume (0.1 - 2.0)"""
        log_command_usage(ctx, "volume", str(vol))
        
        if not (config.min_volume <= vol <= config.max_volume):
            await ctx.send(f"❌ Bhai, volume {config.min_volume} se {config.max_volume} ke beech rakhna!")
            return
        
        audio_manager.set_volume(ctx.guild.id, vol)
        
        # Apply to current source if playing
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = vol
        
        await ctx.send(f"🔊 Volume set to **{vol}**! (Sirf abhi ke liye) 🎚️")
        log_audio_event(ctx.guild.id, "volume_changed", str(vol))
    
    @commands.command(aliases=['cleanup', 'clean', 'clear'])
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
    
    @commands.command(aliases=['ap', 'auto'])
    async def autoplay(self, ctx, toggle: str = None):
        """Toggle autoplay mode - automatically plays related songs when queue ends"""
        log_command_usage(ctx, "autoplay", toggle or "")
        
        guild_id = ctx.guild.id
        current_status = audio_manager.is_autoplay_enabled(guild_id)
        
        # If no argument, just toggle
        if toggle is None:
            new_status = not current_status
        elif toggle.lower() in ['on', 'enable', 'true', '1']:
            new_status = True
        elif toggle.lower() in ['off', 'disable', 'false', '0']:
            new_status = False
        else:
            await ctx.send("❌ Invalid option! Use `!autoplay on` or `!autoplay off`")
            return
        
        if new_status:
            audio_manager.enable_autoplay(guild_id)
            await ctx.send(
                "🎵 **Autoplay chalu kar diya!**\n"
                "Ab queue khatam hone ke baad main khud related songs bajaungi. Tension mat lo, party chalti rahegi! 🚀\n"
                "Band karna ho toh `!autoplay off` bol dena."
            )
            
            # EDGE CASE FIX: If queue is empty and bot is not playing, kickstart autoplay now!
            queue = audio_manager.get_queue(guild_id)
            is_playing = ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused())
            
            if len(queue) == 0 and not is_playing:
                # Queue is empty! Start autoplay immediately
                await ctx.send("🎶 Queue toh khali hai... Main abhi kuch dhang ka music bajati hoon! 🔥")
                
                try:
                    # Get recommendations based on listening history
                    recommendations = await audio_manager.get_autoplay_recommendations(guild_id, count=5)
                    
                    if recommendations:
                        # Add to queue (this sets current_index to 0 since queue was empty)
                        audio_manager.add_songs(guild_id, recommendations)
                        
                        # Join voice channel if not already in one
                        if not ctx.voice_client:
                            if ctx.author.voice:
                                await ctx.author.voice.channel.connect()
                            else:
                                await ctx.send("❌ Pehle voice channel mein aao! Main kaise bajau! 🤷")
                                return
                        
                        # Start playing (current_index is already 0, no need to call next_song)
                        await play_current_song(ctx)
                        
                        # AI Response
                        first_song = recommendations[0].title
                        reply = await ai_brain.get_response("autoplay_start", {"song": first_song, "count": len(recommendations)})
                        await ctx.send(f"✅ {reply}")
                        
                        log_audio_event(guild_id, "autoplay_kickstarted", f"{len(recommendations)} songs")
                    else:
                        # No listening history yet
                        await ctx.send(
                            "🤔 **Hmm...** Pehle kuch songs bajao toh sahi! "
                            "Mujhe pata chale tumhe kya pasand hai. Phir main sahi recommendations dungi! 😎\n"
                            "Try: `!play <song name>`"
                        )
                except Exception as e:
                    logger.error("autoplay_kickstart", e, guild_id=guild_id)
                    await ctx.send("❌ Oops! Kuch gadbad ho gayi. Phir se try karo!")
        else:
            audio_manager.disable_autoplay(guild_id)
            await ctx.send("⏸️ **Autoplay band.** Ab queue khatam toh music khatam. Boriyat shuru? 😴")
        
        log_audio_event(guild_id, f"autoplay_{'enabled' if new_status else 'disabled'}")
    
    @commands.command()
    async def recommend(self, ctx, count: int = 5):
        """Manually get song recommendations based on your listening history"""
        log_command_usage(ctx, "recommend", str(count))
        
        if not (1 <= count <= 10):
            await ctx.send("❌ Please specify a count between 1 and 10")
            return
        
        try:
            processing_msg = await ctx.send("🔄 Ruko, mast recommendations dhoondh rahi hoon...")
            
            recommendations = await audio_manager.get_autoplay_recommendations(ctx.guild.id, count)
            
            if not recommendations:
                await processing_msg.edit(content="❌ Arre, kuch mila hi nahi. Pehle kuch gaane toh bajao!")
                return
            
            # Add recommendations to queue
            queue_position = audio_manager.add_songs(ctx.guild.id, recommendations)
            
            # Start playing if nothing is currently playing
            if ctx.voice_client and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await play_current_song(ctx)
            
            await processing_msg.edit(
                content=f"✅ Lo ji, **{len(recommendations)}** gaane queue mein daal diye! Enjoy! 🎶"
            )
            await ui_manager.update_all_ui(ctx)
            log_audio_event(ctx.guild.id, "manual_recommendations", f"{len(recommendations)} songs")
            
        except Exception as e:
            logger.error("recommend_command", e, guild_id=ctx.guild.id)
            await ctx.send("❌ Oops, recommendations lane mein kuch gadbad ho gayi. Phir se try karo.")



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
            
            # Get requester name
            requester_name = "Unknown"
            if current_song.requester_id:
                try:
                    member = ctx.guild.get_member(current_song.requester_id)
                    if member:
                        requester_name = member.display_name
                    else:
                        try:
                            member = await ctx.guild.fetch_member(current_song.requester_id)
                            requester_name = member.display_name
                        except:
                            pass
                except:
                    pass

            # Record song play in stats
            await stats_manager.record_song_play(
                guild_id=guild_id,
                title=current_song.title,
                requester_id=current_song.requester_id,
                duration=current_song.duration,
                guild_name=ctx.guild.name,
                requester_name=requester_name
            )
            
            # Record in listening history for recommendations
            from utils.listening_history import listening_history
            try:
                # Use original_url (YouTube URL) for recommendations, fallback to webpage_url if not set
                history_url = current_song.original_url or current_song.webpage_url
                listening_history.record_play(
                    guild_id=guild_id,
                    title=current_song.title,
                    url=history_url,
                    requester_id=current_song.requester_id,
                    duration=current_song.duration
                )
            except Exception as e:
                logger.error("listening_history_record", e, guild_id=guild_id)
            
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
            
            # Continuous Autoplay: Check if we need to buffer more songs
            if audio_manager.is_autoplay_enabled(guild_id):
                try:
                    # Calculate remaining songs
                    queue = audio_manager.get_queue(guild_id)
                    current_idx = audio_manager.guild_current_index.get(guild_id, 0)
                    remaining = len(queue) - (current_idx + 1)
                    
                    # If getting low (less than 3 songs), fetch more in background
                    if remaining <= 2:
                        asyncio.create_task(trigger_autoplay_buffer(ctx, guild_id))
                except Exception as e:
                    logger.error("autoplay_buffer_check", e, guild_id=guild_id)

        else:
            # Queue finished - check if autoplay is enabled
            if audio_manager.is_autoplay_enabled(guild_id):
                try:
                    # AI Response for queue end
                    reply_end = await ai_brain.get_response("queue_end", {"user": "Music Lovers"})
                    await ctx.send(f"🎵 **Autoplay**: {reply_end}")
                    
                    # Get recommendations
                    recommendations = await audio_manager.get_autoplay_recommendations(guild_id, count=5)
                    
                    if recommendations:
                        # Add to queue (this sets current_index to 0 since queue was empty)
                        audio_manager.add_songs(guild_id, recommendations)
                        
                        # Start playing first recommendation (already at index 0, no need to call next_song)
                        await play_current_song(ctx)
                        
                        # AI Response for adding songs
                        first_song = recommendations[0].title
                        reply_added = await ai_brain.get_response("autoplay_start", {"song": first_song, "count": len(recommendations)})
                        await ctx.send(f"✅ {reply_added}")
                        
                        log_audio_event(guild_id, "autoplay_activated", f"{len(recommendations)} songs")
                        
                        # Trigger buffer check immediately in case we need even more (unlikely but good safety)
                        # asyncio.create_task(trigger_autoplay_buffer(ctx, guild_id))
                    else:
                        reply_fail = await ai_brain.get_response("error", {"user": "System"})
                        await ctx.send(f"❌ {reply_fail} (No recommendations found)")
                        await ctx.send("🎵 Queue finished! Add more songs or I'll leave in 5 minutes if inactive.")
                        await audio_manager.start_idle_timer(ctx)
                        
                except Exception as e:
                    logger.error("autoplay_activation", e, guild_id=guild_id)
                    await ctx.send("❌ Autoplay failed. Queue finished!")
                    await audio_manager.start_idle_timer(ctx)
            else:
                # No autoplay - normal queue finish behavior
                await ctx.send("🎵 Queue finished! Add more songs or I'll leave in 5 minutes if inactive.")
                await ui_manager.update_all_ui(ctx)
                
                # Start idle timer
                await audio_manager.start_idle_timer(ctx)
                
            log_audio_event(guild_id, "queue_finished")
            
    except Exception as e:
        logger.error("handle_song_end", e, guild_id=guild_id)


async def trigger_autoplay_buffer(ctx, guild_id):
    """Background task to buffer more songs for autoplay"""
    try:
        # Double check if we still need songs (race conditions)
        queue = audio_manager.get_queue(guild_id)
        current_idx = audio_manager.guild_current_index.get(guild_id, 0)
        remaining = len(queue) - (current_idx + 1)
        
        if remaining > 2:
            return

        # Fetch songs silently
        recommendations = await audio_manager.get_autoplay_recommendations(guild_id, count=5)
        
        if recommendations:
            audio_manager.add_songs(guild_id, recommendations)
            
            # AI Response for buffer
            reply_buffer = await ai_brain.get_response("autoplay_start", {"song": "Backup Dancers", "count": len(recommendations)})
            await ctx.send(f"🎵 **Autoplay**: {reply_buffer} (Buffered {len(recommendations)} more)")
            
            await ui_manager.update_all_ui(ctx)
            log_audio_event(guild_id, "autoplay_buffered", f"{len(recommendations)} songs")
            
    except Exception as e:
        logger.error("autoplay_buffer_task", e, guild_id=guild_id)






async def setup(bot):
    await bot.add_cog(MusicCog(bot)) 