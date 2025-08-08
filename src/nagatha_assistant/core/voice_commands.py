"""
Voice Slash Commands for Nagatha Assistant Discord Integration.

This module provides slash commands for voice channel interactions,
including joining/leaving voice channels and voice status information.
"""

import discord
from discord import app_commands
from typing import Optional

from nagatha_assistant.core.slash_command_manager import BaseSlashCommand, SlashCommandDefinition, SlashCommandOption
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()


class JoinVoiceSlashCommand(BaseSlashCommand):
    """Slash command for joining voice channels."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="join",
            description="Join a voice channel and start voice conversation with Nagatha",
            handler=self.execute,
            plugin_name="discord_bot",
            options=[
                SlashCommandOption(
                    name="channel",
                    description="Voice channel to join (optional - will join your current channel)",
                    type="channel",
                    required=False
                )
            ]
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the join voice command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the Discord bot plugin
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            discord_plugin = plugin_manager.get_plugin("discord_bot")
            
            if not discord_plugin or not hasattr(discord_plugin, 'voice_handler'):
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Get voice channel
            voice_channel = kwargs.get('channel')
            if not voice_channel:
                # Check if user is in a voice channel
                if not interaction.user.voice:
                    await interaction.followup.send(
                        "❌ You need to be in a voice channel or specify one to join. "
                        "Please join a voice channel first, or specify a channel with `/join #channel-name`"
                    )
                    return
                voice_channel = interaction.user.voice.channel
            
            # Verify it's a voice channel
            if not isinstance(voice_channel, discord.VoiceChannel):
                await interaction.followup.send("❌ Please specify a voice channel")
                return
            
            # Check permissions
            if not voice_channel.permissions_for(interaction.guild.me).connect:
                await interaction.followup.send("❌ I don't have permission to join that voice channel")
                return
            
            # Join the voice channel
            success = await discord_plugin.voice_handler.join_voice_channel(
                voice_channel, interaction.guild.id
            )
            
            if success:
                await interaction.followup.send(
                    f"🎤 **Joined voice channel:** {voice_channel.name}\n\n"
                    f"I'm now ready for voice conversation! Just speak naturally and I'll respond. "
                    f"Use `/leave` when you're done."
                )
            else:
                await interaction.followup.send("❌ Failed to join voice channel. Please try again.")
                
        except Exception as e:
            logger.exception(f"Error in join voice command: {e}")
            await interaction.followup.send(f"❌ Error joining voice channel: {str(e)}")


class LeaveVoiceSlashCommand(BaseSlashCommand):
    """Slash command for leaving voice channels."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="leave",
            description="Leave the current voice channel",
            handler=self.execute,
            plugin_name="discord_bot"
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the leave voice command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the Discord bot plugin
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            discord_plugin = plugin_manager.get_plugin("discord_bot")
            
            if not discord_plugin or not hasattr(discord_plugin, 'voice_handler'):
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Check if we're in a voice channel
            is_connected = await discord_plugin.voice_handler.is_in_voice_channel(interaction.guild.id)
            
            if not is_connected:
                await interaction.followup.send("❌ I'm not currently in a voice channel")
                return
            
            # Leave the voice channel
            success = await discord_plugin.voice_handler.leave_voice_channel(interaction.guild.id)
            
            if success:
                await interaction.followup.send("👋 **Left voice channel**\n\nThanks for the conversation!")
            else:
                await interaction.followup.send("❌ Failed to leave voice channel. Please try again.")
                
        except Exception as e:
            logger.exception(f"Error in leave voice command: {e}")
            await interaction.followup.send(f"❌ Error leaving voice channel: {str(e)}")


class VoiceStatusSlashCommand(BaseSlashCommand):
    """Slash command for checking voice status."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="voice-status",
            description="Check voice channel status and capabilities",
            handler=self.execute,
            plugin_name="discord_bot"
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the voice status command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the Discord bot plugin
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            discord_plugin = plugin_manager.get_plugin("discord_bot")
            
            if not discord_plugin or not hasattr(discord_plugin, 'voice_handler'):
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Get voice status
            status = await discord_plugin.voice_handler.get_voice_status(interaction.guild.id)
            
            # Build status message
            response = "🎤 **Voice Status**\n\n"
            
            if status['is_connected']:
                channel_info = status['channel_info']
                response += f"**Connected to:** {channel_info['channel_name']}\n"
                response += f"**Members:** {channel_info['member_count']}\n"
                response += f"**Conversations:** {status['conversation_count']}\n"
            else:
                response += "**Status:** Not connected to any voice channel\n"
            
            response += "\n**Capabilities:**\n"
            response += f"• Speech-to-Text: {'✅' if status['whisper_available'] else '❌'}\n"
            response += f"• Text-to-Speech: {'✅' if status['tts_available'] else '❌'}\n"
            
            response += "\n**Commands:**\n"
            response += "• `/join` - Join a voice channel\n"
            response += "• `/leave` - Leave current voice channel\n"
            response += "• `/voice-status` - Show this status\n"
            
            await interaction.followup.send(response)
                
        except Exception as e:
            logger.exception(f"Error in voice status command: {e}")
            await interaction.followup.send(f"❌ Error getting voice status: {str(e)}")


class SpeakSlashCommand(BaseSlashCommand):
    """Slash command for making Nagatha speak in voice channel."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="speak",
            description="Make Nagatha speak a message in the current voice channel",
            handler=self.execute,
            plugin_name="discord_bot",
            options=[
                SlashCommandOption(
                    name="message",
                    description="Message for Nagatha to speak",
                    type="string",
                    required=True
                )
            ]
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the speak command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the Discord bot plugin
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            discord_plugin = plugin_manager.get_plugin("discord_bot")
            
            if not discord_plugin or not hasattr(discord_plugin, 'voice_handler'):
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Check if we're in a voice channel
            is_connected = await discord_plugin.voice_handler.is_in_voice_channel(interaction.guild.id)
            
            if not is_connected:
                await interaction.followup.send("❌ I need to be in a voice channel first. Use `/join` to join a voice channel.")
                return
            
            # Get message
            message = kwargs.get('message')
            if not message:
                await interaction.followup.send("❌ Please provide a message to speak")
                return
            
            # Make Nagatha speak
            success = await discord_plugin.voice_handler.speak_in_voice_channel(
                message, interaction.guild.id
            )
            
            if success:
                await interaction.followup.send(f"🗣️ **Speaking:** {message}")
            else:
                await interaction.followup.send("❌ Failed to speak the message. Please try again.")
                
        except Exception as e:
            logger.exception(f"Error in speak command: {e}")
            await interaction.followup.send(f"❌ Error speaking message: {str(e)}") 