"""
Slash Command Manager for Discord Bot Integration.

This module provides centralized management of Discord slash commands,
including registration, routing, and integration with plugins and MCP servers.
"""

import logging
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable, Union
from enum import Enum

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)


class SlashCommandType(Enum):
    """Types of slash commands."""
    CHAT = "chat"
    MESSAGE = "message" 
    USER = "user"


@dataclass
class SlashCommandOption:
    """Represents a slash command option/parameter."""
    name: str
    description: str
    type: str  # Keep as string for simplicity
    required: bool = True
    choices: Optional[List[Dict[str, Any]]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


@dataclass 
class SlashCommandDefinition:
    """Definition of a slash command."""
    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    plugin_name: str
    options: List[SlashCommandOption] = field(default_factory=list)
    command_type: SlashCommandType = SlashCommandType.CHAT
    guild_only: bool = False
    nsfw: bool = False


class BaseSlashCommand(ABC):
    """Base class for slash command implementations."""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.logger = logging.getLogger(f"slash_command.{plugin_name}")
    
    @abstractmethod
    def get_command_definition(self) -> SlashCommandDefinition:
        """Get the command definition for registration."""
        pass
    
    @abstractmethod
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """Execute the slash command."""
        pass
    
    async def handle_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle command execution errors."""
        self.logger.error(f"Error in slash command {self.get_command_definition().name}: {error}")
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(error)}", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ An error occurred: {str(error)}", 
                    ephemeral=True
                )
        except Exception as follow_error:
            self.logger.error(f"Failed to send error message: {follow_error}")


class SlashCommandManager:
    """
    Manages Discord slash commands for the Nagatha bot.
    
    Features:
    - Command registration and routing
    - Plugin integration
    - Permission management
    - Error handling
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._commands: Dict[str, SlashCommandDefinition] = {}
        self._command_handlers: Dict[str, BaseSlashCommand] = {}
        self.logger = logging.getLogger(__name__)
        
        # Set up error handling
        self._setup_error_handling()
    
    def _setup_error_handling(self) -> None:
        """Set up error handling for app commands."""
        
        @self.bot.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            """Handle application command errors."""
            self.logger.error(f"Application command error: {error}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ An error occurred: {str(error)}", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ An error occurred: {str(error)}", 
                        ephemeral=True
                    )
            except Exception as follow_error:
                self.logger.error(f"Failed to send error message: {follow_error}")
    
    def register_command(self, command: BaseSlashCommand) -> bool:
        """
        Register a slash command.
        
        Args:
            command: Command implementation to register
            
        Returns:
            True if registered successfully, False if name conflict
        """
        command_def = command.get_command_definition()
        
        if command_def.name in self._commands:
            self.logger.warning(f"Slash command {command_def.name} already registered")
            return False
        
        try:
            # Create and register the app command dynamically
            self._create_app_command(command_def, command)
            
            self._commands[command_def.name] = command_def
            self._command_handlers[command_def.name] = command
            
            self.logger.info(f"Registered slash command: {command_def.name} from plugin {command_def.plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register slash command {command_def.name}: {e}")
            return False
    
    def _create_app_command(self, command_def: SlashCommandDefinition, command: BaseSlashCommand) -> None:
        """Create and register a discord.py app command."""
        
        # For simple commands, just use the @app_commands.command decorator approach
        if not command_def.options:
            # Simple command with no parameters
            @app_commands.command(name=command_def.name, description=command_def.description)
            async def simple_command(interaction: discord.Interaction):
                try:
                    await command.execute(interaction)
                except Exception as e:
                    await command.handle_error(interaction, e)
            
            self.bot.tree.add_command(simple_command)
        
        else:
            # Command with parameters - we'll create it manually
            self._create_parameterized_command(command_def, command)
    
    def _create_parameterized_command(self, command_def: SlashCommandDefinition, command: BaseSlashCommand) -> None:
        """Create a command with parameters."""
        
        # For now, create a generic command handler that can handle common patterns
        # This is a simplified approach - in production, we'd want more robust parameter handling
        
        @app_commands.command(name=command_def.name, description=command_def.description)
        async def parameterized_command(interaction: discord.Interaction):
            try:
                # Extract parameters from the interaction data
                kwargs = {}
                if hasattr(interaction, 'data') and 'options' in interaction.data:
                    for option in interaction.data['options']:
                        kwargs[option['name']] = option.get('value')
                
                await command.execute(interaction, **kwargs)
            except Exception as e:
                await command.handle_error(interaction, e)
        
        # For parameterized commands, we'll need to manually set up the parameters
        # This is a limitation of this simplified approach
        self.bot.tree.add_command(parameterized_command)
    
    def unregister_command(self, command_name: str) -> bool:
        """
        Unregister a slash command.
        
        Args:
            command_name: Name of command to unregister
            
        Returns:
            True if unregistered successfully
        """
        if command_name not in self._commands:
            return False
        
        try:
            # Remove from bot tree
            self.bot.tree.remove_command(command_name)
            
            del self._commands[command_name]
            del self._command_handlers[command_name]
            
            self.logger.info(f"Unregistered slash command: {command_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unregister command {command_name}: {e}")
            return False
    
    async def sync_commands(self, guild: Optional[discord.Guild] = None) -> int:
        """
        Sync registered commands with Discord.
        
        Args:
            guild: Guild to sync to (None for global commands)
            
        Returns:
            Number of commands synced
        """
        try:
            if guild:
                synced = await self.bot.tree.sync(guild=guild)
                self.logger.info(f"Synced {len(synced)} slash commands to guild {guild.name}")
            else:
                synced = await self.bot.tree.sync()
                self.logger.info(f"Synced {len(synced)} global slash commands")
            
            return len(synced)
            
        except Exception as e:
            self.logger.error(f"Failed to sync slash commands: {e}")
            return 0
    
    def get_registered_commands(self) -> List[str]:
        """Get list of registered command names."""
        return list(self._commands.keys())
    
    def get_command_info(self, command_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a registered command."""
        if command_name not in self._commands:
            return None
        
        cmd_def = self._commands[command_name]
        return {
            "name": cmd_def.name,
            "description": cmd_def.description,
            "plugin": cmd_def.plugin_name,
            "options": [
                {
                    "name": opt.name,
                    "description": opt.description,
                    "type": opt.type,
                    "required": opt.required
                }
                for opt in cmd_def.options
            ],
            "guild_only": cmd_def.guild_only,
            "nsfw": cmd_def.nsfw
        }
    
    def get_commands_by_plugin(self, plugin_name: str) -> List[str]:
        """Get list of commands registered by a specific plugin."""
        return [
            name for name, cmd_def in self._commands.items()
            if cmd_def.plugin_name == plugin_name
        ]
    
    def unregister_plugin_commands(self, plugin_name: str) -> int:
        """
        Unregister all commands from a specific plugin.
        
        Args:
            plugin_name: Name of plugin whose commands to unregister
            
        Returns:
            Number of commands unregistered
        """
        commands_to_remove = self.get_commands_by_plugin(plugin_name)
        
        for command_name in commands_to_remove:
            self.unregister_command(command_name)
        
        self.logger.info(f"Unregistered {len(commands_to_remove)} commands from plugin {plugin_name}")
        return len(commands_to_remove)