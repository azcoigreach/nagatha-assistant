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
            discord_plugin.add_slash_command(
                name="my_command",
                description="My custom slash command",
                handler=self.handle_my_command
            )
    
    async def handle_my_command(self, interaction: discord.Interaction):
        """Handle the /my_command slash command."""
        await interaction.response.send_message(
            "Hello from my custom command!",
            ephemeral=True
        )
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

## Integration with MCP Servers

MCP servers can also register slash commands by:
1. Implementing a tool that calls the Discord plugin's registration methods
2. Using the plugin system to create a wrapper plugin
3. Publishing events that the Discord plugin listens for

Example MCP tool for command registration:

```python
# In your MCP server
@server.tool("register_discord_command")
async def register_discord_command(name: str, description: str):
    """Register a Discord slash command from MCP."""
    # This would need to communicate with the running Nagatha instance
    # Implementation depends on your MCP server architecture
    pass
```

This enables a fully extensible system where any component can contribute Discord slash commands to enhance the user experience.