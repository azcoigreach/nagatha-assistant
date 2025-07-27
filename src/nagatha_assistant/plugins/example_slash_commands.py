"""
Example plugin demonstrating how to register Discord slash commands.

This plugin shows how other plugins and MCP servers can register
their own slash commands with the Discord bot.
"""

from typing import Optional
import discord

from nagatha_assistant.core.plugin import SimplePlugin, PluginConfig
from nagatha_assistant.core.event import Event
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()


class ExampleSlashCommandPlugin(SimplePlugin):
    """
    Example plugin that registers custom slash commands.
    
    This demonstrates the pattern for plugins to extend the Discord bot
    with their own slash commands.
    """
    
    PLUGIN_NAME = "example_slash_commands"
    PLUGIN_VERSION = "1.0.0"
    
    def __init__(self, config: PluginConfig):
        """Initialize the example plugin."""
        super().__init__(config)
        self.discord_plugin = None
        self.registered_commands = []
    
    async def setup(self) -> None:
        """Setup the plugin by registering slash commands."""
        # Get the Discord bot plugin
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        self.discord_plugin = plugin_manager.get_plugin("discord_bot")
        
        if not self.discord_plugin:
            logger.warning("Discord bot plugin not found - cannot register slash commands")
            return
        
        # Register our custom slash commands
        await self._register_slash_commands()
        
        logger.info("Example slash command plugin setup complete")
    
    async def teardown(self) -> None:
        """Cleanup by unregistering slash commands."""
        if self.discord_plugin:
            for command_name in self.registered_commands:
                self.discord_plugin.remove_slash_command(command_name)
            self.registered_commands.clear()
        
        logger.info("Example slash command plugin cleaned up")
    
    async def _register_slash_commands(self) -> None:
        """Register our custom slash commands."""
        
        # Example 1: Simple command with no parameters
        success = self.discord_plugin.add_slash_command(
            name="example_hello",
            description="Example command that says hello",
            handler=self._handle_hello_command
        )
        if success:
            self.registered_commands.append("example_hello")
        
        # Example 2: Command that demonstrates MCP integration
        success = self.discord_plugin.add_slash_command(
            name="example_mcp_status",
            description="Example command showing MCP server information",
            handler=self._handle_mcp_status_command
        )
        if success:
            self.registered_commands.append("example_mcp_status")
        
        logger.info(f"Registered {len(self.registered_commands)} example slash commands")
    
    async def _handle_hello_command(self, interaction: discord.Interaction) -> None:
        """Handle the /example_hello slash command."""
        await interaction.response.send_message(
            f"👋 Hello {interaction.user.mention}! This is an example slash command "
            f"registered by the `{self.name}` plugin.",
            ephemeral=True
        )
    
    async def _handle_mcp_status_command(self, interaction: discord.Interaction) -> None:
        """Handle the /example_mcp_status slash command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            
            # Get MCP status
            mcp_manager = await get_mcp_manager()
            mcp_status = await mcp_manager.get_status()
            
            # Build response
            response = "🔧 **Example MCP Status Report**\n\n"
            
            servers = mcp_status.get("servers", {})
            if not servers:
                response += "No MCP servers currently connected."
            else:
                response += f"**Connected Servers:** {len(servers)}\n\n"
                
                for server_name, server_info in servers.items():
                    response += f"**{server_name}**\n"
                    tools = server_info.get("tools", [])
                    response += f"  • Tools: {len(tools)}\n"
                    if tools:
                        # Show first few tools
                        tool_names = [tool.get("name", "unknown") for tool in tools[:3]]
                        response += f"  • Examples: {', '.join(tool_names)}"
                        if len(tools) > 3:
                            response += f" (+{len(tools) - 3} more)"
                        response += "\n"
                    response += "\n"
            
            response += "\n*This is an example command showing how plugins can integrate with MCP.*"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            logger.exception(f"Error in example MCP status command: {e}")
            await interaction.followup.send(
                f"❌ Error getting MCP status: {str(e)}"
            )


# Plugin configuration for discovery
PLUGIN_CONFIG = {
    "name": "example_slash_commands",
    "version": "1.0.0",
    "description": "Example plugin demonstrating Discord slash command registration",
    "author": "Nagatha Assistant",
    "dependencies": ["discord_bot"],
    "config": {},
    "enabled": False,  # Disabled by default since it's just an example
    "priority": 100
}