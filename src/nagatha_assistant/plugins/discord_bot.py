"""
Discord Bot Plugin for Nagatha Assistant.

A Discord bot integration that allows Nagatha to interact with Discord servers,
providing AI assistant capabilities through Discord channels.
"""

import os
import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands

from nagatha_assistant.core.plugin import SimplePlugin, PluginConfig, PluginCommand
from nagatha_assistant.core.event import Event, StandardEventTypes, create_system_event
from nagatha_assistant.core.slash_command_manager import SlashCommandManager
from nagatha_assistant.core.slash_commands import ChatSlashCommand, StatusSlashCommand, HelpSlashCommand
from nagatha_assistant.core.voice_commands import JoinVoiceSlashCommand, LeaveVoiceSlashCommand, VoiceStatusSlashCommand, SpeakSlashCommand
from nagatha_assistant.core.voice_handler import VoiceHandler
from nagatha_assistant.utils.logger import setup_logger_with_env_control, get_logger
from nagatha_assistant.db_models import DiscordAutoChat
from nagatha_assistant.db import SessionLocal

logger = setup_logger_with_env_control()


# Helper functions for auto-chat management
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


async def should_rate_limit(channel_id: str, max_messages_per_hour: int = None) -> bool:
    """Check if we should rate limit auto-chat responses."""
    # Get rate limit from environment or use default
    if max_messages_per_hour is None:
        import os
        # Check if rate limiting is disabled entirely
        if os.getenv('DISCORD_DISABLE_RATE_LIMIT', '').lower() in ('true', '1', 'yes', 'on'):
            return False
        max_messages_per_hour = int(os.getenv('DISCORD_AUTO_CHAT_RATE_LIMIT', '100'))
    
    setting = await get_auto_chat_setting(str(channel_id))
    if not setting:
        return True
    
    # Reset daily counter if it's a new day
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    if setting.last_message_at:
        # Ensure both datetimes are timezone-aware for comparison
        if setting.last_message_at.tzinfo is None:
            # If last_message_at is naive, assume UTC
            last_message_at = setting.last_message_at.replace(tzinfo=timezone.utc)
        else:
            last_message_at = setting.last_message_at
        
        if last_message_at.date() < now.date():
            async with SessionLocal() as session:
                setting.message_count = 0
                setting.last_message_at = now
                session.add(setting)
                await session.commit()
    
    # Check hourly rate limit
    if setting.last_message_at:
        # Ensure both datetimes are timezone-aware for comparison
        if setting.last_message_at.tzinfo is None:
            # If last_message_at is naive, assume UTC
            last_message_at = setting.last_message_at.replace(tzinfo=timezone.utc)
        else:
            last_message_at = setting.last_message_at
        
        hour_ago = now - timedelta(hours=1)
        if last_message_at > hour_ago and setting.message_count >= max_messages_per_hour:
            logger.debug(f"Rate limiting auto-chat in channel {channel_id}: {setting.message_count}/{max_messages_per_hour} messages in the last hour")
            return True
    
    return False


async def update_auto_chat_usage(channel_id: str):
    """Update auto-chat usage statistics."""
    async with SessionLocal() as session:
        from sqlalchemy import select
        from datetime import datetime, timezone
        
        stmt = select(DiscordAutoChat).where(DiscordAutoChat.channel_id == str(channel_id))
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.message_count += 1
            setting.last_message_at = datetime.now(timezone.utc)
            await session.commit()


