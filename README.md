# Nagatha Assistant

Nagatha Assistant is a powerful, modular personal AI agent built in Python that leverages the Model Context Protocol (MCP) for extensible tool integration. Named after Agatha Christie, Nagatha combines conversational AI with intelligent tool usage to help with tasks like note-taking, task management, web research, content analysis, and much more.

## 🌟 Key Features

- **🧠 Intelligent AI Agent**: Context-aware conversations with GPT-4 powered responses
- **🔧 MCP Integration**: Extensible tool system using Model Context Protocol
- **📝 Note Management**: Rich note-taking with markdown support, tags, and full-text search
- **📋 Task & Reminder System**: Complete task management with priorities, due dates, and automated notifications
- **🔍 Web Research**: Advanced web scraping, searching, and content analysis via MCP tools
- **🐘 Mastodon Integration**: User profile analysis and moderation tools for Mastodon instances
- **🤖 Discord Bot**: Native Discord integration for AI assistance in Discord servers
- **💬 Multiple Interfaces**: Command-line, Textual UI, Discord, and programmatic API access
- **📊 Usage Tracking**: Automatic token usage and cost monitoring
- **🗄️ Database Management**: SQLite with Alembic migrations for schema versioning
- **🧠 Persistent Memory System**: Cross-session storage with user preferences, facts, command history, and TTL support
- **📈 Background Processing**: Automated scheduler for reminders and notifications

## 🏗️ Architecture

Nagatha is built with a modular, async-first architecture:

```
src/nagatha_assistant/
├── cli.py                 # Click-based command-line interface
├── core/                  # Core system components
│   ├── agent.py          # Main AI agent and conversation handling
│   ├── mcp_manager.py    # MCP server connections and tool management
│   └── personality.py    # Nagatha's character and system prompts
├── db.py                 # Database configuration and connection management
├── db_models.py          # SQLAlchemy models for all entities
├── modules/              # Feature modules (notes, tasks, reminders)
│   ├── notes.py
│   ├── tasks.py
│   └── reminders.py
├── utils/                # Utilities and helpers
│   ├── logger.py         # Structured logging
│   └── usage_tracker.py  # Token usage and cost tracking
└── __init__.py           # Package initialization and version
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (required for modern async features)
- **Git** for version control
- **OpenAI API Key** for AI conversations
- **Optional**: MCP server dependencies (Node.js for npm packages, etc.)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AZcoigreach/nagatha-assistant.git
   cd nagatha-assistant
   ```

2. **Set up Python environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your settings:
   nano .env
   ```

   **Required environment variables:**
   ```bash
   # OpenAI Configuration
   OPENAI_API_KEY=sk-your-openai-api-key-here
   OPENAI_MODEL=gpt-4o-mini  # or gpt-4, gpt-3.5-turbo, etc.
   
   # Database
   DATABASE_URL=sqlite+aiosqlite:///nagatha.db  # Default SQLite
   
   # Logging
   LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
   NAGATHA_LOG_LEVEL_FILE=DEBUG
   NAGATHA_LOG_LEVEL_CHAT=WARNING
   
   # Memory and Context
   CONTEXT_MEMORY_MESSAGES=10  # Cross-session context messages
   
   # Timeouts
   OPENAI_TIMEOUT=60
   NAGATHA_MCP_TIMEOUT=10
   NAGATHA_CONVERSATION_TIMEOUT=120
   ```

4. **Set up MCP servers (optional but recommended):**
   ```bash
   cp mcp.json.template mcp.json
   # Edit mcp.json with your MCP server configurations
   nano mcp.json
   ```

5. **Initialize the database:**
   ```bash
   nagatha db upgrade
   ```

6. **Start Nagatha:**
   ```bash
   # Launch the interactive Textual UI
   nagatha run

   # OR start the core server (for API access)
   nagatha server --host 0.0.0.0 --port 8000
   ```

## 💬 Usage

### Interactive Chat (Textual UI)

The Textual UI provides a rich terminal interface for conversing with Nagatha:

```bash
nagatha run
```

**UI Commands:**
- `/help` - Show all available commands
- `/new` - Create a new conversation session
- `/sessions` - List all conversation sessions
- `/switch <id>` - Switch to a specific session
- `/history` - Show current session history
- `/context [N]` - Set cross-session context limit
- `/models` - List available OpenAI models
- `/usage` - Show token usage and costs
- `/clear` - Clear the screen
- `/quit` - Exit the application

### Command Line Interface

Nagatha provides comprehensive CLI commands for all functionality:

#### Chat Commands
```bash
# Session management
nagatha chat new                     # Create new conversation session
nagatha chat list                    # List all sessions
nagatha chat history <session_id>    # Show session history
nagatha chat send <session_id> "Hello Nagatha!" --context-limit 5

