# Copilot Instructions for Nagatha Assistant

## Project Overview

Nagatha Assistant is a Python-based personal AI agent that uses the Model Context Protocol (MCP) for extensible tool integration. The project follows async-first architecture with SQLAlchemy for database management, OpenAI for AI conversations, and a modular design pattern.

## Technology Stack

- **Python 3.11+** (required for modern async features)
- **SQLAlchemy** with async support (aiosqlite)
- **Alembic** for database migrations
- **OpenAI API** for AI conversations
- **Textual** for TUI interface
- **Click** for CLI interface
- **MCP (Model Context Protocol)** for tool integration
- **Pytest** for testing with async support

## Code Style and Patterns

### General Guidelines

1. **Use type hints** for all function parameters and return values
2. **Follow PEP 8** style guidelines
3. **Use async/await** for all I/O operations
4. **Implement proper error handling** with try/catch blocks
5. **Use structured logging** via the project's logger utility
6. **Write docstrings** for all public functions and classes

### File Organization

```
src/nagatha_assistant/
├── cli.py                 # Click-based command-line interface
├── ui.py                  # Textual UI implementation
├── core/                  # Core system components
│   ├── agent.py          # Main AI agent and conversation handling
│   ├── mcp_manager.py    # MCP server connections and tool management
│   ├── personality.py    # Nagatha's character and system prompts
│   ├── event_bus.py      # Event-driven architecture
│   └── event.py          # Event definitions and types
├── db.py                 # Database configuration and connection management
├── db_models.py          # SQLAlchemy models for all entities
├── utils/                # Utilities and helpers
│   ├── logger.py         # Structured logging
│   └── usage_tracker.py  # Token usage and cost tracking
└── __init__.py           # Package initialization and version
```

### Database Patterns

1. **Use async SQLAlchemy** with `SessionLocal()` context manager
2. **Follow the established model patterns** in `db_models.py`
3. **Use Alembic migrations** for schema changes
4. **Implement proper relationships** between models
5. **Use server_default** for database-level defaults

Example database operation:
```python
async with SessionLocal() as session:
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
    result = await session.execute(stmt)
    return result.scalars().all()
```

### Async Patterns

1. **Always use async/await** for database operations, API calls, and I/O
2. **Use asyncio.create_task()** for fire-and-forget operations
3. **Implement proper cleanup** in shutdown functions
4. **Handle async context managers** correctly

### Error Handling

1. **Use structured logging** for errors:
```python
from nagatha_assistant.utils.logger import setup_logger_with_env_control
logger = setup_logger_with_env_control()
logger.error(f"Error calling MCP tool '{tool_name}': {e}")
```

2. **Implement graceful degradation** for MCP tool failures
3. **Return meaningful error messages** to users
4. **Use try/catch blocks** around external API calls

### Testing Patterns

1. **Use pytest with async support** (configured in pytest.ini)
2. **Write async test functions** with proper fixtures
3. **Use conftest.py** for shared test fixtures
4. **Test both success and failure scenarios**
5. **Mock external dependencies** (OpenAI, MCP servers)

Example test pattern:
```python
import pytest
from nagatha_assistant.core.agent import start_session

@pytest.mark.asyncio
async def test_start_session():
    session_id = await start_session()
    assert session_id > 0
```

## MCP Integration Guidelines

1. **Use the MCP manager** for all tool interactions
2. **Handle MCP server failures gracefully**
3. **Implement tool selection logic** based on user intent
4. **Use the event bus** for MCP-related events
5. **Follow the established MCP patterns** in `mcp_manager.py`

## CLI Development

1. **Use Click decorators** for command definitions
2. **Follow the established CLI patterns** in `cli.py`
3. **Implement proper help text** for all commands
4. **Use async command functions** when needed
5. **Handle command-line arguments** with proper validation

## UI Development (Textual)

1. **Follow Textual framework patterns** in `ui.py`
2. **Use async event handlers** for UI interactions
3. **Implement proper screen management**
4. **Handle user input validation**
5. **Use the established UI component patterns**

## Environment and Configuration

1. **Use environment variables** for configuration
2. **Follow the established env var patterns**:
   - `OPENAI_API_KEY` - OpenAI API key
   - `DATABASE_URL` - Database connection string
   - `LOG_LEVEL` - Logging level
   - `CONTEXT_MEMORY_MESSAGES` - Context memory limit

3. **Use python-dotenv** for local development
4. **Implement proper configuration validation**

## Event System

1. **Use the event bus** for system-wide communication
2. **Follow the established event patterns** in `event.py`
3. **Use proper event priorities** (HIGH, NORMAL, LOW)
4. **Implement event handlers** for system events
5. **Use the event system** for cross-module communication

## Security Considerations

1. **Never hardcode API keys** - use environment variables
2. **Validate user input** before processing
3. **Use proper SQL injection prevention** (SQLAlchemy handles this)
4. **Implement proper error messages** that don't leak sensitive info
5. **Use secure defaults** for all configurations

## Performance Guidelines

1. **Use async operations** for all I/O
2. **Implement proper connection pooling** for database
3. **Use efficient database queries** with proper indexing
4. **Implement caching** where appropriate
5. **Monitor token usage** and costs

## Documentation Standards

1. **Write clear docstrings** for all public functions
2. **Include type hints** in all function signatures
3. **Document complex business logic** with inline comments
4. **Update README.md** for new features
5. **Maintain CHANGELOG.md** for version changes

## Common Patterns to Follow

### Database Session Management
```python
async with SessionLocal() as session:
    # Database operations
    await session.commit()
```

### MCP Tool Usage
```python
mcp_manager = await get_mcp_manager()
result = await mcp_manager.call_tool(tool_name, arguments)
```

### Event Publishing
```python
event_bus = get_event_bus()
event = create_agent_event(event_type, session_id, data)
await event_bus.publish(event)
```

### Logging
```python
logger = setup_logger_with_env_control()
logger.info("Operation completed successfully")
logger.error(f"Operation failed: {error}")
```

### Error Handling
```python
try:
    result = await some_async_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    # Handle error appropriately
    raise
```

## What NOT to Do

1. **Don't use synchronous I/O** in async functions
2. **Don't hardcode configuration values**
3. **Don't ignore error handling**
4. **Don't bypass the established patterns**
5. **Don't use global variables** for state management
6. **Don't implement features without tests**
7. **Don't break the async event loop**

## Testing Requirements

1. **Write tests for all new features**
2. **Maintain test coverage** above 80%
3. **Use async test fixtures** properly
4. **Mock external dependencies**
5. **Test both success and error paths**

## Migration Guidelines

1. **Use Alembic** for all database schema changes
2. **Write migration scripts** for data transformations
3. **Test migrations** on development data
4. **Document breaking changes** in CHANGELOG.md
5. **Provide rollback procedures** for migrations

## Deployment Considerations

1. **Use environment variables** for all configuration
2. **Implement proper logging** for production
3. **Use connection pooling** for database
4. **Implement health checks** for services
5. **Use proper process management** (systemd, supervisor, etc.)

## Code Review Checklist

When reviewing code, ensure:
- [ ] Type hints are present
- [ ] Async/await is used correctly
- [ ] Error handling is implemented
- [ ] Tests are included
- [ ] Documentation is updated
- [ ] Logging is appropriate
- [ ] Security considerations are addressed
- [ ] Performance implications are considered
- [ ] Code follows established patterns
- [ ] No hardcoded values
