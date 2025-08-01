"""
Unified Discord Bot for Nagatha Assistant.

This Discord bot connects to the unified Nagatha server and provides
AI assistant capabilities through Discord channels with shared sessions.
"""

import os
import asyncio
import json
import aiohttp
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands

from nagatha_assistant.utils.logger import get_logger
from nagatha_assistant.db_models import DiscordAutoChat
from nagatha_assistant.db import SessionLocal

logger = get_logger(__name__)


# Helper functions for auto-chat management (reused from original)
async def get_auto_chat_setting(channel_id: str, guild_id: Optional[str] = None) -> Optional[DiscordAutoChat]:
    """Get auto-chat setting for a channel."""
    async with SessionLocal() as session:
        from sqlalchemy import select
        stmt = select(DiscordAutoChat).where(DiscordAutoChat.channel_id == str(channel_id))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def set_auto_chat_setting(channel_id: str, guild_id: Optional[str], enabled: bool, user_id: str) -> DiscordAutoChat:
    """Set auto-chat setting for a channel."""
    async with SessionLocal() as session:
        from sqlalchemy import select
        
        # Check if setting already exists
        stmt = select(DiscordAutoChat).where(DiscordAutoChat.channel_id == str(channel_id))
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            # Update existing setting
            setting.enabled = enabled
            setting.enabled_by_user_id = str(user_id)
            setting.updated_at = datetime.now()
        else:
            # Create new setting
            setting = DiscordAutoChat(
                channel_id=str(channel_id),
                guild_id=str(guild_id) if guild_id else None,
                enabled=enabled,
                enabled_by_user_id=str(user_id)
            )
            session.add(setting)
        
        await session.commit()
        await session.refresh(setting)
        return setting


async def is_auto_chat_enabled(channel_id: str) -> bool:
    """Check if auto-chat is enabled for a channel."""
    setting = await get_auto_chat_setting(str(channel_id))
    return setting is not None and setting.enabled


async def should_rate_limit(channel_id: str, max_messages_per_hour: int = 20) -> bool:
    """Check if we should rate limit auto-chat responses."""
    setting = await get_auto_chat_setting(str(channel_id))
    if not setting:
        return True
    
    # Reset daily counter if it's a new day
    now = datetime.now()
    if setting.last_message_at and setting.last_message_at.date() < now.date():
        async with SessionLocal() as session:
            setting.message_count = 0
            setting.last_message_at = now
            session.add(setting)
            await session.commit()
    
    # Check hourly rate limit
    if setting.last_message_at:
        hour_ago = now - timedelta(hours=1)
        if setting.last_message_at > hour_ago and setting.message_count >= max_messages_per_hour:
            return True
    
    return False


async def update_auto_chat_usage(channel_id: str):
    """Update auto-chat usage statistics."""
    async with SessionLocal() as session:
        from sqlalchemy import select
        
        stmt = select(DiscordAutoChat).where(DiscordAutoChat.channel_id == str(channel_id))
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.message_count += 1
            setting.last_message_at = datetime.now()
            session.add(setting)
            await session.commit()


