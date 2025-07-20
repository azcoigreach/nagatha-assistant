"""
Core slash commands for Nagatha Assistant Discord integration.

This module provides the fundamental slash commands that integrate with 
Nagatha's core functionality like chat, notes, tasks, and system status.
"""

import logging
from typing import Optional

import discord
from discord import app_commands

from .slash_command_manager import BaseSlashCommand, SlashCommandDefinition, SlashCommandOption
from .agent import send_message, start_session

logger = logging.getLogger(__name__)


class ChatSlashCommand(BaseSlashCommand):
    """Slash command for chatting with Nagatha."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="chat",
            description="Chat with Nagatha AI assistant",
            handler=self.execute,
            plugin_name="discord_bot",
            options=[
                SlashCommandOption(
                    name="message",
                    description="Your message to Nagatha",
                    type="string",
                    required=True
                ),
                SlashCommandOption(
                    name="private",
                    description="Send response privately (only you can see it)",
                    type="boolean",
                    required=False
                )
            ]
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the chat command."""
        # Extract parameters from kwargs or interaction data
        message = kwargs.get('message')
        private = kwargs.get('private', False)
        
        if not message and hasattr(interaction, 'data') and 'options' in interaction.data:
            for option in interaction.data['options']:
                if option['name'] == 'message':
                    message = option['value']
                elif option['name'] == 'private':
                    private = option['value']
        
        if not message:
            await interaction.response.send_message("❌ Message is required", ephemeral=True)
            return
        
        # Defer response since AI calls can take time
        await interaction.response.defer(ephemeral=private)
        
        try:
            # Create or get user session
            user_id = str(interaction.user.id)
            session_id = await start_session()
            
            # Get AI response
            response = await send_message(session_id, message)
            
            # Split long responses (Discord limit is 2000 chars)
            if len(response) > 2000:
                # Send first part
                await interaction.followup.send(response[:1997] + "...")
                
                # Send remaining parts
                remaining = response[1997:]
                while remaining:
                    chunk = remaining[:2000]
                    remaining = remaining[2000:]
                    await interaction.followup.send(chunk)
            else:
                await interaction.followup.send(response)
                
        except Exception as e:
            logger.exception(f"Error in chat command: {e}")
            await interaction.followup.send(
                f"❌ Sorry, I encountered an error: {str(e)}", 
                ephemeral=True
            )


class StatusSlashCommand(BaseSlashCommand):
    """Slash command for system status."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="status",
            description="Get Nagatha system status",
            handler=self.execute,
            plugin_name="discord_bot"
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the status command."""
        await interaction.response.defer()
        
        try:
            from ..core.mcp_manager import get_mcp_manager
            from ..core.plugin_manager import get_plugin_manager
            
            # Get MCP status
            try:
                mcp_manager = await get_mcp_manager()
                mcp_status = await mcp_manager.get_status()
                mcp_servers = len(mcp_status.get("servers", {}))
                mcp_tools = sum(len(server.get("tools", [])) for server in mcp_status.get("servers", {}).values())
            except Exception:
                mcp_servers = 0
                mcp_tools = 0
            
            # Get plugin status
            try:
                plugin_manager = get_plugin_manager()
                plugin_status = plugin_manager.get_plugin_status()
                active_plugins = sum(1 for p in plugin_status.values() if p["state"] == "started")
                total_plugins = len(plugin_status)
            except Exception:
                active_plugins = 0
                total_plugins = 0
            
            # Build status response
            response = "🤖 **Nagatha Assistant Status**\n\n"
            response += f"**Discord Bot:** ✅ Online\n"
            response += f"**Active Plugins:** {active_plugins}/{total_plugins}\n"
            response += f"**MCP Servers:** {mcp_servers}\n" 
            response += f"**Available Tools:** {mcp_tools}\n\n"
            
            # Add plugin details
            if plugin_status:
                response += "**Plugin Status:**\n"
                for name, status in plugin_status.items():
                    state_emoji = "✅" if status["state"] == "started" else "❌"
                    response += f"{state_emoji} {name} ({status['state']})\n"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in status command: {e}")
            await interaction.followup.send(
                f"❌ Error getting status: {str(e)}", 
                ephemeral=True
            )


class HelpSlashCommand(BaseSlashCommand):
    """Slash command for help information."""
    
    def __init__(self):
        super().__init__("discord_bot")
    
    def get_command_definition(self) -> SlashCommandDefinition:
        return SlashCommandDefinition(
            name="help",
            description="Get help with Nagatha commands",
            handler=self.execute,
            plugin_name="discord_bot"
        )
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the help command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..core.plugin_manager import get_plugin_manager
            plugin_manager = get_plugin_manager()
            discord_plugin = plugin_manager.get_plugin("discord_bot")
            
            if not discord_plugin or not hasattr(discord_plugin, 'slash_command_manager'):
                await interaction.followup.send("❌ Slash command manager not available")
                return
            
            slash_manager = discord_plugin.slash_command_manager
            commands = slash_manager.get_registered_commands()
            
            # Show general help
            response = "🤖 **Nagatha Assistant Commands**\n\n"
            response += "**Available Slash Commands:**\n"
            for cmd_name in sorted(commands):
                cmd_info = slash_manager.get_command_info(cmd_name)
                if cmd_info:
                    response += f"• `/{cmd_name}` - {cmd_info['description']}\n"
            
            response += "\n**Getting Started:**\n"
            response += "• `/chat <message>` - Chat with Nagatha AI\n"
            response += "• `/status` - Check system status\n"
            response += "• `/help` - Show this help message\n"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in help command: {e}")
            await interaction.followup.send(
                f"❌ Error getting help: {str(e)}"
            )