# Example conversation
nagatha chat send 1 "Take a note titled 'Meeting Notes' with content 'Discussed project timeline'"
nagatha chat send 1 "Search the web for recent AI developments"
nagatha chat send 1 "What tasks do I have due this week?"
```

#### Note Management
```bash
# Create notes
nagatha note add "Meeting Notes" "Discussed the Q1 roadmap" --tag work --tag meeting
nagatha note add "Recipe Ideas" "Try making sourdough bread" --tag cooking --tag personal

# Search and retrieve
nagatha note list                    # List all notes
nagatha note list --tag work         # Filter by tag
nagatha note get 1                   # Get specific note
nagatha note search "roadmap"        # Full-text search
nagatha note search --tag cooking    # Search by tag

# Management
nagatha note update 1 --title "Updated Title" --content "New content"
nagatha note delete 1
```

#### Task Management
```bash
# Create tasks
nagatha task add "Complete project proposal" "Write the Q2 project proposal document" \
  --due-at "2025-05-15T17:00:00" --priority high --tag work

nagatha task add "Buy groceries" "Weekly grocery shopping" \
  --due-at "2025-05-08T10:00:00" --priority medium --tag personal

# List and filter
nagatha task list                    # All tasks
nagatha task list --status pending  # Only pending tasks
nagatha task list --tag work        # Work-related tasks
nagatha task list --priority high   # High-priority tasks

# Task operations
nagatha task get 1                   # View task details
nagatha task update 1 --priority medium --status in_progress
nagatha task complete 1             # Mark as completed
nagatha task close 1                # Archive the task
nagatha task delete 1               # Remove completely
```

#### Reminder System
```bash
# Create reminders
nagatha reminder add 1 "2025-05-10T09:00:00" --message "Project deadline reminder"
nagatha reminder add 1 "2025-05-08T08:00:00" --message "Daily standup" --recurrence daily

# Manage reminders
nagatha reminder list                # All reminders
nagatha reminder list --task-id 1    # Reminders for specific task
nagatha reminder deliver 1           # Manually trigger reminder
nagatha reminder delete 1            # Remove reminder
```

#### Database Operations
```bash
# Database management
nagatha db upgrade                   # Run Alembic migrations
nagatha db backup                    # Create timestamped backup
nagatha db backup /path/to/backup.db # Backup to specific location

# System information
nagatha models                       # List available OpenAI models
nagatha usage                        # Show token usage and costs
```

#### MCP System
```bash
# MCP server management
nagatha mcp status                   # Show server status and available tools
nagatha mcp reload                   # Reconnect to all MCP servers
```

#### Memory System
```bash
# Set memory values
nagatha memory set user_preferences theme dark
nagatha memory set facts meeting_time "9 AM daily" --source "calendar"
nagatha memory set temporary api_token "token123" --ttl 3600

# Get memory values
nagatha memory get user_preferences theme
nagatha memory get facts meeting_time --format pretty

# Search and list
nagatha memory search facts "meeting"
nagatha memory list user_preferences
nagatha memory stats

# Clear data (be careful!)
nagatha memory clear temporary
nagatha memory clear facts --key "old_info"
```

For comprehensive memory system documentation, see **[docs/MEMORY_SYSTEM.md](docs/MEMORY_SYSTEM.md)**.

### Programmatic API

You can also use Nagatha programmatically in Python:

```python
import asyncio
from nagatha_assistant.core.agent import chat_with_user, create_session
from nagatha_assistant.modules.notes import take_note, search_notes
from nagatha_assistant.modules.tasks import add_task, list_tasks

async def example_usage():
    # Create a conversation session
    session = await create_session()
    session_id = session.id
    
    # Chat with Nagatha
    response = await chat_with_user(session_id, "Hello Nagatha, how are you today?")
    print(f"Nagatha: {response}")
    
    # Use modules directly
    note = await take_note("API Example", "This note was created via the API", ["demo", "api"])
    print(f"Created note: {note.title}")
    
    # Search notes
    results = await search_notes("API")
    print(f"Found {len(results)} notes matching 'API'")
    
    # Create a task
    task = await add_task(
        title="Learn Nagatha API",
        description="Explore the programmatic interface",
        due_at="2025-05-15T17:00:00",
        priority="medium",
        tags=["learning", "development"]
    )
    print(f"Created task: {task.title}")

