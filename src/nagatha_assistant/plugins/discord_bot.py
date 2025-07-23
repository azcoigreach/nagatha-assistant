"""
Discord Bot Plugin for Nagatha Assistant.

A Discord bot integration that allows Nagatha to interact with Discord servers,
providing AI assistant capabilities through Discord channels.
"""

import os
import logging
import asyncio
from typing import Any, Dict, Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from nagatha_assistant.core.plugin import SimplePlugin, PluginConfig, PluginCommand
from nagatha_assistant.core.event import Event, StandardEventTypes, create_system_event
from nagatha_assistant.core.slash_command_manager import SlashCommandManager
from nagatha_assistant.core.slash_commands import ChatSlashCommand, StatusSlashCommand, HelpSlashCommand
from nagatha_assistant.utils.logger import setup_logger_with_env_control

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
        logger.info(f'Connected to {len(self.guilds)} guild(s): {[guild.name for guild in self.guilds]}')
        
        # Sync slash commands
        try:
            # Sync globally or to specific guild
            guild_id = self.discord_plugin.guild_id
            if guild_id:
                guild = self.get_guild(int(guild_id))
                if guild:
                    synced = await self.tree.sync(guild=guild)
                    logger.info(f"Synced {len(synced)} slash commands to guild {guild.name}")
                else:
                    logger.warning(f"Guild with ID {guild_id} not found, syncing globally")
                    synced = await self.tree.sync()
                    logger.info(f"Synced {len(synced)} slash commands globally")
            else:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands globally")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
        
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
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
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
                HelpSlashCommand()
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
            
            # Register commands with the bot tree
            self.bot.tree.add_command(chat_command)
            self.bot.tree.add_command(status_command)
            self.bot.tree.add_command(help_command)
            
            logger.info("Registered legacy slash commands: chat, status, help")
            
        except Exception as e:
            logger.error(f"Error registering legacy slash commands: {e}")

    async def _handle_chat_command(self, interaction: discord.Interaction, message: str, private: bool = False):
        """Handle the /chat slash command."""
        # Defer response since AI calls can take time
        await interaction.response.defer(ephemeral=private)
        
        try:
            from ..core.agent import send_message_via_celery, start_session
            
            # Create or get user session
            user_id = str(interaction.user.id)
            session_id = await start_session()
            
            # Get AI response using Celery-based processing
            try:
                response = await send_message_via_celery(session_id, message)
            except Exception as celery_error:
                logger.warning(f"Celery processing failed, falling back: {celery_error}")
                # Fallback to direct processing
                from ..core.agent import send_message
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
    
    async def _handle_status_command(self, interaction: discord.Interaction):
        """Handle the /status slash command."""
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
    
    async def _handle_help_command(self, interaction: discord.Interaction):
        """Handle the /help slash command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Build help response
            response = "🤖 **Nagatha Assistant Commands**\n\n"
            response += "**Available Slash Commands:**\n"
            response += "• `/chat <message> [private]` - Chat with Nagatha AI assistant\n"
            response += "• `/status` - Get system status and plugin information\n" 
            response += "• `/help` - Show this help message\n\n"
            
            response += "**Legacy Prefix Commands:**\n"
            response += f"• `{self.command_prefix}ping` - Test bot connectivity\n"
            response += f"• `{self.command_prefix}hello` - Get a greeting from Nagatha\n\n"
            
            response += "**Getting Started:**\n"
            response += "1. Use `/chat` to have conversations with Nagatha\n"
            response += "2. Check `/status` to see what tools and plugins are available\n"
            response += "3. Nagatha can help with notes, tasks, web research, and more!\n\n"
            
            response += "*More commands may be available from other plugins and MCP servers.*"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in help command: {e}")
            await interaction.followup.send(
                f"❌ Error getting help: {str(e)}"
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