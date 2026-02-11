"""
Discord UI components for Music Bot
Interactive views and buttons for music control
"""
import discord
from discord import ui, Embed
from typing import Dict, Optional, Any
from config import config
from utils.logger import logger
from audio.manager import audio_manager


class NowPlayingView(ui.View):
    """Interactive controls for currently playing song"""
    
    def __init__(self, ctx, timeout: float = None):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current queue state"""
        self.clear_items()
        
        queue = audio_manager.get_queue(self.guild_id)
        current_idx = audio_manager.guild_current_index.get(self.guild_id, 0)
        
        # Previous button
        prev_enabled = current_idx > 0
        previous_button = ui.Button(
            label="⏮️ Prev", 
            style=discord.ButtonStyle.secondary, 
            disabled=not prev_enabled
        )
        previous_button.callback = self.prev_song
        self.add_item(previous_button)
        
        # Play/Pause button
        if self.ctx.voice_client and self.ctx.voice_client.is_playing():
            play_pause_button = ui.Button(
                label="⏸️ Pause", 
                style=discord.ButtonStyle.primary
            )
        else:
            play_pause_button = ui.Button(
                label="▶️ Play", 
                style=discord.ButtonStyle.success
            )
        play_pause_button.callback = self.play_pause
        self.add_item(play_pause_button)
        
        # Next button
        next_enabled = current_idx < len(queue) - 1
        skip_button = ui.Button(
            label="⏭️ Next", 
            style=discord.ButtonStyle.secondary, 
            disabled=not next_enabled
        )
        skip_button.callback = self.skip
        self.add_item(skip_button)
        
        # Stop button
        stop_button = ui.Button(
            label="⏹️ Stop", 
            style=discord.ButtonStyle.danger
        )
        stop_button.callback = self.stop
        self.add_item(stop_button)
        
        # Repeat button
        repeat_enabled = audio_manager.is_repeat(self.guild_id)
        repeat_button = ui.Button(
            label="🔂 Repeat" if repeat_enabled else "🔁 Repeat",
            style=discord.ButtonStyle.success if repeat_enabled else discord.ButtonStyle.secondary
        )
        repeat_button.callback = self.toggle_repeat
        self.add_item(repeat_button)
    
    async def prev_song(self, interaction: discord.Interaction):
        """Handle previous song button"""
        try:
            if not audio_manager.previous_song(self.guild_id):
                await interaction.response.send_message("❌ No previous song available.", ephemeral=True)
                return
            
            # Stop current song to trigger automatic next song play
            if self.ctx.voice_client and (self.ctx.voice_client.is_playing() or self.ctx.voice_client.is_paused()):
                self.ctx.voice_client.stop()
            
            await interaction.response.send_message("⏮️ Going to previous song", ephemeral=True)
            
            # Update button states
            self.update_buttons()
            try:
                await interaction.edit_original_response(view=self)
            except:
                pass  # Message might be ephemeral
                
        except Exception as e:
            logger.error("prev_song_button", e, guild_id=self.guild_id)
            try:
                await interaction.response.send_message("❌ An error occurred while going to previous song.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred while going to previous song.", ephemeral=True)
    
    async def play_pause(self, interaction: discord.Interaction):
        """Handle play/pause button"""
        try:
            vc = self.ctx.voice_client
            if not vc:
                await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)
                return
            
            if vc.is_playing():
                vc.pause()
                await interaction.response.send_message("⏸️ Paused", ephemeral=True)
            elif vc.is_paused():
                vc.resume()
                await interaction.response.send_message("▶️ Resumed", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
                return
            
            # Update button states
            self.update_buttons()
            
            # Update the parent message with new buttons
            try:
                # Get the message from the UI manager
                from ui.views import ui_manager
                await ui_manager.update_now_playing_buttons(self.ctx, self)
            except:
                pass  # Fallback: don't update if there's an issue
            
        except Exception as e:
            logger.error("play_pause_button", e, guild_id=self.guild_id)
            try:
                await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred.", ephemeral=True)
    
    async def skip(self, interaction: discord.Interaction):
        """Handle skip button"""
        try:
            queue = audio_manager.get_queue(self.guild_id)
            current_idx = audio_manager.guild_current_index.get(self.guild_id, 0)
            
            if not queue or current_idx >= len(queue) - 1:
                await interaction.response.send_message("❌ No next song available.", ephemeral=True)
                return
            
            # Stop current song to trigger automatic next song play
            if self.ctx.voice_client and (self.ctx.voice_client.is_playing() or self.ctx.voice_client.is_paused()):
                self.ctx.voice_client.stop()
            else:
                # If nothing is playing, manually advance to next song
                if audio_manager.next_song(self.guild_id):
                    from commands.music import play_current_song
                    await play_current_song(self.ctx)
            
            await interaction.response.send_message("⏭️ Skipped to next song", ephemeral=True)
            
            # Update button states
            self.update_buttons()
            
        except Exception as e:
            logger.error("skip_button", e, guild_id=self.guild_id)
            try:
                await interaction.response.send_message("❌ An error occurred while skipping.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred while skipping.", ephemeral=True)
    
    async def stop(self, interaction: discord.Interaction):
        """Handle stop button"""
        try:
            if self.ctx.voice_client and (self.ctx.voice_client.is_playing() or self.ctx.voice_client.is_paused()):
                audio_manager.clear_queue(self.guild_id)
                self.ctx.voice_client.stop()
                await interaction.response.send_message("⏹️ Stopped playback and cleared queue.", ephemeral=True)
            else:
                await interaction.response.send_message("Nothing is playing.", ephemeral=True)
                
        except Exception as e:
            logger.error("stop_button", e, guild_id=self.guild_id)
            await interaction.response.send_message("An error occurred while stopping.", ephemeral=True)
    
    async def toggle_repeat(self, interaction: discord.Interaction):
        """Handle repeat toggle button"""
        try:
            current_repeat = audio_manager.is_repeat(self.guild_id)
            new_repeat = not current_repeat
            audio_manager.set_repeat(self.guild_id, new_repeat)
            
            status = "ON" if new_repeat else "OFF"
            emoji = "🔂" if new_repeat else "🔁"
            await interaction.response.send_message(f"{emoji} Repeat is now **{status}**", ephemeral=True)
            
            # Update button states
            self.update_buttons()
            
            # Update the parent message with new buttons
            try:
                from ui.views import ui_manager
                await ui_manager.update_now_playing_buttons(self.ctx, self)
            except:
                pass  # Fallback: don't update if there's an issue
            
        except Exception as e:
            logger.error("repeat_button", e, guild_id=self.guild_id)
            try:
                await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
            except:
                await interaction.followup.send("❌ An error occurred.", ephemeral=True)


class QueueView(ui.View):
    """Paginated queue display with navigation"""
    
    def __init__(self, ctx, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.per_page = config.queue_per_page
        self.current_page = 0
        self.setup_pagination()
        self.update_buttons()
    
    def setup_pagination(self):
        """Setup pagination to show current song's page"""
        queue = audio_manager.get_queue(self.guild_id)
        current_idx = audio_manager.guild_current_index.get(self.guild_id, 0)
        
        if queue and 0 <= current_idx < len(queue):
            self.current_page = current_idx // self.per_page
        
        self.total_pages = max(0, (len(queue) - 1) // self.per_page)
    
    def update_buttons(self):
        """Update pagination buttons"""
        self.clear_items()
        
        # Previous page button
        prev_button = ui.Button(
            label="⬅️ Prev", 
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0)
        )
        prev_button.callback = self.prev_page
        self.add_item(prev_button)
        
        # Next page button  
        next_button = ui.Button(
            label="➡️ Next", 
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.total_pages)
        )
        next_button.callback = self.next_page
        self.add_item(next_button)
        
        # Jump to current song button
        jump_button = ui.Button(
            label="🎵 Current", 
            style=discord.ButtonStyle.primary
        )
        jump_button.callback = self.jump_to_current
        self.add_item(jump_button)
    
    def create_queue_embed(self) -> Embed:
        """Create queue embed for current page"""
        queue = audio_manager.get_queue(self.guild_id)
        current_idx = audio_manager.guild_current_index.get(self.guild_id, 0)
        
        if not queue:
            embed = Embed(
                title="🎵 Queue", 
                description="The queue is empty. Add some songs!",
                color=0x2b2d31
            )
            return embed
        
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(queue))
        
        description_lines = []
        
        for i in range(start_idx, end_idx):
            song = queue[i]
            title = song.title
            
            # Truncate long titles
            if len(title) > 60:
                title = title[:57] + "..."
            
            # Add indicator for currently playing song
            prefix = "▶️ " if i == current_idx else ""
            duration = song.format_duration()
            
            description_lines.append(f"{prefix}**{i + 1}.** [{duration}] {title}")
        
        description = "\n".join(description_lines)
        
        embed = Embed(
            title="🎵 Queue", 
            description=description,
            color=0x2b2d31
        )
        
        # Add footer with page info
        if self.total_pages > 0:
            embed.set_footer(
                text=f"Page {self.current_page + 1}/{self.total_pages + 1} • {len(queue)} songs total"
            )
        else:
            embed.set_footer(text=f"{len(queue)} songs total")
        
        return embed
    
    async def prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_queue_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_queue_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def jump_to_current(self, interaction: discord.Interaction):
        """Jump to page containing currently playing song"""
        queue = audio_manager.get_queue(self.guild_id)
        current_idx = audio_manager.guild_current_index.get(self.guild_id, 0)
        
        if queue and 0 <= current_idx < len(queue):
            target_page = current_idx // self.per_page
            if target_page != self.current_page:
                self.current_page = target_page
                self.update_buttons()
                embed = self.create_queue_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.send_message("Already on the current song's page!", ephemeral=True)
        else:
            await interaction.response.send_message("No song is currently playing.", ephemeral=True)