# Run the example
asyncio.run(example_usage())
```

## 🔧 Configuration

### Environment Variables

Nagatha uses environment variables for configuration. All variables are optional with sensible defaults:

```bash
# === Core Configuration ===
OPENAI_API_KEY=sk-your-key-here              # Required for AI features
OPENAI_MODEL=gpt-4o-mini                     # Default model for conversations
OPENAI_TIMEOUT=60                            # API request timeout (seconds)

# === Database ===
DATABASE_URL=sqlite+aiosqlite:///nagatha.db  # Database connection string

# === Logging ===
LOG_LEVEL=INFO                               # Console log level
LOG_FILE=nagatha.log                         # Log file path (optional)
NAGATHA_LOG_LEVEL_FILE=DEBUG                 # File logging level
NAGATHA_LOG_LEVEL_CHAT=WARNING               # Chat interface log level

# === Memory & Context ===
CONTEXT_MEMORY_MESSAGES=10                   # Cross-session context messages
NAGATHA_USAGE_FILE=.nagatha_usage.json       # Usage tracking file

# === MCP Configuration ===
NAGATHA_MCP_TIMEOUT=10                       # MCP operation timeout
NAGATHA_MCP_CONNECTION_TIMEOUT=10            # Server connection timeout
NAGATHA_MCP_DISCOVERY_TIMEOUT=3              # Tool discovery timeout
NAGATHA_CONVERSATION_TIMEOUT=120             # Extended timeout for tool-heavy chats

# === Server Configuration ===
NAGATHA_HOST=localhost                       # Server bind address
NAGATHA_PORT=8000                            # Server port
```

### Database Configuration

Nagatha supports multiple database backends through SQLAlchemy:

```bash
# SQLite (default, recommended for personal use)
DATABASE_URL=sqlite+aiosqlite:///nagatha.db

# PostgreSQL (for production or shared usage)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/nagatha

# MySQL (alternative option)
DATABASE_URL=mysql+aiomysql://user:pass@localhost/nagatha
```

### Logging Configuration

Nagatha provides sophisticated logging with multiple levels:

- **File Logging**: Detailed logs for debugging and auditing
- **Chat Logging**: Selective logging visible in the chat interface
- **Console Logging**: Terminal output for CLI operations

```bash
# Log everything to file, but only warnings to chat
NAGATHA_LOG_LEVEL_FILE=DEBUG
NAGATHA_LOG_LEVEL_CHAT=WARNING
LOG_LEVEL=INFO  # Console level
```

## 📊 Features Deep Dive

### Conversation Memory

Nagatha maintains intelligent conversation context:

- **Session History**: Complete conversation history per session
- **Cross-Session Context**: Configurable inclusion of messages from other sessions
- **Context Limits**: Prevent token overflow with configurable limits
- **Memory Persistence**: All conversations stored in the database

### Usage Tracking

Automatic monitoring of API usage and costs:

```bash
nagatha usage
```

Output includes:
- Token usage per model (prompt + completion tokens)
- Estimated costs in USD
- Usage trends over time
- Model-specific breakdowns

### Task Management

Comprehensive task system with:

- **Priorities**: low, medium, high, urgent
- **Statuses**: pending, in_progress, completed, cancelled, closed
- **Due Dates**: Full datetime support with timezone awareness
- **Tags**: Flexible categorization and filtering
- **Associations**: Link tasks to notes and other entities

### Reminder System

Intelligent reminder scheduling:

- **One-time Reminders**: Specific datetime notifications
- **Recurring Reminders**: Daily, weekly, monthly patterns
- **Background Processing**: Automatic delivery via scheduler
- **Task Integration**: Reminders tied to specific tasks
- **Flexible Messaging**: Custom reminder content

### Advanced Search

Powerful search across all content:

```python
# Full-text search in notes
await search_notes("meeting notes project timeline")

# Tag-based filtering
await search_notes(tag="work")

