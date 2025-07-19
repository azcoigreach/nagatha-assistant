"""
Base plugin system for Nagatha Assistant.

This module provides the base classes and interfaces for the plugin system,
including plugin definitions, lifecycle management, and registration.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable

from .event import Event, EventHandler
from .event_bus import get_event_bus

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """Plugin lifecycle states."""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100  # Lower numbers have higher priority


@dataclass
class PluginCommand:
    """Represents a command registered by a plugin."""
    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    plugin_name: str
    parameters: Optional[Dict[str, Any]] = None


class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class BasePlugin(ABC):
    """
    Base class for all Nagatha plugins.
    
    Plugins extend the functionality of Nagatha through a well-defined interface
    that provides lifecycle management, event integration, and command registration.
    """
    
    def __init__(self, config: PluginConfig):
        """
        Initialize the plugin with configuration.
        
        Args:
            config: Plugin configuration object
        """
        self.config = config
        self.state = PluginState.LOADED
        self.logger = logging.getLogger(f"plugin.{config.name}")
        self._event_subscriptions: List[int] = []
        self._registered_commands: Set[str] = set()
        self._event_bus = get_event_bus()
        
    @property
    def name(self) -> str:
        """Get the plugin name."""
        return self.config.name
    
    @property
    def version(self) -> str:
        """Get the plugin version."""
        return self.config.version
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the plugin.
        
        This method is called after the plugin is loaded but before it's started.
        Use this to set up any resources or validate configuration.
        
        Raises:
            PluginError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the plugin.
        
        This method is called to activate the plugin after initialization.
        Register event handlers and commands here.
        
        Raises:
            PluginError: If startup fails
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the plugin.
        
        This method is called to gracefully shutdown the plugin.
        Clean up resources and unregister handlers here.
        """
        pass
    
    async def reload_config(self, new_config: PluginConfig) -> None:
        """
        Reload plugin configuration.
        
        Default implementation just updates the config. Override for custom behavior.
        
        Args:
            new_config: New configuration to apply
        """
        self.config = new_config
        self.logger.info(f"Configuration reloaded for plugin {self.name}")
    
    def subscribe_to_events(self, pattern: str, handler: EventHandler, 
                          priority_filter: Optional[Any] = None,
                          source_filter: Optional[str] = None) -> int:
        """
        Subscribe to events with automatic cleanup on plugin stop.
        
        Args:
            pattern: Event pattern to match
            handler: Event handler function
            priority_filter: Filter by event priority
            source_filter: Filter by event source
            
        Returns:
            Subscription ID
        """
        subscription_id = self._event_bus.subscribe(
            pattern, handler, priority_filter, source_filter
        )
        self._event_subscriptions.append(subscription_id)
        return subscription_id
    
    async def publish_event(self, event: Event) -> None:
        """
        Publish an event through the event bus.
        
        Args:
            event: Event to publish
        """
        try:
            await self._event_bus.publish(event)
        except Exception as e:
            # If event bus is not running, log but don't fail
            self.logger.debug(f"Could not publish event {event.event_type}: {e}")
    
    def publish_event_sync(self, event: Event) -> None:
        """
        Synchronously publish an event (for when not in async context).
        
        Args:
            event: Event to publish
        """
        try:
            self._event_bus.publish_sync(event)
        except Exception as e:
            # If event bus is not running, log but don't fail
            self.logger.debug(f"Could not publish event {event.event_type}: {e}")
    
    def register_command(self, command: PluginCommand) -> None:
        """
        Register a command for this plugin.
        
        This is a hook for the plugin manager to register commands.
        The actual implementation is handled by the plugin manager.
        
        Args:
            command: Command to register
        """
        self._registered_commands.add(command.name)
        self.logger.debug(f"Command '{command.name}' registered for plugin {self.name}")
    
    def unregister_command(self, command_name: str) -> None:
        """
        Unregister a command for this plugin.
        
        Args:
            command_name: Name of command to unregister
        """
        self._registered_commands.discard(command_name)
        self.logger.debug(f"Command '{command_name}' unregistered for plugin {self.name}")
    
    def get_registered_commands(self) -> Set[str]:
        """Get all commands registered by this plugin."""
        return self._registered_commands.copy()
    
    async def _cleanup_subscriptions(self) -> None:
        """Clean up all event subscriptions for this plugin."""
        for subscription_id in self._event_subscriptions:
            self._event_bus.unsubscribe(subscription_id)
        self._event_subscriptions.clear()
        self.logger.debug(f"Cleaned up {len(self._event_subscriptions)} event subscriptions")
    
    async def _set_state(self, state: PluginState) -> None:
        """
        Set the plugin state and publish a state change event.
        
        Args:
            state: New plugin state
        """
        old_state = self.state
        self.state = state
        
        # Publish state change event
        from .event import create_system_event, StandardEventTypes
        event = create_system_event(
            f"plugin.{state.value}",
            {
                "plugin_name": self.name,
                "old_state": old_state.value,
                "new_state": state.value
            },
            source="plugin_manager"
        )
        await self.publish_event(event)
        
        self.logger.info(f"Plugin {self.name} state changed from {old_state.value} to {state.value}")


class SimplePlugin(BasePlugin):
    """
    A simple plugin base class for plugins that don't need complex initialization.
    
    This provides sensible defaults for plugins that just want to register
    event handlers and commands without complex setup.
    """
    
    async def initialize(self) -> None:
        """Default initialization - just sets state."""
        await self._set_state(PluginState.INITIALIZED)
    
    async def start(self) -> None:
        """Default start - calls setup method if available."""
        if hasattr(self, 'setup'):
            await self.setup()
        await self._set_state(PluginState.STARTED)
    
    async def stop(self) -> None:
        """Default stop - cleans up subscriptions and calls teardown if available."""
        if hasattr(self, 'teardown'):
            await self.teardown()
        await self._cleanup_subscriptions()
        await self._set_state(PluginState.STOPPED)


# Event types for plugin system
class PluginEventTypes:
    """Standard event types for the plugin system."""
    
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_INITIALIZED = "plugin.initialized"  
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_STOPPED = "plugin.stopped"
    PLUGIN_ERROR = "plugin.error"
    PLUGIN_COMMAND_REGISTERED = "plugin.command.registered"
    PLUGIN_COMMAND_UNREGISTERED = "plugin.command.unregistered"
    PLUGIN_DEPENDENCY_RESOLVED = "plugin.dependency.resolved"
    PLUGIN_DEPENDENCY_FAILED = "plugin.dependency.failed"