class UnifiedDiscordBot(commands.Bot):
    """
    Discord bot that connects to the unified Nagatha server.
    """
    
    def __init__(self, server_config: Dict[str, Any], *args, **kwargs):
        """Initialize the unified Discord bot."""
        super().__init__(*args, **kwargs)
        self.server_config = server_config
        # REST API runs on main server port + 1
        rest_port = server_config['port'] + 1
        self.server_url = f"http://{server_config['host']}:{rest_port}"
        self.http_session: Optional[aiohttp.ClientSession] = None
        
    async def setup_hook(self):
        """Set up the bot when it starts."""
        self.http_session = aiohttp.ClientSession()
        logger.info("Unified Discord bot setup complete")
    
    async def close(self):
        """Clean up when the bot shuts down."""
        if self.http_session:
            await self.http_session.close()
        await super().close()
    
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Unified Discord bot logged in as {self.user}")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Sync slash commands
        try:
            await self.tree.sync()
            logger.info("Slash commands synced")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
    
    async def on_disconnect(self):
        """Called when the bot disconnects."""
        logger.warning("Unified Discord bot disconnected")
    
    async def on_error(self, event_name: str, *args, **kwargs):
        """Called when an error occurs."""
        logger.error(f"Discord bot error in {event_name}: {args}")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Process commands first
        await self.process_commands(message)
        
        # Handle auto-chat if enabled
        if await is_auto_chat_enabled(str(message.channel.id)):
            # Check rate limiting
            if await should_rate_limit(str(message.channel.id)):
                return
            
            # Process auto-chat message
            await self._handle_auto_chat_message(message)
    
    async def _handle_auto_chat_message(self, message: discord.Message):
        """Handle auto-chat message processing."""
        try:
            # Create user ID for Discord
            user_id = f"discord:{message.author.id}"
            
            # Prepare interface context
            interface_context = {
                "interface": "discord",
                "channel_id": str(message.channel.id),
                "guild_id": str(message.guild.id) if message.guild else None,
                "message_id": str(message.id),
                "author": {
                    "id": str(message.author.id),
                    "name": message.author.display_name,
                    "bot": message.author.bot
                }
            }
            
            # Send message to unified server
            response = await self._send_message_to_server(
                message=message.content,
                user_id=user_id,
                interface_context=interface_context
            )
            
            # Update usage statistics
            await update_auto_chat_usage(str(message.channel.id))
            
            # Send response to Discord
            await self._send_long_message(message.channel, response)
            
            logger.info(f"Auto-chat response sent in channel {message.channel.id}")
            
        except Exception as e:
            logger.exception(f"Error in auto-chat message handling: {e}")
            # Send error message to channel
            try:
                await message.channel.send("❌ Sorry, I encountered an error processing your message.")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    async def _send_message_to_server(self, message: str, user_id: str, interface_context: Dict[str, Any]) -> str:
        """Send a message to the unified server and get response."""
        if not self.http_session:
            raise Exception("HTTP session not available")
        
        try:
            # Send message to server
            async with self.http_session.post(
                f"{self.server_url}/process_message",
                json={
                    "message": message,
                    "user_id": user_id,
                    "interface": "discord",
                    "interface_context": interface_context
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "No response received")
                else:
                    error_text = await response.text()
                    raise Exception(f"Server responded with status {response.status}: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Failed to connect to server: {e}")
    
    async def _send_long_message(self, channel, content: str):
        """Send a message that might be longer than Discord's limit."""
        # Discord limit is 2000 characters
        if len(content) <= 2000:
            await channel.send(content)
        else:
            # Split long messages
            parts = []
            current_part = ""
            
            # Split by lines first to avoid breaking words
            lines = content.split('\n')
            for line in lines:
                # If adding this line would exceed limit, send current part
                if len(current_part) + len(line) + 1 > 1950:  # Leave some margin
                    if current_part:
                        parts.append(current_part)
                        current_part = line
                    else:
                        # Line itself is too long, split it
                        while len(line) > 1950:
                            parts.append(line[:1950])
                            line = line[1950:]
                        current_part = line
                else:
                    if current_part:
                        current_part += '\n' + line
                    else:
                        current_part = line
            
            # Add the last part
            if current_part:
                parts.append(current_part)
            
            # Send all parts
            for i, part in enumerate(parts):
                if i == 0:
                    await channel.send(part)
                else:
                    await channel.send(f"**(continued...)**\n{part}")


class UnifiedDiscordBotManager:
    """
    Manager for the unified Discord bot.
    """
    
    def __init__(self, server_config: Dict[str, Any]):
        """Initialize the Discord bot manager."""
        self.server_config = server_config
        self.bot: Optional[UnifiedDiscordBot] = None
        self.is_running = False
        self._bot_task: Optional[asyncio.Task] = None
        
    async def start_bot(self, token: str) -> str:
        """Start the Discord bot."""
        if self.is_running:
            return "Bot is already running"
        
        try:
            # Create bot instance
            intents = discord.Intents.default()
            intents.message_content = True
            intents.guilds = True
            
            self.bot = UnifiedDiscordBot(
                server_config=self.server_config,
                command_prefix="!",
                intents=intents
            )
            
            # Register slash commands
            await self._register_slash_commands()
            
            # Start the bot
            self._bot_task = asyncio.create_task(self._run_bot(token))
            self.is_running = True
            
            logger.info("Unified Discord bot started")
            return "Discord bot started successfully"
            
        except Exception as e:
            logger.exception(f"Failed to start Discord bot: {e}")
            return f"Failed to start Discord bot: {e}"
    
    async def stop_bot(self) -> str:
        """Stop the Discord bot."""
        if not self.is_running:
            return "Bot is not running"
        
        try:
            if self.bot:
                await self.bot.close()
            
            if self._bot_task:
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    pass
            
            self.is_running = False
            self.bot = None
            self._bot_task = None
            
            logger.info("Unified Discord bot stopped")
            return "Discord bot stopped successfully"
            
        except Exception as e:
            logger.exception(f"Failed to stop Discord bot: {e}")
            return f"Failed to stop Discord bot: {e}"
    
    async def get_bot_status(self) -> Dict[str, Any]:
        """Get the bot status."""
        if not self.is_running or not self.bot:
            return {
                "running": False,
                "connected_guilds": 0,
                "latency": None
            }
        
        return {
            "running": True,
            "connected_guilds": len(self.bot.guilds),
            "latency": self.bot.latency,
            "user": str(self.bot.user) if self.bot.user else None
        }
    
    async def _register_slash_commands(self):
        """Register slash commands with the bot."""
        if not self.bot:
            return
        
        @self.bot.tree.command(name="chat", description="Chat with Nagatha AI assistant")
        @app_commands.describe(
            message="Your message to Nagatha",
            private="Send response privately (only you can see it)"
        )
        async def chat_command(interaction: discord.Interaction, message: str, private: bool = False):
            await self._handle_chat_command(interaction, message, private)
        
        @self.bot.tree.command(name="status", description="Get Nagatha system status")
        async def status_command(interaction: discord.Interaction):
            await self._handle_status_command(interaction)
        
        @self.bot.tree.command(name="help", description="Get help with Nagatha commands")
        async def help_command(interaction: discord.Interaction):
            await self._handle_help_command(interaction)
        
        @self.bot.tree.command(name="auto-chat", description="Enable or disable auto-chat mode for this channel")
        @app_commands.describe(
            action="Turn auto-chat on or off",
        )
        @app_commands.choices(action=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
            app_commands.Choice(name="status", value="status")
        ])
        async def auto_chat_command(interaction: discord.Interaction, action: str):
            await self._handle_auto_chat_command(interaction, action)
    
    async def _handle_chat_command(self, interaction: discord.Interaction, message: str, private: bool = False):
        """Handle the /chat slash command."""
        # Defer response since AI calls can take time
        await interaction.response.defer(ephemeral=private)
        
        try:
            # Create user ID for Discord
            user_id = f"discord:{interaction.user.id}"
            
            # Prepare interface context
            interface_context = {
                "interface": "discord",
                "channel_id": str(interaction.channel_id),
                "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
                "author": {
                    "id": str(interaction.user.id),
                    "name": interaction.user.display_name,
                    "bot": interaction.user.bot
                }
            }
            
            # Send message to unified server
            response = await self.bot._send_message_to_server(
                message=message,
                user_id=user_id,
                interface_context=interface_context
            )
            
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
    
    async def _handle_status_command(self, interaction: discord.Interaction):
        """Handle the /status slash command."""
        await interaction.response.defer()
        
        try:
            # Get server status
            if not self.bot or not self.bot.http_session:
                await interaction.followup.send("❌ Cannot connect to server")
                return
            
            async with self.bot.http_session.get(f"{self.bot.server_url}/status") as response:
                if response.status == 200:
                    status_data = await response.json()
                    
                    # Build status response
                    response_text = "🤖 **Nagatha Assistant Status**\n\n"
                    response_text += f"**Discord Bot:** ✅ Online\n"
                    response_text += f"**Connected Guilds:** {len(self.bot.guilds)}\n"
                    response_text += f"**Bot Latency:** {self.bot.latency:.2f}ms\n"
                    response_text += f"**Server:** {self.server_config['host']}:{self.server_config['port']}\n\n"
                    
                    # Add server stats if available
                    if "server" in status_data:
                        server_stats = status_data["server"]
                        response_text += f"**Server Uptime:** {server_stats.get('uptime_seconds', 0):.1f}s\n"
                        response_text += f"**Active Sessions:** {status_data.get('sessions', {}).get('active_sessions', 0)}\n"
                        response_text += f"**Total Users:** {status_data.get('sessions', {}).get('total_users', 0)}\n"
                    
                    await interaction.followup.send(response_text)
                else:
                    await interaction.followup.send("❌ Could not get server status")
            
        except Exception as e:
            logger.exception(f"Error in status command: {e}")
            await interaction.followup.send(
                f"❌ Error getting status: {str(e)}", 
                ephemeral=True
            )
    
    async def _handle_help_command(self, interaction: discord.Interaction):
        """Handle the /help slash command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Build help response
            response = "🤖 **Nagatha Assistant Commands**\n\n"
            response += "**Available Slash Commands:**\n"
            response += "• `/chat <message> [private]` - Chat with Nagatha AI assistant\n"
            response += "• `/auto-chat <on|off|status>` - Enable/disable auto-chat mode for this channel\n"
            response += "• `/status` - Get system status and server information\n" 
            response += "• `/help` - Show this help message\n\n"
            
            response += "**Auto-Chat Mode:**\n"
            response += "When enabled, Nagatha will automatically respond to messages in this channel.\n"
            response += "Use `/auto-chat on` to enable or `/auto-chat off` to disable.\n\n"
            
            response += "**Note:** This bot is connected to the unified Nagatha server and shares sessions with other interfaces."
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in help command: {e}")
            await interaction.followup.send(
                f"❌ Error showing help: {str(e)}", 
                ephemeral=True
            )
    
    async def _handle_auto_chat_command(self, interaction: discord.Interaction, action: str):
        """Handle the /auto-chat slash command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            channel_id = str(interaction.channel_id)
            guild_id = str(interaction.guild_id) if interaction.guild_id else None
            user_id = str(interaction.user.id)
            
            if action == "on":
                # Enable auto-chat
                await set_auto_chat_setting(channel_id, guild_id, True, user_id)
                await interaction.followup.send(
                    f"✅ Auto-chat enabled for this channel!\n"
                    f"Nagatha will now automatically respond to messages here.",
                    ephemeral=True
                )
                
            elif action == "off":
                # Disable auto-chat
                await set_auto_chat_setting(channel_id, guild_id, False, user_id)
                await interaction.followup.send(
                    f"❌ Auto-chat disabled for this channel.\n"
                    f"Use `/chat` commands to interact with Nagatha.",
                    ephemeral=True
                )
                
            elif action == "status":
                # Check auto-chat status
                is_enabled = await is_auto_chat_enabled(channel_id)
                status_text = "enabled" if is_enabled else "disabled"
                status_emoji = "✅" if is_enabled else "❌"
                
                await interaction.followup.send(
                    f"{status_emoji} Auto-chat is currently **{status_text}** for this channel.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.exception(f"Error in auto-chat command: {e}")
            await interaction.followup.send(
                f"❌ Error managing auto-chat: {str(e)}", 
                ephemeral=True
            )
    
    async def _run_bot(self, token: str):
        """Run the Discord bot."""
        try:
            await self.bot.start(token)
        except Exception as e:
            logger.exception(f"Error running Discord bot: {e}")
            self.is_running = False 