# Combined search
await search_notes("roadmap", tag="planning")
```

## 🔌 MCP Integration

Nagatha leverages the Model Context Protocol for extensible tool integration. See `README_MCP.md` for comprehensive MCP documentation, including:

- Server configuration and management
- Tool discovery and registration
- Custom MCP server development
- Troubleshooting and debugging

### Popular MCP Servers

Nagatha works with any MCP-compatible server:

- **firecrawl-mcp**: Web scraping and search
- **nagatha-mastodon-mcp**: Mastodon user analysis and moderation
- **memory-mcp**: Knowledge graph and memory management
- **mcp-server-bootstrap**: Example/template server

## 🤖 Discord Bot Integration

Nagatha includes a Discord bot plugin that allows you to bring AI assistant capabilities directly to your Discord servers. The bot provides:

- **Basic Bot Commands**: Ping, hello, and status commands
- **Event-Driven Architecture**: Integrated with Nagatha's event system
- **Secure Token Management**: Environment variable-based configuration
- **Docker/Cloud Ready**: Designed for containerized deployments

### Quick Discord Setup

1. **Configure your bot token:**
   ```bash
   # Add to your .env file
   DISCORD_BOT_TOKEN=your_bot_token_here
   DISCORD_GUILD_ID=your_guild_id_here  # Optional
   DISCORD_COMMAND_PREFIX=!  # Optional, defaults to !
   ```

2. **Manage the Discord bot:**
   ```bash
   # Interactive setup guide
   nagatha discord setup
   
   # Start the bot
   nagatha discord start
   
   # Check status
   nagatha discord status
   
   # Stop the bot
   nagatha discord stop
   ```

3. **Test in Discord:**
   ```
   !ping    # Bot responds with "Pong!"
   !hello   # Greeting message
   ```

For complete setup instructions, bot permissions, Docker deployment, and troubleshooting, see **[docs/DISCORD_SETUP.md](docs/DISCORD_SETUP.md)**.

## 🧪 Development

### Testing

Nagatha follows test-driven development (TDD) practices:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=nagatha_assistant --cov-report=html

# Run specific test modules
pytest tests/test_agent.py
pytest tests/test_notes_module.py
pytest tests/test_tasks_module.py

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_chat"
```

### Code Quality

Ensure code quality with:

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

### Database Migrations

Create new database migrations with Alembic:

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "Add new feature"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Show migration history
alembic history
```

### Adding New Features

1. **Create Module**: Add new modules in `src/nagatha_assistant/modules/`
2. **Database Models**: Define models in `src/nagatha_assistant/db_models.py`
3. **CLI Commands**: Add commands to `src/nagatha_assistant/cli.py`
4. **Tests**: Write comprehensive tests in `tests/`
5. **Documentation**: Update README and add docstrings

## 🚀 Deployment

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

EXPOSE 8000
CMD ["python", "-m", "nagatha_assistant.cli", "server", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Considerations

- **Database**: Use PostgreSQL for production deployments
- **Environment**: Secure API keys and environment variables
- **Logging**: Configure appropriate log levels and rotation
- **Monitoring**: Set up health checks and metrics
- **Backup**: Regular database backups for data protection

## 🔧 Troubleshooting

### Common Issues

**Database Connection Errors:**
```bash
# Reset database
rm nagatha.db
nagatha db upgrade
```

**MCP Server Issues:**
```bash
# Check server status
nagatha mcp status

# Reload configuration
nagatha mcp reload
```

**API Key Problems:**
```bash
# Verify environment variables
echo $OPENAI_API_KEY

# Test with simple command
nagatha models
```

**Performance Issues:**
- Reduce `CONTEXT_MEMORY_MESSAGES` for faster responses
- Use `gpt-3.5-turbo` for cost-effective conversations
- Configure appropriate timeout values

### Debug Mode

Enable debug logging for troubleshooting:

```bash
export LOG_LEVEL=DEBUG
export NAGATHA_LOG_LEVEL_FILE=DEBUG
nagatha run
```

## 📈 Version History

See `CHANGELOG.md` for detailed version history and release notes.

**Current Version: 0.8.0**
- Refactored to use Model Context Protocol (MCP)
- Enhanced tool integration and management
- Improved conversation handling and context management
- Added comprehensive logging and debugging features

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI** for GPT models and API
- **Model Context Protocol** team for the MCP standard
- **Agatha Christie** for inspiration behind the name
- **Open Source Community** for the excellent Python ecosystem

---

**Need help?** Check `README_MCP.md` for MCP-specific documentation, or create an issue on GitHub for support.