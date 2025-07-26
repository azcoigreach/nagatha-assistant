# Discord Slash Commands for Nagatha Assistant

This document describes the Discord slash commands implementation in Nagatha Assistant, including how to use the built-in commands and how to create custom commands from plugins and MCP servers.

## Built-in Slash Commands

Nagatha Assistant provides several core slash commands out of the box:

### `/chat <message> [private]`
Chat with Nagatha AI assistant.

**Parameters:**
- `message` (required): Your message to Nagatha
- `private` (optional): Send response privately (only you can see it)

**Examples:**
```
/chat Hello Nagatha, how are you today?
/chat Can you help me organize my tasks? private:true
```

### `/status`
Get Nagatha system status including plugin and MCP server information.

**Example:**
```
/status
```

**Response includes:**
- Discord bot status
- Active plugins count
- Connected MCP servers
- Available tools count
- Detailed plugin status

### `/help`
Get help with available commands and usage information.

**Example:**
```
/help
```

## Using Slash Commands

1. **Start the Discord bot**: Use `nagatha discord start` to start the bot in the background
2. **Commands will sync automatically** when the bot connects to Discord
3. **Use commands in Discord**: Type `/` in any channel where the bot has access
4. **View command help**: Discord will show parameter descriptions as you type

## Creating Custom Slash Commands

Plugins and MCP servers can register their own slash commands with the Discord bot. Here's how:

### From a Plugin

```python
from nagatha_assistant.core.plugin import SimplePlugin
from nagatha_assistant.core.plugin_manager import get_plugin_manager
import discord

class MyPlugin(SimplePlugin):
    async def setup(self):
        # Get the Discord bot plugin
        plugin_manager = get_plugin_manager()
        discord_plugin = plugin_manager.get_plugin("discord_bot")
        
        if discord_plugin:
            # Register a custom slash command
            success = discord_plugin.add_slash_command(
                name="my_command",
                description="My custom slash command",
                handler=self.handle_my_command
            )
            
            if success:
                self.logger.info("Custom slash command registered successfully")
            else:
                self.logger.error("Failed to register custom slash command")
    
    async def handle_my_command(self, interaction: discord.Interaction):
        """Handle the /my_command slash command."""
        await interaction.response.send_message(
            "Hello from my custom command!",
            ephemeral=True
        )
    
    async def teardown(self):
        """Clean up when plugin is unloaded."""
        plugin_manager = get_plugin_manager()
        discord_plugin = plugin_manager.get_plugin("discord_bot")
        
        if discord_plugin:
            # Remove the custom command
            discord_plugin.remove_slash_command("my_command")
```

### Available Methods

The Discord bot plugin provides these methods for managing slash commands:

#### `add_slash_command(name, description, handler, **kwargs)`
Add a custom slash command.

**Parameters:**
- `name`: Command name (must be unique)
- `description`: Command description shown in Discord
- `handler`: Async function to handle the command
- `**kwargs`: Additional discord.py app_commands parameters

**Returns:** `True` if successful, `False` otherwise

#### `remove_slash_command(name)`
Remove a slash command.

**Parameters:**
- `name`: Command name to remove

**Returns:** `True` if successful, `False` otherwise

#### `sync_slash_commands(guild_id=None)`
Manually sync commands with Discord.

**Parameters:**
- `guild_id`: Guild ID to sync to (None for global sync)

**Returns:** Number of commands synced

#### `get_slash_command_names()`
Get list of registered slash command names.

**Returns:** List of command names

### Command Handler Requirements

Command handlers must be async functions that accept a `discord.Interaction` parameter:

```python
async def my_handler(interaction: discord.Interaction):
    # Always respond to the interaction
    await interaction.response.send_message("Response text")
    
    # Or defer and use followup for longer operations
    await interaction.response.defer()
    # ... do work ...
    await interaction.followup.send("Result")
```

### Error Handling

The Discord bot automatically wraps command handlers with error handling that:
- Catches exceptions and sends error messages
- Logs errors for debugging
- Sends ephemeral error responses to users

### Best Practices

1. **Use descriptive names**: Command names should be clear and unique
2. **Add proper descriptions**: Help users understand what commands do
3. **Handle errors gracefully**: Use try/catch in complex handlers
4. **Use ephemeral responses**: For private/temporary information
5. **Defer long operations**: Use `await interaction.response.defer()` for operations > 3 seconds
6. **Clean up on plugin shutdown**: Remove commands in plugin teardown

### Advanced Features

#### Guild-specific Commands
You can create commands that only work in specific guilds:

```python
discord_plugin.add_slash_command(
    name="admin_command",
    description="Admin-only command",
    handler=my_handler,
    guild_ids=[123456789]  # Only available in this guild
)
```

#### Command Parameters
For commands with parameters, you'll need to use discord.py's app_commands decorators:

```python
from discord import app_commands

@app_commands.command(name="echo", description="Echo a message")
@app_commands.describe(message="Message to echo")
async def echo_command(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(f"You said: {message}")

# Register with the bot
discord_plugin.bot.tree.add_command(echo_command)
```

## Example Plugin

See `src/nagatha_assistant/plugins/example_slash_commands.py` for a complete example plugin that demonstrates:
- Registering multiple commands
- Command handlers with different complexity
- Integration with MCP systems
- Proper setup and teardown

### Example: MCP Integration Command