class UIManager:
    """Manages all UI updates and message handling"""
    
    def __init__(self):
        self.ui_messages: Dict[int, Dict[str, discord.Message]] = {}
    
    async def update_now_playing(self, ctx) -> Optional[discord.Message]:
        """Update or create now playing message"""
        guild_id = ctx.guild.id
        current_song = audio_manager.get_current_song(guild_id)
            # Clean up old message before sending a fresh one
        await self._cleanup_message(guild_id, 'now_playing')
        
        if current_song and ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            embed = Embed(
                title="🎵 Now Playing",
                description=current_song.title,
                color=0x2b2d31
            )
            
            # Autoplay Tip above the embed
            is_autoplay = audio_manager.is_autoplay_enabled(guild_id)
            ap_status = "ON 🔥" if is_autoplay else "OFF 💤"
            tip_content = f"**Tip:** Want non-stop music? Type `!ap` to toggle Autoplay! (Current: {ap_status})"
            
            if current_song.thumbnail:
                embed.set_thumbnail(url=current_song.thumbnail)
            
            if current_song.duration:
                embed.add_field(
                    name="Duration", 
                    value=current_song.format_duration(),
                    inline=True
                )
            
                embed.add_field(
                    name="Duration", 
                    value=current_song.format_duration(),
                    inline=True
                )
            
            # Add Autoplay status and instruction to footer
            is_autoplay = audio_manager.is_autoplay_enabled(guild_id)
            ap_status = "ON" if is_autoplay else "OFF"
            ap_icon = "🔥" if is_autoplay else "💤"
            embed.set_footer(text=f"Autoplay: {ap_status} {ap_icon} • Type !ap or !auto to automatically play related songs!")
            
            view = NowPlayingView(ctx)
            message = await ctx.send(content=tip_content, embed=embed, view=view)
            if guild_id not in self.ui_messages:
                self.ui_messages[guild_id] = {}
            self.ui_messages[guild_id]['now_playing'] = message
            return message
        
        return None
    
    async def update_queue(self, ctx) -> Optional[discord.Message]:
        """Update or create queue message"""
        guild_id = ctx.guild.id
        queue = audio_manager.get_queue(guild_id)
        
        # Clean up old message before sending a fresh one
        await self._cleanup_message(guild_id, 'queue')
        
        if queue:
            view = QueueView(ctx)
            embed = view.create_queue_embed()
            message = await ctx.send(embed=embed, view=view)
            if guild_id not in self.ui_messages:
                self.ui_messages[guild_id] = {}
            self.ui_messages[guild_id]['queue'] = message
            return message
        
        return None
    
    async def update_all_ui(self, ctx):
        """Update both now playing and queue UI"""
        await self.update_now_playing(ctx)
        await self.update_queue(ctx)
    
    async def update_now_playing_buttons(self, ctx, view: NowPlayingView):
        """Update only the buttons of the now playing message"""
        try:
            guild_id = ctx.guild.id
            if guild_id in self.ui_messages and 'now_playing' in self.ui_messages[guild_id]:
                message = self.ui_messages[guild_id]['now_playing']
                view.update_buttons()
                await message.edit(view=view)
        except Exception as e:
            logger.error("update_now_playing_buttons", e, guild_id=ctx.guild.id)
    
    async def _cleanup_message(self, guild_id: int, message_type: str):
        """Clean up old UI message"""
        if guild_id in self.ui_messages and message_type in self.ui_messages[guild_id]:
            try:
                old_message = self.ui_messages[guild_id][message_type]
                await old_message.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                logger.error(f"cleanup_message_{message_type}", e, guild_id=guild_id)
            finally:
                self.ui_messages[guild_id].pop(message_type, None)
    
    async def cleanup_all_messages(self, guild_id: int):
        """Clean up all UI messages for a guild"""
        if guild_id in self.ui_messages:
            for message_type in list(self.ui_messages[guild_id].keys()):
                await self._cleanup_message(guild_id, message_type)
            self.ui_messages.pop(guild_id, None)


# Global UI manager instance
ui_manager = UIManager()