class NagathaDiscordBot(commands.Bot):
    """
    Custom Discord bot class for Nagatha.
    
    This extends the discord.py Bot class to integrate with Nagatha's
    event system and provide AI assistant functionality.
    """
    
    def __init__(self, discord_plugin: 'DiscordBotPlugin', *args, **kwargs):
        """Initialize the Discord bot with reference to the plugin."""
        self.discord_plugin = discord_plugin
        super().__init__(*args, **kwargs)
    
    async def on_ready(self):
        """Called when the bot has successfully connected to Discord."""
        logger.info(f'Discord bot logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'Connected to {len(self.guilds)} guild(s): {[guild.name for guild in self.guilds]}')
        
        # Debug: Check what commands are registered
        registered_commands = [cmd.name for cmd in self.tree.get_commands()]
        logger.info(f"Registered commands in tree: {registered_commands}")
        
        # Sync slash commands
        try:
            # Sync globally or to specific guild
            guild_id = self.discord_plugin.guild_id
            logger.info(f"Attempting to sync commands with guild_id: {guild_id}")
            
            if guild_id:
                guild = self.get_guild(int(guild_id))
                if guild:
                    logger.info(f"Found guild: {guild.name} (ID: {guild.id})")
                    synced = await self.tree.sync(guild=guild)
                    logger.info(f"Synced {len(synced)} slash commands to guild {guild.name}")
                    for cmd in synced:
                        logger.info(f"  - Synced command: {cmd.name}")
                else:
                    logger.warning(f"Guild with ID {guild_id} not found, syncing globally")
                    synced = await self.tree.sync()
                    logger.info(f"Synced {len(synced)} slash commands globally")
            else:
                logger.info("No guild_id specified, syncing globally")
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands globally")
                for cmd in synced:
                    logger.info(f"  - Synced command: {cmd.name}")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Publish bot ready event
        event = create_system_event(
            "discord.bot.ready",
            {
                "bot_id": self.user.id,
                "bot_name": self.user.name,
                "guilds": [guild.name for guild in self.guilds]
            },
            source="discord_bot_plugin"
        )
        await self.discord_plugin.publish_event(event)
    
    async def on_disconnect(self):
        """Called when the bot disconnects from Discord."""
        logger.warning("Discord bot disconnected")
        
        # Publish bot disconnect event
        event = create_system_event(
            "discord.bot.disconnect",
            {"reason": "Connection lost"},
            source="discord_bot_plugin"
        )
        await self.discord_plugin.publish_event(event)
    
    async def on_error(self, event_name: str, *args, **kwargs):
        """Called when an error occurs in an event handler."""
        logger.error(f"Discord bot error in event {event_name}: {args}")
        
        # Publish bot error event
        event = create_system_event(
            "discord.bot.error",
            {
                "event_name": event_name,
                "error_args": str(args)
            },
            source="discord_bot_plugin"
        )
        await self.discord_plugin.publish_event(event)
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        Handle voice state updates (users joining/leaving voice channels).
        
        This allows Nagatha to respond to voice channel activity and
        potentially handle voice conversations.
        """
        # Don't respond to our own voice state changes
        if member == self.user:
            return
        
        # Check if this affects a voice channel we're in
        if hasattr(self.discord_plugin, 'voice_handler') and self.discord_plugin.voice_handler:
            voice_handler = self.discord_plugin.voice_handler
            
            # Check if we're in the same voice channel
            if before.channel and voice_handler.voice_clients.get(member.guild.id):
                our_channel = voice_handler.voice_clients[member.guild.id].channel
                if before.channel.id == our_channel.id:
                    # User left our voice channel
                    logger.info(f"User {member.name} left voice channel {before.channel.name}")
                    
                    # If we're the only one left, consider leaving
                    if len(before.channel.members) <= 1:  # Only us or empty
                        logger.info("Voice channel is empty, considering leaving")
                        # You could add logic here to auto-leave after a delay
                
                elif after.channel and after.channel.id == our_channel.id:
                    # User joined our voice channel
                    logger.info(f"User {member.name} joined voice channel {after.channel.name}")
                    
                    # Welcome message or other interaction
                    if len(after.channel.members) == 2:  # Just us and the new user
                        logger.info("First user joined our voice channel")
            
            # Handle voice activity
            if hasattr(voice_handler, 'voice_listener'):
                # Check if user is speaking (not muted and not deafened)
                speaking = after.self_mute is False and after.self_deaf is False
                await voice_handler.handle_voice_activity(member.id, speaking, member.guild.id)
        
        # Publish voice state event for other systems
        event = create_system_event(
            "discord.voice.state_update",
            {
                "member_id": member.id,
                "member_name": member.name,
                "guild_id": member.guild.id if member.guild else None,
                "before_channel_id": before.channel.id if before.channel else None,
                "before_channel_name": before.channel.name if before.channel else None,
                "after_channel_id": after.channel.id if after.channel else None,
                "after_channel_name": after.channel.name if after.channel else None,
                "action": "joined" if not before.channel and after.channel else "left" if before.channel and not after.channel else "moved"
            },
            source="discord_bot_plugin"
        )
        await self.discord_plugin.publish_event(event)
    
    async def on_voice_packet(self, user_id: int, data: bytes):
        """Handle incoming voice packets from users."""
        try:
            if hasattr(self.discord_plugin, 'voice_handler') and self.discord_plugin.voice_handler:
                voice_handler = self.discord_plugin.voice_handler
                
                # Find the guild ID for this user
                guild_id = None
                for gid, voice_client in voice_handler.voice_clients.items():
                    if voice_client.channel:
                        # Check if user is in this voice channel
                        for member in voice_client.channel.members:
                            if member.id == user_id:
                                guild_id = gid
                                break
                        if guild_id:
                            break
                
                if guild_id:
                    await voice_handler.handle_voice_packet(user_id, data, guild_id)
                    
        except Exception as e:
            logger.error(f"Error handling voice packet: {e}")
    
    async def on_message(self, message: discord.Message):
        """
        Handle incoming Discord messages.
        
        This is where we can integrate with Nagatha's conversation system
        to provide AI responses to Discord messages.
        """
        # Don't respond to ourselves or other bots
        if message.author == self.user or message.author.bot:
            return
        
        # Skip system messages
        if message.type != discord.MessageType.default:
            return
        
        # Log the message
        logger.debug(f"Discord message from {message.author}: {message.content}")
        
        # Publish message event for other systems to handle
        event = create_system_event(
            "discord.message.received",
            {
                "author_id": message.author.id,
                "author_name": str(message.author),
                "channel_id": message.channel.id,
                "channel_name": getattr(message.channel, 'name', 'DM'),
                "guild_id": message.guild.id if message.guild else None,
                "guild_name": message.guild.name if message.guild else None,
                "content": message.content,
                "message_id": message.id
            },
            source="discord_bot_plugin"
        )
        await self.discord_plugin.publish_event(event)
        
        # Check if auto-chat is enabled for this channel
        try:
            if await is_auto_chat_enabled(str(message.channel.id)):
                # Check rate limiting
                if await should_rate_limit(str(message.channel.id)):
                    logger.debug(f"Rate limiting auto-chat in channel {message.channel.id}")
                    return
                
                # Process the message as an auto-chat
                await self._handle_auto_chat_message(message)
            
        except Exception as e:
            logger.error(f"Error in auto-chat handling: {e}")
        
        # Process commands (this will handle slash commands and prefix commands)
        await self.process_commands(message)
    
    async def _handle_auto_chat_message(self, message: discord.Message):
        """Handle auto-chat message processing."""
        try:
            # Use the unified server's session management for Discord channels
            from nagatha_assistant.server.core_server import get_unified_server
            
            # Get unified server instance
            server = await get_unified_server()
            
            # Create user ID and interface context for Discord
            user_id = f"discord:{message.author.id}"
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
            
            # Process message through unified server (this handles session management properly)
            response = await server.process_message(
                message=message.content,
                user_id=user_id,
                interface="discord",
                interface_context=interface_context
            )
            
            # Update usage statistics
            await update_auto_chat_usage(str(message.channel.id))
            
            # Send response to Discord
            await self._send_long_message(message.channel, response)
            
            # Speak the response in voice channel if linked
            if hasattr(self.discord_plugin, 'voice_handler') and self.discord_plugin.voice_handler:
                await self.discord_plugin.voice_handler.speak_text_channel_response(
                    str(message.channel.id), response
                )
            
            logger.info(f"Auto-chat response sent in channel {message.channel.id}")
            
        except Exception as e:
            logger.exception(f"Error in auto-chat message handling: {e}")
            # Send error message to channel
            try:
                await message.channel.send("❌ Sorry, I encountered an error processing your message.")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
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


class DiscordBotPlugin(SimplePlugin):
    """
    Discord bot plugin for Nagatha Assistant.
    
    This plugin provides Discord bot functionality, allowing Nagatha
    to connect to Discord servers and interact with users through
    Discord channels.
    """
    
    PLUGIN_NAME = "discord_bot"
    PLUGIN_VERSION = "1.0.0"
    
    def __init__(self, config: PluginConfig):
        """Initialize the Discord bot plugin."""
        super().__init__(config)
        
        # Discord configuration
        self.token = os.getenv('DISCORD_BOT_TOKEN')
        self.guild_id = os.getenv('DISCORD_GUILD_ID')
        self.command_prefix = os.getenv('DISCORD_COMMAND_PREFIX', self.config.config.get('command_prefix', '!'))
        
        # Bot state
        self.bot: Optional[NagathaDiscordBot] = None
        self.is_running = False
        self._bot_task: Optional[asyncio.Task] = None
        
        # Slash command management
        self.slash_command_manager: Optional[SlashCommandManager] = None
        
        # Voice handler
        self.voice_handler: Optional[VoiceHandler] = None
        
    async def setup(self) -> None:
        """Setup the Discord bot plugin by registering commands and handlers."""
        
        # Register plugin commands
        start_command = PluginCommand(
            name="discord_start",
            description="Start the Discord bot",
            handler=self.start_discord_bot,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
        
        stop_command = PluginCommand(
            name="discord_stop", 
            description="Stop the Discord bot",
            handler=self.stop_discord_bot,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
        
        status_command = PluginCommand(
            name="discord_status",
            description="Get Discord bot status",
            handler=self.get_discord_status,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
        
        sync_command = PluginCommand(
            name="discord_sync",
            description="Sync Discord slash commands",
            handler=self.sync_discord_commands,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "guild_id": {
                        "type": "string",
                        "description": "Guild ID to sync to (optional, syncs globally if not provided)"
                    }
                },
                "required": []
            }
        )
        
        # Register with the plugin manager
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        plugin_manager.register_command(start_command)
        plugin_manager.register_command(stop_command)
        plugin_manager.register_command(status_command)
        plugin_manager.register_command(sync_command)
        
        # Subscribe to system events
        self.subscribe_to_events(
            "system.*",
            self.handle_system_event
        )
        
        # Validate Discord configuration
        if not self.token:
            logger.warning("Discord bot token not configured - Discord functionality disabled")
        else:
            # Auto-start if configured
            auto_start = self.config.config.get('auto_start', False)
            if auto_start:
                logger.info("Auto-starting Discord bot...")
                await self.start_discord_bot()
        
        logger.info("Discord bot plugin setup complete")
    
    async def teardown(self) -> None:
        """Cleanup the Discord bot plugin."""
        await self.stop_discord_bot()
        logger.info("Discord bot plugin shutdown complete")
    
    async def start_discord_bot(self, **kwargs) -> str:
        """
        Start the Discord bot.
        
        Returns:
            Status message about the bot startup
        """
        if self.is_running:
            return "Discord bot is already running"
        
        if not self.token:
            return "Discord bot token not configured"
        
        try:
            logger.info("Starting Discord bot initialization...")
            
            # Configure Discord intents
            intents = discord.Intents.default()
            intents.message_content = True  # Required for message content access
            intents.voice_states = True  # Required for voice channel events
            intents.guilds = True  # Required for guild information
            intents.members = True  # Required for voice features
            logger.debug("Discord intents configured")
            
            # Create bot instance
            self.bot = NagathaDiscordBot(
                self,
                command_prefix=self.command_prefix,
                intents=intents,
                help_command=None  # Disable default help command
            )
            logger.debug("Discord bot instance created")
            
            # Initialize slash command manager
            self.slash_command_manager = SlashCommandManager(self.bot)
            logger.debug("Slash command manager initialized")
            
            # Initialize voice handler
            self.voice_handler = VoiceHandler(self)
            logger.debug("Voice handler initialized")
            
            # Register core slash commands
            # await self._register_core_slash_commands()
            
            # Register legacy slash commands for backward compatibility
            self._register_legacy_slash_commands()
            
            # Add legacy prefix commands for backward compatibility
            @self.bot.command(name='ping')
            async def ping(ctx):
                """Respond with pong to test bot connectivity."""
                await ctx.send('Pong! Nagatha is online.')
            
            @self.bot.command(name='hello')
            async def hello(ctx):
                """Say hello to users."""
                await ctx.send(f'Hello {ctx.author.mention}! I\'m Nagatha, your AI assistant.')
            
            logger.debug("Discord bot commands registered")
            
            # Start the bot in a background task
            self._bot_task = asyncio.create_task(self._run_bot())
            
            # Set up task completion callback
            def task_done_callback(task):
                try:
                    task.result()
                except asyncio.CancelledError:
                    logger.info("Discord bot task was cancelled")
                except Exception as e:
                    logger.error(f"Discord bot task failed: {e}")
                finally:
                    self.is_running = False
            
            self._bot_task.add_done_callback(task_done_callback)
            
            self.is_running = True
            logger.info("Discord bot started successfully")
            return "Discord bot started successfully"
            
        except Exception as e:
            logger.exception(f"Failed to start Discord bot: {e}")
            return f"Failed to start Discord bot: {str(e)}"
    
    async def stop_discord_bot(self, **kwargs) -> str:
        """
        Stop the Discord bot.
        
        Returns:
            Status message about the bot shutdown
        """
        if not self.is_running:
            return "Discord bot is not running"
        
        try:
            self.is_running = False
            
            # Close the bot connection
            if self.bot:
                await self.bot.close()
            
            # Cancel the bot task
            if self._bot_task:
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    pass
            
            # Publish bot stop event
            event = create_system_event(
                "discord.bot.stopped",
                {},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
            
            logger.info("Discord bot stopped")
            return "Discord bot stopped successfully"
            
        except Exception as e:
            logger.error(f"Error stopping Discord bot: {e}")
            return f"Error stopping Discord bot: {str(e)}"
    
    async def get_discord_status(self, **kwargs) -> str:
        """
        Get the current status of the Discord bot.
        
        Returns:
            Status information about the Discord bot
        """
        if not self.token:
            return "Discord bot: Not configured (missing token)"
        
        if not self.is_running:
            return "Discord bot: Stopped"
        
        if self.bot and hasattr(self.bot, 'user') and self.bot.user:
            guild_count = len(self.bot.guilds)
            return f"Discord bot: Running as {self.bot.user.name} in {guild_count} servers"
        else:
            return "Discord bot: Starting..."
    
    async def sync_discord_commands(self, **kwargs) -> str:
        """
        Sync Discord slash commands.
        
        Args:
            guild_id (optional): Guild ID to sync to. If not provided, syncs globally.
            
        Returns:
            Status message about the sync operation
        """
        if not self.is_running:
            return "Discord bot is not running. Start it first with `discord_start`."
        
        if not self.bot:
            return "Discord bot not initialized. Please start the bot first."
        
        try:
            guild_id = kwargs.get('guild_id')
            
            # Convert guild_id to int if provided
            guild_id_int = None
            if guild_id:
                try:
                    guild_id_int = int(guild_id)
                except ValueError:
                    return f"Invalid guild ID: {guild_id}. Must be a number."
            
            # Sync commands
            synced_count = await self.sync_slash_commands(guild_id_int)
            
            if guild_id_int:
                guild = self.bot.get_guild(guild_id_int)
                guild_name = guild.name if guild else f"Guild {guild_id_int}"
                return f"✅ Synced {synced_count} slash commands to guild: {guild_name}"
            else:
                return f"✅ Synced {synced_count} slash commands globally"
                
        except Exception as e:
            logger.error(f"Error syncing Discord commands: {e}")
            return f"❌ Error syncing commands: {str(e)}"
    
    async def _register_core_slash_commands(self) -> None:
        """Register core slash commands using the SlashCommandManager."""
        if not self.slash_command_manager:
            logger.error("Slash command manager not initialized")
            return
        
        try:
            # Register core slash commands
            core_commands = [
                ChatSlashCommand(),
                StatusSlashCommand(),
                HelpSlashCommand(),
                JoinVoiceSlashCommand(),
                LeaveVoiceSlashCommand(),
                VoiceStatusSlashCommand(),
                SpeakSlashCommand()
            ]
            
            for command in core_commands:
                success = self.slash_command_manager.register_command(command)
                if success:
                    logger.info(f"Registered core slash command: {command.get_command_definition().name}")
                else:
                    logger.warning(f"Failed to register core slash command: {command.get_command_definition().name}")
            
            logger.info("Core slash commands registration complete")
            
        except Exception as e:
            logger.error(f"Error registering core slash commands: {e}")

    def _register_legacy_slash_commands(self) -> None:
        """Register legacy slash commands using discord.py app_commands for backward compatibility."""
        if not self.bot:
            return
        
        try:
            # Chat command
            @app_commands.command(name="chat", description="Chat with Nagatha AI assistant")
            @app_commands.describe(
                message="Your message to Nagatha",
                private="Send response privately (only you can see it)"
            )
            async def chat_command(interaction: discord.Interaction, message: str, private: bool = False):
                await self._handle_chat_command(interaction, message, private)
            
            # Status command  
            @app_commands.command(name="status", description="Get Nagatha system status")
            async def status_command(interaction: discord.Interaction):
                await self._handle_status_command(interaction)
            
            # Help command
            @app_commands.command(name="help", description="Get help with Nagatha commands")
            async def help_command(interaction: discord.Interaction):
                await self._handle_help_command(interaction)
            
            # Auto-chat command
            @app_commands.command(name="auto-chat", description="Enable or disable auto-chat mode for this channel")
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
            
            # Voice commands
            @app_commands.command(name="join", description="Join a voice channel and start voice conversation with Nagatha")
            @app_commands.describe(
                channel="Voice channel to join (optional - will join your current channel)"
            )
            async def join_command(interaction: discord.Interaction, channel: discord.VoiceChannel = None):
                await self._handle_join_voice_command(interaction, channel)
            
            @app_commands.command(name="leave", description="Leave the current voice channel")
            async def leave_command(interaction: discord.Interaction):
                await self._handle_leave_voice_command(interaction)
            
            @app_commands.command(name="voice-status", description="Check voice channel status and capabilities")
            async def voice_status_command(interaction: discord.Interaction):
                await self._handle_voice_status_command(interaction)
            
            @app_commands.command(name="speak", description="Make Nagatha speak a message in the current voice channel")
            @app_commands.describe(
                message="Message for Nagatha to speak"
            )
            async def speak_command(interaction: discord.Interaction, message: str):
                await self._handle_speak_command(interaction, message)
            
            # Sync command
            @app_commands.command(name="sync", description="Sync slash commands (admin only)")
            async def sync_command(interaction: discord.Interaction):
                await self._handle_sync_command(interaction)
            
            # Register commands with the bot tree
            logger.info("Adding commands to bot tree...")
            self.bot.tree.add_command(chat_command)
            self.bot.tree.add_command(status_command)
            self.bot.tree.add_command(help_command)
            self.bot.tree.add_command(auto_chat_command)
            self.bot.tree.add_command(join_command)
            self.bot.tree.add_command(leave_command)
            self.bot.tree.add_command(voice_status_command)
            self.bot.tree.add_command(speak_command)
            self.bot.tree.add_command(sync_command)
            
            # Verify commands were added
            registered_commands = [cmd.name for cmd in self.bot.tree.get_commands()]
            logger.info(f"Commands in tree after registration: {registered_commands}")
            logger.info("Registered legacy slash commands: chat, status, help, auto-chat")
            
        except Exception as e:
            logger.error(f"Error registering legacy slash commands: {e}")

    async def _handle_chat_command(self, interaction: discord.Interaction, message: str, private: bool = False):
        """Handle the /chat slash command."""
        try:
            # Defer response since AI calls can take time
            await interaction.response.defer(ephemeral=private)
            
            from nagatha_assistant.core.agent import send_message, start_session
            
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
            
            # Speak the response in voice channel if linked (only for non-private responses)
            if not private and hasattr(self.discord_plugin, 'voice_handler') and self.discord_plugin.voice_handler:
                await self.discord_plugin.voice_handler.speak_text_channel_response(
                    str(interaction.channel_id), response
                )
                
        except Exception as e:
            logger.exception(f"Error in chat command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Sorry, I encountered an error: {str(e)}", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Sorry, I encountered an error: {str(e)}", 
                        ephemeral=True
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    async def _handle_status_command(self, interaction: discord.Interaction):
        """Handle the /status slash command."""
        try:
            # Defer response since status calls can take time
            await interaction.response.defer()
            
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            
            # Get MCP status
            mcp_manager = await get_mcp_manager()
            mcp_status = mcp_manager.get_initialization_summary()
            
            # Get plugin status
            plugin_manager = get_plugin_manager()
            plugin_status = plugin_manager.get_plugin_status()
            
            # Build status response
            response = "🤖 **Nagatha System Status**\n\n"
            
            # MCP Status
            response += "**MCP Servers:**\n"
            if mcp_status['connected'] > 0:
                response += f"✅ {mcp_status['connected']}/{mcp_status['total_configured']} servers connected\n"
                response += f"🔧 {mcp_status['total_tools']} tools available\n"
            else:
                response += "❌ No MCP servers connected\n"
            
            # Plugin Status
            response += "\n**Plugins:**\n"
            active_plugins = [name for name, status in plugin_status.items() if status.get('state') == 'started']
            if active_plugins:
                response += f"✅ {len(active_plugins)} plugins active\n"
                for plugin in active_plugins[:3]:  # Show first 3
                    response += f"  • {plugin}\n"
                if len(active_plugins) > 3:
                    response += f"  • ... and {len(active_plugins) - 3} more\n"
            else:
                response += "❌ No plugins active\n"
            
            # Bot Status
            response += "\n**Bot Status:**\n"
            response += "✅ Connected to Discord\n"
            response += f"📊 {len(self.bot.guilds)} servers connected\n"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in status command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Error getting status: {str(e)}", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error getting status: {str(e)}", 
                        ephemeral=True
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    async def _handle_help_command(self, interaction: discord.Interaction):
        """Handle the /help slash command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Build help response
            response = "🤖 **Nagatha Assistant Commands**\n\n"
            response += "**Available Slash Commands:**\n"
            response += "• `/chat <message> [private]` - Chat with Nagatha AI assistant\n"
            response += "• `/auto-chat <on|off|status>` - Enable/disable auto-chat mode for this channel\n"
            response += "• `/status` - Get system status and plugin information\n" 
            response += "• `/help` - Show this help message\n"
            response += "• `/sync` - Sync slash commands (admin only)\n\n"
            
            response += "**Voice Commands:**\n"
            response += "• `/join [channel]` - Join a voice channel and link to this text channel\n"
            response += "• `/leave` - Leave the current voice channel\n"
            response += "• `/voice-status` - Check voice capabilities and status\n"
            response += "• `/speak <message>` - Make Nagatha speak a message\n\n"
            
            response += "**Legacy Prefix Commands:**\n"
            response += f"• `{self.command_prefix}ping` - Test bot connectivity\n"
            response += f"• `{self.command_prefix}hello` - Get a greeting from Nagatha\n\n"
            
            response += "**Getting Started:**\n"
            response += "1. Use `/chat` to have conversations with Nagatha\n"
            response += "2. Use `/auto-chat on` to enable automatic responses in this channel\n"
            response += "3. Use `/join` to link voice channel to this text channel for voice responses\n"
            response += "4. Check `/status` to see what tools and plugins are available\n"
            response += "5. Nagatha can help with notes, tasks, web research, and more!\n\n"
            
            response += "*More commands may be available from other plugins and MCP servers.*"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in help command: {e}")
            await interaction.followup.send(
                f"❌ Error getting help: {str(e)}"
            )
    
    async def _handle_auto_chat_command(self, interaction: discord.Interaction, action: str):
        """Handle the /auto-chat slash command."""
        try:
            # Defer the response first
            await interaction.response.defer()
            
            channel_id = str(interaction.channel_id)
            guild_id = str(interaction.guild_id) if interaction.guild_id else None
            user_id = str(interaction.user.id)
            
            if action == "status":
                # Get current status
                setting = await get_auto_chat_setting(channel_id)
                if setting and setting.enabled:
                    response = f"✅ **Auto-chat is ENABLED** in this channel\n"
                    response += f"• Enabled by: <@{setting.enabled_by_user_id}>\n"
                    response += f"• Messages today: {setting.message_count}\n"
                    if setting.last_message_at:
                        response += f"• Last response: <t:{int(setting.last_message_at.timestamp())}:R>\n"
                else:
                    response = "❌ **Auto-chat is DISABLED** in this channel"
                
                await interaction.followup.send(response)
                return
            
            elif action == "on":
                # Check permissions - only admins or channel owners can enable auto-chat
                if interaction.guild:
                    # In guilds, check for manage_channel permission
                    if not interaction.user.guild_permissions.manage_channels:
                        await interaction.followup.send(
                            "❌ You need 'Manage Channels' permission to enable auto-chat in this server.",
                            ephemeral=True
                        )
                        return
                # For DMs, anyone can enable auto-chat
                
                # Enable auto-chat
                setting = await set_auto_chat_setting(channel_id, guild_id, True, user_id)
                
                response = "✅ **Auto-chat ENABLED!** 🎉\n\n"
                response += "Nagatha will now automatically respond to all messages in this channel.\n\n"
                response += "**Features:**\n"
                response += "• Natural conversation without `/chat` commands\n"
                response += "• Rate limited to prevent spam (100 messages/hour)\n"
                response += "• Ignores bot messages and system messages\n\n"
                response += "Use `/auto-chat off` to disable or `/auto-chat status` to check usage."
                
                await interaction.followup.send(response)
                
                logger.info(f"Auto-chat enabled in channel {channel_id} by user {user_id}")
                
            elif action == "off":
                # Check permissions - only the user who enabled it or admins can disable
                current_setting = await get_auto_chat_setting(channel_id)
                if current_setting and current_setting.enabled:
                    can_disable = False
                    
                    # User who enabled it can always disable
                    if current_setting.enabled_by_user_id == user_id:
                        can_disable = True
                    # Admins can disable
                    elif interaction.guild and interaction.user.guild_permissions.manage_channels:
                        can_disable = True
                    # In DMs, anyone can disable
                    elif not interaction.guild:
                        can_disable = True
                    
                    if not can_disable:
                        await interaction.followup.send(
                            "❌ You can only disable auto-chat if you enabled it or have 'Manage Channels' permission.",
                            ephemeral=True
                        )
                        return
                
                # Disable auto-chat
                await set_auto_chat_setting(channel_id, guild_id, False, user_id)
                
                response = "🔕 **Auto-chat DISABLED**\n\n"
                response += "Nagatha will no longer automatically respond to messages.\n"
                response += "You can still use `/chat` for individual conversations."
                
                await interaction.followup.send(response)
                
                logger.info(f"Auto-chat disabled in channel {channel_id} by user {user_id}")
            
        except Exception as e:
            logger.exception(f"Error in auto-chat command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Error managing auto-chat: {str(e)}", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error managing auto-chat: {str(e)}", 
                        ephemeral=True
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    async def _handle_join_voice_command(self, interaction: discord.Interaction, channel: discord.VoiceChannel = None):
        """Handle the /join voice command."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.voice_handler:
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Get voice channel
            voice_channel = channel
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
            
            # Join the voice channel and link to the text channel where the command was issued
            text_channel_id = str(interaction.channel_id)
            success = await self.voice_handler.join_voice_channel(
                voice_channel, interaction.guild.id, text_channel_id
            )
            
            if success:
                # Start voice listening
                await self.voice_handler.start_voice_listening(interaction.guild.id)
                
                await interaction.followup.send(
                    f"🎤 **Joined voice channel:** {voice_channel.name}\n\n"
                    f"I'm now linked to this text channel and will speak my responses here in the voice channel. "
                    f"Just type your messages and I'll respond with both text and voice! "
                    f"Use `/leave` when you're done."
                )
            else:
                await interaction.followup.send("❌ Failed to join voice channel. Please try again.")
                
        except Exception as e:
            logger.exception(f"Error in join voice command: {e}")
            await interaction.followup.send(f"❌ Error joining voice channel: {str(e)}")
    
    async def _handle_leave_voice_command(self, interaction: discord.Interaction):
        """Handle the /leave voice command."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.voice_handler:
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Check if we're in a voice channel
            is_connected = await self.voice_handler.is_in_voice_channel(interaction.guild.id)
            
            if not is_connected:
                await interaction.followup.send("❌ I'm not currently in a voice channel")
                return
            
            # Leave the voice channel
            success = await self.voice_handler.leave_voice_channel(interaction.guild.id)
            
            if success:
                await interaction.followup.send("👋 **Left voice channel**\n\nThanks for the conversation!")
            else:
                await interaction.followup.send("❌ Failed to leave voice channel. Please try again.")
                
        except Exception as e:
            logger.exception(f"Error in leave voice command: {e}")
            await interaction.followup.send(f"❌ Error leaving voice channel: {str(e)}")
    
    async def _handle_voice_status_command(self, interaction: discord.Interaction):
        """Handle the /voice-status command."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.voice_handler:
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Get voice status
            status = await self.voice_handler.get_voice_status(interaction.guild.id)
            
            # Build status message
            response = "🎤 **Voice Status**\n\n"
            
            if status['is_connected']:
                channel_info = status['channel_info']
                response += f"**Connected to:** {channel_info['channel_name']}\n"
                response += f"**Members:** {channel_info['member_count']}\n"
                response += f"**Conversations:** {status['conversation_count']}\n"
                
                # Show linked text channel info
                if channel_info.get('text_channel_id'):
                    response += f"**Linked Text Channel:** <#{channel_info['text_channel_id']}>\n"
                    response += "**Mode:** Text-to-Voice (speaking text responses)\n"
                else:
                    response += "**Mode:** Voice-to-Voice (listening for speech)\n"
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
    
    async def _handle_speak_command(self, interaction: discord.Interaction, message: str):
        """Handle the /speak command."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not self.voice_handler:
                await interaction.followup.send("❌ Voice functionality not available")
                return
            
            # Check if we're in a voice channel
            is_connected = await self.voice_handler.is_in_voice_channel(interaction.guild.id)
            
            if not is_connected:
                await interaction.followup.send("❌ I need to be in a voice channel first. Use `/join` to join a voice channel.")
                return
            
            # Make Nagatha speak
            success = await self.voice_handler.speak_in_voice_channel(
                message, interaction.guild.id
            )
            
            if success:
                await interaction.followup.send(f"🗣️ **Speaking:** {message}")
            else:
                await interaction.followup.send("❌ Failed to speak the message. Please try again.")
                
        except Exception as e:
            logger.exception(f"Error in speak command: {e}")
            await interaction.followup.send(f"❌ Error speaking message: {str(e)}")
    
    async def _handle_sync_command(self, interaction: discord.Interaction):
        """Handle the /sync slash command."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Check if user has admin permissions
            if interaction.guild and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send(
                    "❌ You need administrator permissions to sync slash commands.",
                    ephemeral=True
                )
                return
            
            # Sync commands
            synced_count = await self.sync_slash_commands(interaction.guild.id if interaction.guild else None)
            
            if interaction.guild:
                await interaction.followup.send(
                    f"✅ Synced {synced_count} slash commands to this server!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ Synced {synced_count} slash commands globally!",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.exception(f"Error in sync command: {e}")
            await interaction.followup.send(
                f"❌ Error syncing commands: {str(e)}",
                ephemeral=True
            )
    
    def add_slash_command(self, name: str, description: str, handler: callable, **kwargs) -> bool:
        """
        Add a custom slash command from a plugin or MCP server.
        
        Args:
            name: Command name
            description: Command description  
            handler: Async function to handle the command
            **kwargs: Additional app_commands.command parameters
            
        Returns:
            True if registered successfully, False otherwise
        """
        if not self.bot:
            logger.warning("Cannot add slash command: bot not initialized")
            return False
        
        try:
            # Create the app command
            @app_commands.command(name=name, description=description, **kwargs)
            async def custom_command(interaction: discord.Interaction):
                try:
                    await handler(interaction)
                except Exception as e:
                    logger.exception(f"Error in custom slash command {name}: {e}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"❌ Command error: {str(e)}", ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"❌ Command error: {str(e)}", ephemeral=True
                        )
            
            # Add to bot tree
            self.bot.tree.add_command(custom_command)
            
            logger.info(f"Added custom slash command: /{name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add slash command {name}: {e}")
            return False
    
    def remove_slash_command(self, name: str) -> bool:
        """
        Remove a custom slash command.
        
        Args:
            name: Command name to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        if not self.bot:
            return False
        
        try:
            self.bot.tree.remove_command(name)
            logger.info(f"Removed slash command: /{name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove slash command {name}: {e}")
            return False
    
    async def sync_slash_commands(self, guild_id: Optional[int] = None) -> int:
        """
        Manually sync slash commands with Discord.
        
        Args:
            guild_id: Guild ID to sync to (None for global sync)
            
        Returns:
            Number of commands synced
        """
        if not self.bot:
            return 0
        
        try:
            if guild_id:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    synced = await self.bot.tree.sync(guild=guild)
                    logger.info(f"Synced {len(synced)} slash commands to guild {guild.name}")
                    return len(synced)
                else:
                    logger.warning(f"Guild {guild_id} not found")
                    return 0
            else:
                synced = await self.bot.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands globally")
                return len(synced)
                
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
            return 0
    
    def get_slash_command_names(self) -> List[str]:
        """Get list of registered slash command names."""
        if not self.bot:
            return []
        
        return [cmd.name for cmd in self.bot.tree.get_commands()]
    
    async def _run_bot(self):
        """Internal method to run the Discord bot."""
        try:
            logger.info(f"Attempting to connect to Discord with token: {self.token[:10]}...")
            # Remove timeout to see if connection works without timing out
            await self.bot.start(self.token)
        except asyncio.TimeoutError:
            logger.error("Discord bot connection timed out")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": "Connection timed out"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        except discord.PrivilegedIntentsRequired as e:
            logger.error(f"Discord bot privileged intents not enabled: {e}")
            logger.error("To fix this, go to https://discord.com/developers/applications/")
            logger.error("Select your bot application, go to the 'Bot' section,")
            logger.error("and enable 'Message Content Intent' under 'Privileged Gateway Intents'")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": f"Privileged intents not enabled: {str(e)}"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        except discord.LoginFailure as e:
            logger.error(f"Discord bot login failed - invalid token: {e}")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": f"Login failure: {str(e)}"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        except discord.HTTPException as e:
            logger.error(f"Discord bot HTTP error: {e}")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": f"HTTP error: {str(e)}"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        except discord.GatewayNotFound as e:
            logger.error(f"Discord bot gateway not found: {e}")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": f"Gateway not found: {str(e)}"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        except discord.ConnectionClosed as e:
            logger.error(f"Discord bot connection closed: {e}")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": f"Connection closed: {str(e)}"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        except asyncio.CancelledError:
            logger.info("Discord bot task was cancelled")
            self.is_running = False
            raise  # Re-raise CancelledError
        except Exception as e:
            logger.error(f"Discord bot crashed with unexpected error: {e}")
            logger.exception("Full traceback:")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": f"Unexpected error: {str(e)}"},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
        finally:
            # Ensure is_running is set to False when the method exits
            self.is_running = False
            logger.info("Discord bot _run_bot method completed")
    
    async def handle_system_event(self, event: Event) -> None:
        """
        Handle system events.
        
        Args:
            event: System event to handle
        """
        if event.event_type == StandardEventTypes.SYSTEM_STARTUP:
            logger.info("Discord bot plugin detected system startup")
            # Optionally auto-start the bot if configured
            auto_start = self.config.config.get("auto_start", False)
            if auto_start and self.token:
                await self.start_discord_bot()
                
        elif event.event_type == StandardEventTypes.SYSTEM_SHUTDOWN:
            logger.info("Discord bot plugin detected system shutdown")
            await self.stop_discord_bot()


# Plugin configuration for discovery
PLUGIN_CONFIG = {
    "name": "discord_bot",
    "version": "1.0.0",
    "description": "Discord bot integration for Nagatha Assistant",
    "author": "Nagatha Assistant",
    "dependencies": ["discord.py"],
    "config": {
        "auto_start": False,  # Whether to automatically start the bot on system startup
        "command_prefix": "!",  # Default command prefix
    },
    "enabled": True,
    "priority": 50  # Medium priority
}