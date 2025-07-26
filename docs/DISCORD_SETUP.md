# Discord Bot Setup Guide

This guide will help you set up the Discord bot integration for Nagatha Assistant.

## Prerequisites

- Discord account
- Access to Discord Developer Portal
- Nagatha Assistant installed and configured

## Setting Up Your Discord Bot

### 1. Create a Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Give your application a name (e.g., "Nagatha Assistant")
4. Click "Create"

### 2. Create a Bot User

1. In your application settings, go to the "Bot" section
2. Click "Add Bot"
3. Confirm by clicking "Yes, do it!"
4. **Important**: Under "Privileged Gateway Intents", enable:
   - **Message Content Intent** (required for the bot to read message content)
   - Server Members Intent (optional, for advanced features)
   - Presence Intent (optional, for status features)

### 3. Get Your Bot Token

1. In the Bot section, under "Token", click "Copy"
2. **Keep this token secure** - treat it like a password
3. Never share this token publicly or commit it to version control

### 4. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here  # Optional: limits bot to specific server
DISCORD_COMMAND_PREFIX=!  # Optional: defaults to !
```

To find your Guild ID:
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click on your server name
3. Click "Copy Server ID"

### 5. Invite the Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Under "Scopes", select:
   - `bot`
   - `applications.commands` (for slash commands)
3. Under "Bot Permissions", select:
   - Send Messages
   - Read Message History
   - View Channels
   - Use Slash Commands
   - Add additional permissions as needed
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

## Using the Discord Bot

### CLI Commands

Once configured, you can manage the Discord bot using these commands:

```bash
# Check Discord bot setup and configuration
nagatha discord setup

# Get bot status
nagatha discord status

# Start the Discord bot (runs in background)
nagatha discord start

# Stop the Discord bot
nagatha discord stop
```

### Auto-Start Configuration

You can configure the Discord bot to start automatically when Nagatha starts by setting the `auto_start` option in the plugin configuration:

```json
{
  "name": "discord_bot",
  "config": {
    "auto_start": true,
    "command_prefix": "!"
  }
}
```

### Available Bot Commands

The bot provides both slash commands and legacy prefix commands:

#### Slash Commands (Modern)
- `/chat <message> [private]` - Chat with Nagatha AI assistant
- `/status` - Get system status and plugin information
- `/help` - Show help information

#### Legacy Prefix Commands (Backward Compatibility)
- `!ping` - Test bot connectivity (responds with "Pong!")
- `!hello` - Greeting command

### Basic Usage Example

1. Configure your bot token in `.env`
2. Start the bot:
   ```bash
   nagatha discord start
   ```
3. In your Discord server, use slash commands like `/chat Hello Nagatha!`
4. The bot will respond with AI-generated responses

## Integration with Nagatha's Core Systems

The Discord bot integrates deeply with Nagatha's core systems:

### Event System Integration
- Publishes events for message reception, bot status changes, and errors
- Subscribes to system events for coordinated startup/shutdown
- Enables other plugins to react to Discord activities

### MCP Server Integration
- The `/status` command shows connected MCP servers and available tools
- Plugins can register custom slash commands that integrate with MCP tools
- Enables AI-powered responses using all available MCP capabilities

### Plugin System Integration
- Built as a plugin that can be enabled/disabled
- Provides APIs for other plugins to register custom commands
- Integrates with the plugin manager for coordinated lifecycle management

## Docker Deployment

For Docker deployment, ensure your environment variables are passed to the container:

### Docker Compose Example

```yaml
version: '3.8'
services:
  nagatha:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
      - DISCORD_GUILD_ID=${DISCORD_GUILD_ID}
      - DISCORD_COMMAND_PREFIX=!
    volumes:
      - ./data:/app/data
```

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nagatha-assistant
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nagatha-assistant
  template:
    metadata:
      labels:
        app: nagatha-assistant
    spec:
      containers:
      - name: nagatha
        image: nagatha-assistant:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: nagatha-secrets
              key: openai-api-key
        - name: DISCORD_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: nagatha-secrets
              key: discord-bot-token
        - name: DISCORD_COMMAND_PREFIX
          value: "!"
```

## Troubleshooting

### Common Issues

1. **Bot Token Invalid**
   - Verify the token is copied correctly
   - Regenerate the token if needed
   - Ensure no extra spaces or characters

2. **Bot Not Responding**
   - Check that Message Content Intent is enabled
   - Verify the bot has proper permissions in your server
   - Check bot status with `nagatha discord status`

3. **Permission Errors**
   - Ensure the bot role has proper permissions
   - Check channel-specific permissions
   - Bot needs "Send Messages" and "View Channels" at minimum

4. **Connection Issues**
   - Check your internet connection
   - Verify Discord's service status
   - Check Nagatha logs for error messages

5. **Slash Commands Not Appearing**
   - Ensure the bot has `applications.commands` scope
   - Check that commands were synced successfully
   - Verify the bot is in the correct guild (if using guild-specific commands)

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export LOG_LEVEL=DEBUG
nagatha discord start
```

### Getting Help

If you encounter issues:

1. Check the Nagatha logs for error messages
2. Verify your Discord bot configuration
3. Test with basic commands like `/chat Hello`
4. Create an issue on the GitHub repository with:
   - Error messages (remove sensitive tokens)
   - Steps to reproduce
   - Your environment details

## Security Best Practices

1. **Never share your bot token** - treat it like a password
2. **Use environment variables** - don't hardcode tokens
3. **Limit bot permissions** - only grant necessary permissions
4. **Regular token rotation** - regenerate tokens periodically
5. **Monitor bot activity** - watch for unusual behavior
6. **Use guild-specific commands** - when possible, limit commands to specific servers

## Architecture Overview

The Discord bot is built with a modular architecture:

### Core Components
- **DiscordBotPlugin**: Main plugin that manages the bot lifecycle
- **NagathaDiscordBot**: Custom Discord.py bot class with Nagatha integration
- **SlashCommandManager**: Manages slash command registration and routing
- **Event Integration**: Publishes and subscribes to system events

### Plugin Integration
- **Command Registration**: Plugins can register custom slash commands
- **Event Handling**: Plugins can react to Discord events
- **MCP Integration**: Commands can utilize MCP server tools
- **Lifecycle Management**: Coordinated startup/shutdown with other plugins

### Extensibility
- **Custom Commands**: Plugins can add their own slash commands
- **Event-Driven**: Other systems can react to Discord activities
- **MCP Tools**: Commands can leverage any available MCP server tools
- **Plugin APIs**: Rich APIs for plugin integration

## Future Features

The Discord bot foundation is designed to support future enhancements:

- **Advanced AI Integration**: Deeper integration with Nagatha's conversation system
- **Voice Channel Support**: Voice interaction capabilities
- **Scheduled Messages**: Automated reminders and notifications
- **Server Moderation**: Advanced moderation features
- **Custom Command Creation**: User-defined commands
- **Multi-Server Management**: Centralized management of multiple servers
- **Analytics Dashboard**: Usage statistics and insights

## Contributing

To contribute to the Discord bot functionality:

1. Follow the existing plugin architecture
2. Add tests for new features
3. Update documentation
4. Ensure security best practices
5. Test with real Discord servers

The Discord bot code is located in:
- Plugin: `src/nagatha_assistant/plugins/discord_bot.py`
- Slash Commands: `src/nagatha_assistant/core/slash_commands.py`
- Command Manager: `src/nagatha_assistant/core/slash_command_manager.py`
- CLI Commands: `src/nagatha_assistant/cli.py`
- Tests: `tests/test_discord_*.py`