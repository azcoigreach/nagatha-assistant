"""
Echo Plugin for Nagatha Assistant.

A simple plugin that demonstrates the plugin system by providing
an echo command that returns the input text.
"""

import logging
from typing import Any, Dict

from ..core.plugin import SimplePlugin, PluginConfig, PluginCommand
from ..core.event import Event, StandardEventTypes

logger = logging.getLogger(__name__)


class EchoPlugin(SimplePlugin):
    """
    Simple echo plugin that returns input text.
    
    This plugin demonstrates:
    - Basic plugin structure
    - Command registration
    - Event handling
    - Configuration usage
    """
    
    PLUGIN_NAME = "echo"
    PLUGIN_VERSION = "1.0.0"
    
    def __init__(self, config: PluginConfig):
        """Initialize the echo plugin."""
        super().__init__(config)
        self.echo_count = 0
    
    async def setup(self) -> None:
        """Setup the echo plugin by registering commands and event handlers."""
        # Register the echo command
        echo_command = PluginCommand(
            name="echo",
            description="Echo back the provided text",
            handler=self.handle_echo_command,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to echo back"
                    }
                },
                "required": ["text"]
            }
        )
        
        # Register with the plugin manager
        from ..core.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        plugin_manager.register_command(echo_command)
        
        # Subscribe to system events
        self.subscribe_to_events(
            "system.*",
            self.handle_system_event
        )
        
        logger.info(f"Echo plugin setup complete")
    
    async def teardown(self) -> None:
        """Cleanup the echo plugin."""
        logger.info(f"Echo plugin processed {self.echo_count} echo commands")
    
    async def handle_echo_command(self, text: str, **kwargs) -> str:
        """
        Handle the echo command.
        
        Args:
            text: Text to echo back
            **kwargs: Additional arguments
            
        Returns:
            The echoed text
        """
        self.echo_count += 1
        
        # Add any prefix from config
        prefix = self.config.config.get("prefix", "")
        result = f"{prefix}{text}" if prefix else text
        
        # Publish an event for the echo
        from ..core.event import create_system_event
        event = create_system_event(
            "plugin.echo.executed",
            {
                "plugin_name": self.name,
                "input_text": text,
                "output_text": result,
                "echo_count": self.echo_count
            },
            source="echo_plugin"
        )
        await self.publish_event(event)
        
        logger.debug(f"Echo command executed: '{text}' -> '{result}'")
        return result
    
    async def handle_system_event(self, event: Event) -> None:
        """
        Handle system events.
        
        Args:
            event: System event to handle
        """
        if event.event_type == StandardEventTypes.SYSTEM_STARTUP:
            logger.info("Echo plugin detected system startup")
        elif event.event_type == StandardEventTypes.SYSTEM_SHUTDOWN:
            logger.info("Echo plugin detected system shutdown")


# Plugin configuration for discovery
PLUGIN_CONFIG = {
    "name": "echo",
    "version": "1.0.0",
    "description": "Simple echo plugin for testing and demonstration",
    "author": "Nagatha Assistant",
    "dependencies": [],
    "config": {
        "prefix": ""  # Optional prefix for echo responses
    },
    "enabled": True,
    "priority": 100
}