```python
class ExampleSlashCommandPlugin(SimplePlugin):
    async def setup(self):
        plugin_manager = get_plugin_manager()
        discord_plugin = plugin_manager.get_plugin("discord_bot")
        
        if discord_plugin:
            # Register a command that shows MCP status
            discord_plugin.add_slash_command(
                name="mcp_status",
                description="Show MCP server status",
                handler=self._handle_mcp_status_command
            )
    
    async def _handle_mcp_status_command(self, interaction: discord.Interaction):
        """Handle the /mcp_status slash command."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            
            # Get MCP status
            mcp_manager = await get_mcp_manager()
            mcp_status = await mcp_manager.get_status()
            
            # Build response
            response = "🔧 **MCP Status Report**\n\n"
            
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
                        tool_names = [tool.get("name", "unknown") for tool in tools[:3]]
                        response += f"  • Examples: {', '.join(tool_names)}"
                        if len(tools) > 3:
                            response += f" (+{len(tools) - 3} more)"
                        response += "\n"
                    response += "\n"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error getting MCP status: {str(e)}"
            )
```

## Integration with MCP Servers

MCP servers can integrate with Discord slash commands in several ways:

### 1. Plugin Wrapper Approach
Create a plugin that wraps MCP server functionality:

```python
class MCPDiscordPlugin(SimplePlugin):
    async def setup(self):
        # Get Discord plugin
        plugin_manager = get_plugin_manager()
        discord_plugin = plugin_manager.get_plugin("discord_bot")
        
        if discord_plugin:
            # Register commands that use MCP tools
            discord_plugin.add_slash_command(
                name="web_search",
                description="Search the web using MCP tools",
                handler=self._handle_web_search
            )
    
    async def _handle_web_search(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            # Get MCP manager and call tools
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            mcp_manager = await get_mcp_manager()
            
            # Call MCP tool
            result = await mcp_manager.call_tool("search", {
                "query": "your search query"
            })
            
            await interaction.followup.send(f"Search result: {result}")
            
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}")
```

### 2. Event-Driven Integration
Use Nagatha's event system to coordinate between MCP servers and Discord:

```python
class EventDrivenMCPPlugin(SimplePlugin):
    async def setup(self):
        # Subscribe to Discord events
        self.subscribe_to_events("discord.message.received", self.handle_discord_message)
        
        # Get Discord plugin and register command
        plugin_manager = get_plugin_manager()
        discord_plugin = plugin_manager.get_plugin("discord_bot")
        
        if discord_plugin:
            discord_plugin.add_slash_command(
                name="process_message",
                description="Process message with MCP tools",
                handler=self._handle_process_command
            )
    
    async def handle_discord_message(self, event):
        """Handle Discord messages and potentially use MCP tools."""
        # Process message content with MCP tools
        pass
    
    async def _handle_process_command(self, interaction: discord.Interaction):
        """Handle the /process_message command."""
        # Implementation here
        pass
```

### 3. Direct MCP Tool Integration
Register commands that directly call MCP tools:

```python
async def setup_mcp_discord_commands():
    """Setup Discord commands that directly use MCP tools."""
    plugin_manager = get_plugin_manager()
    discord_plugin = plugin_manager.get_plugin("discord_bot")
    
    if not discord_plugin:
        return
    
    # Register commands for each MCP tool
    mcp_manager = await get_mcp_manager()
    tools = mcp_manager.get_available_tools()
    
    for tool in tools:
        if tool.server_name == "firecrawl-mcp":
            # Register firecrawl-specific commands
            discord_plugin.add_slash_command(
                name=f"scrape_{tool.name}",
                description=f"Use {tool.name} from firecrawl-mcp",
                handler=create_tool_handler(tool)
            )
```

## Troubleshooting

### Commands not showing in Discord
1. Check that the bot has appropriate permissions
2. Verify commands were registered successfully (check logs)
3. Try manually syncing: `discord_plugin.sync_slash_commands()`
4. For guild commands, ensure the bot is in the correct guild

### Command registration fails
1. Check that command names are unique
2. Verify the Discord bot plugin is loaded and running
3. Check logs for specific error messages
4. Ensure command handlers are async functions

### Permissions issues
The bot needs these Discord permissions:
- `applications.commands` (for slash commands)
- `Send Messages` (for responses)
- `Use Slash Commands` (to register commands)

### MCP Integration Issues
1. Ensure MCP servers are properly configured and running
2. Check that tools are available via `nagatha mcp status`
3. Verify error handling in command handlers
4. Test MCP tool calls independently before integrating with Discord

## Advanced Patterns

### Command Groups
For complex plugins, you can create command groups:

```python
from discord import app_commands

# Create a command group
group = app_commands.Group(name="myplugin", description="My plugin commands")

@group.command(name="action1")
async def action1(interaction: discord.Interaction):
    await interaction.response.send_message("Action 1")

@group.command(name="action2") 
async def action2(interaction: discord.Interaction):
    await interaction.response.send_message("Action 2")

# Register the group
discord_plugin.bot.tree.add_command(group)
```

### Contextual Commands
Commands that adapt based on context:

```python
async def contextual_handler(interaction: discord.Interaction):
    # Check user permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admin only!", ephemeral=True)
        return
    
    # Check channel type
    if isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("This command only works in servers")
        return
    
    # Proceed with command
    await interaction.response.send_message("Command executed!")
```

### Persistent State
Commands that maintain state across interactions:

```python
class StatefulPlugin(SimplePlugin):
    def __init__(self, config):
        super().__init__(config)
        self.user_sessions = {}  # Store user session data
    
    async def handle_stateful_command(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"step": 0}
        
        session = self.user_sessions[user_id]
        
        if session["step"] == 0:
            session["step"] = 1
            await interaction.response.send_message("Step 1: What would you like to do?")
        elif session["step"] == 1:
            session["step"] = 0
            await interaction.response.send_message("Step 2: Processing your request...")
```

This enables a fully extensible system where any component can contribute Discord slash commands to enhance the user experience, with deep integration into Nagatha's MCP and plugin systems.