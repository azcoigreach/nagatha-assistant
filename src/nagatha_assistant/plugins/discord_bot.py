"""
Discord Bot Plugin for Nagatha Assistant.

A Discord bot integration that allows Nagatha to interact with Discord servers,
providing AI assistant capabilities through Discord channels.
"""

import os
import logging
import asyncio
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from ..core.plugin import SimplePlugin, PluginConfig, PluginCommand
from ..core.event import Event, StandardEventTypes, create_system_event
from ..utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


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
    
    async def on_message(self, message: discord.Message):
        """
        Handle incoming Discord messages.
        
        This is where we can integrate with Nagatha's conversation system
        to provide AI responses to Discord messages.
        """
        # Don't respond to ourselves
        if message.author == self.user:
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
        
        # Process commands
        await self.process_commands(message)


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
        self.bot: Optional[NagathaDiscordBot] = None
        self._bot_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Discord configuration
        self.token = os.getenv('DISCORD_BOT_TOKEN')
        self.guild_id = os.getenv('DISCORD_GUILD_ID')
        self.command_prefix = os.getenv('DISCORD_COMMAND_PREFIX', '!')
        
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
        
        # Register with the plugin manager
        from ..core.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        plugin_manager.register_command(start_command)
        plugin_manager.register_command(stop_command)
        plugin_manager.register_command(status_command)
        
        # Subscribe to system events
        self.subscribe_to_events(
            "system.*",
            self.handle_system_event
        )
        
        # Validate Discord configuration
        if not self.token:
            logger.warning("Discord bot token not configured - Discord functionality disabled")
        
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
            # Configure Discord intents
            intents = discord.Intents.default()
            intents.message_content = True  # Required for message content access
            
            # Create bot instance
            self.bot = NagathaDiscordBot(
                self,
                command_prefix=self.command_prefix,
                intents=intents,
                help_command=None  # Disable default help command
            )
            
            # Add a simple ping command
            @self.bot.command(name='ping')
            async def ping(ctx):
                """Respond with pong to test bot connectivity."""
                await ctx.send('Pong! Nagatha is online.')
            
            @self.bot.command(name='hello')
            async def hello(ctx):
                """Say hello to users."""
                await ctx.send(f'Hello {ctx.author.mention}! I\'m Nagatha, your AI assistant.')
            
            # Start the bot in a background task
            self._bot_task = asyncio.create_task(self._run_bot())
            self.is_running = True
            
            # Publish bot start event
            event = create_system_event(
                "discord.bot.starting",
                {"command_prefix": self.command_prefix},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
            
            logger.info("Discord bot starting...")
            return "Discord bot started successfully"
            
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            self.is_running = False
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
    
    async def _run_bot(self):
        """Internal method to run the Discord bot."""
        try:
            await self.bot.start(self.token)
        except Exception as e:
            logger.error(f"Discord bot crashed: {e}")
            self.is_running = False
            
            # Publish bot error event
            event = create_system_event(
                "discord.bot.crashed",
                {"error": str(e)},
                source="discord_bot_plugin"
            )
            await self.publish_event(event)
    
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