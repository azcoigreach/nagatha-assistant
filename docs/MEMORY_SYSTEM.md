# Nagatha Assistant Memory System

The Nagatha Assistant Memory System provides persistent storage and retrieval of information across conversations and sessions. This document explains how to use the memory system both as an end user and as a developer.

## Overview

The memory system allows Nagatha to:
- **Remember user preferences** across sessions
- **Store conversation context** and session state
- **Keep track of command history** for reference
- **Learn and store facts** about users and topics
- **Cache temporary data** with automatic expiration
- **Search across stored information** efficiently

## Memory Sections

The memory system is organized into logical sections, each with different persistence characteristics:

### 1. User Preferences (`user_preferences`)
**Persistence**: Permanent  
**Purpose**: Store user settings and preferences that persist across all sessions

**Examples**:
- Theme preferences (dark/light mode)
- Language settings
- Notification preferences
- Default AI model choices
- Personal information and preferences

### 2. Session State (`session_state`)
**Persistence**: Session-scoped  
**Purpose**: Store temporary state and context for the current conversation session

**Examples**:
- Current task or focus area
- Conversation context and topics
- Progress tracking within a session
- Temporary user inputs or selections

### 3. Command History (`command_history`)
**Persistence**: Permanent  
**Purpose**: Keep a searchable history of user commands and interactions

**Examples**:
- Previously executed commands
- Command responses and outcomes
- Usage patterns for learning
- Troubleshooting and audit trail

### 4. Facts (`facts`)
**Persistence**: Permanent  
**Purpose**: Store long-term knowledge and facts that Nagatha learns about users and topics

**Examples**:
- User's work schedule and preferences
- Important dates and deadlines
- Project information and context
- Personal facts and relationships
- Technical knowledge and procedures

### 5. Temporary (`temporary`)
**Persistence**: TTL-based (expires automatically)  
**Purpose**: Store short-term data that should automatically expire

**Examples**:
- API tokens and temporary credentials
- Cache data and computed results
- Session-specific temporary state
- Rate limiting and throttling data

## Using the Memory System

### Command Line Interface (CLI)

The memory system can be managed through dedicated CLI commands:

#### Set a Memory Value
```bash
# Set a user preference
nagatha memory set user_preferences theme dark

# Set session state (requires session ID)
nagatha memory set session_state current_task "writing documentation" --session 12345

# Set a fact with source attribution
nagatha memory set facts python_version "Python 3.12+" --source "system_info"

# Set temporary data with TTL (time-to-live)
nagatha memory set temporary api_token "token123" --ttl 3600
```

#### Get a Memory Value
```bash
# Get a user preference
nagatha memory get user_preferences theme

# Get session state
nagatha memory get session_state current_task --session 12345

# Get a fact
nagatha memory get facts python_version

# Get with default value if not found
nagatha memory get user_preferences language --default "en"
```

#### List Keys in a Section
```bash
# List all user preferences
nagatha memory list user_preferences

# List session state for a specific session
nagatha memory list session_state --session 12345

# List facts
nagatha memory list facts
```

#### Search Within a Section
```bash
# Search user preferences for "theme"
nagatha memory search user_preferences theme

# Search facts for "python"
nagatha memory search facts python

# Search command history for specific commands
nagatha memory search command_history "help"
```

#### Clear Memory Sections
```bash
# Clear all temporary data
nagatha memory clear temporary

# Clear session state for a specific session
nagatha memory clear session_state --session 12345

# WARNING: Clear all user preferences (use with caution)
nagatha memory clear user_preferences --confirm
```

#### View Memory Statistics
```bash
# Show usage statistics for all sections
nagatha memory stats

# Show statistics for a specific section
nagatha memory stats user_preferences
```

### Programmatic API

The memory system can also be used programmatically in Python scripts:

```python
import asyncio
from nagatha_assistant.core.memory import ensure_memory_manager_started

async def example_usage():
    # Start the memory system
    memory = await ensure_memory_manager_started()
    
    # User preferences
    await memory.set_user_preference("theme", "dark")
    theme = await memory.get_user_preference("theme")
    
    # Session state
    session_id = 12345
    await memory.set_session_state(session_id, "current_task", "analysis")
    task = await memory.get_session_state(session_id, "current_task")
    
    # Command history
    await memory.add_command_to_history("help", "Available commands: ...", session_id)
    history = await memory.get_command_history(session_id, limit=10)
    
    # Facts storage
    await memory.store_fact("meeting_time", "Daily standup at 9 AM", source="calendar")
    fact = await memory.get_fact("meeting_time")
    
    # Temporary data with TTL
    await memory.set_temporary("cache_key", {"data": "value"}, ttl_seconds=3600)
    cached = await memory.get_temporary("cache_key")
    
    # Search across sections
    results = await memory.search("facts", "meeting")

# Run the example
asyncio.run(example_usage())
```

### Integration with Nagatha Conversations

The memory system is automatically integrated with Nagatha's conversational AI. When you chat with Nagatha, it can:

- **Access your preferences** to personalize responses
- **Remember conversation context** from previous sessions
- **Store and recall facts** you tell it
- **Learn from your interactions** over time

**Example conversation showing memory usage:**

```
User: "Remember that I prefer dark themes in all applications"
Nagatha: "I'll remember your preference for dark themes. I've stored this in your user preferences."

User: "What's my theme preference?"
Nagatha: "According to your stored preferences, you prefer dark themes in all applications."

User: "Set a reminder that my team meeting is every Tuesday at 2 PM"
Nagatha: "I've stored this fact about your team meeting schedule. I can remind you about this in future conversations."
```

## Practical Use Cases

### 1. Personal Assistant Setup
```bash
# Configure your preferences
nagatha memory set user_preferences name "John Doe"
nagatha memory set user_preferences timezone "America/New_York"
nagatha memory set user_preferences work_hours "9AM-5PM"
nagatha memory set user_preferences notification_style "minimal"
```

### 2. Project Context Management
```bash
# Store project information
nagatha memory set facts current_project "Q2 Marketing Campaign"
nagatha memory set facts project_deadline "2024-06-30"
nagatha memory set facts project_team "Alice, Bob, Carol"
nagatha memory set facts project_budget "50000"

# Query project information
nagatha memory search facts project
```

### 3. Learning and Knowledge Building
```bash
# Store technical facts as you learn them
nagatha memory set facts docker_basics "Docker containers provide isolated runtime environments" --source "training"
nagatha memory set facts sql_optimization "Use indexes on frequently queried columns" --source "experience"
nagatha memory set facts api_endpoint "Production API at https://api.example.com/v1" --source "documentation"

# Search your knowledge base
nagatha memory search facts docker
nagatha memory search facts optimization
```

### 4. Session Context Tracking
```bash
# During a work session
nagatha memory set session_state current_focus "code_review" --session 001
nagatha memory set session_state files_reviewed "3" --session 001
nagatha memory set session_state next_action "merge_pull_request" --session 001

# Check your session state
nagatha memory get session_state current_focus --session 001
```

### 5. Temporary Data Management
```bash
# Store temporary authentication tokens
nagatha memory set temporary github_token "ghp_xxxx" --ttl 7200  # 2 hours

# Cache computation results
nagatha memory set temporary analysis_results '{"total": 1500, "average": 75}' --ttl 3600  # 1 hour

# Check if temporary data exists
nagatha memory get temporary github_token
```

## Advanced Features

### Event Integration
The memory system publishes events when data is created, updated, or deleted. This allows other parts of Nagatha to react to memory changes:

- `memory.entry.created` - When new data is stored
- `memory.entry.updated` - When existing data is modified
- `memory.entry.deleted` - When data is removed
- `memory.search.performed` - When a search is executed

### Storage Backends
The memory system supports multiple storage backends:

- **Database Backend** (default): Persistent storage using SQLite/PostgreSQL
- **In-Memory Backend**: Fast temporary storage for testing and caching

### TTL (Time-To-Live) Support
Temporary data can be set with automatic expiration:

```bash
# Data expires after 1 hour (3600 seconds)
nagatha memory set temporary session_token "abc123" --ttl 3600

# Data expires after 24 hours
nagatha memory set temporary daily_cache '{"count": 42}' --ttl 86400
```

### Cross-Session Context
The memory system enables Nagatha to maintain context across multiple conversation sessions, providing continuity in your interactions.

## Data Types and Serialization

The memory system can store any Python data type:
- Strings, numbers, booleans
- Lists, dictionaries, and nested structures
- Custom objects (with proper serialization)
- JSON-compatible data structures

All data is automatically serialized and deserialized transparently.

## Best Practices

### 1. Choose the Right Section
- Use `user_preferences` for settings that should persist forever
- Use `session_state` for temporary conversation context
- Use `facts` for important information you want to remember
- Use `temporary` for data that should expire automatically

### 2. Use Descriptive Keys
```bash
# Good: Descriptive and hierarchical
nagatha memory set user_preferences ui_theme "dark"
nagatha memory set facts work_schedule_monday "9AM-5PM"

# Less ideal: Vague or unclear
nagatha memory set user_preferences setting1 "dark"
nagatha memory set facts info "9AM-5PM"
```

### 3. Include Source Attribution for Facts
```bash
# Include source information for facts
nagatha memory set facts api_rate_limit "1000 requests/hour" --source "API documentation"
nagatha memory set facts meeting_room "Conference Room A" --source "booking confirmation"
```

### 4. Use Appropriate TTL for Temporary Data
```bash
# Short TTL for sensitive data
nagatha memory set temporary auth_token "token123" --ttl 1800  # 30 minutes

# Longer TTL for cache data
nagatha memory set temporary daily_stats '{"total": 100}' --ttl 86400  # 24 hours
```

### 5. Regular Cleanup
```bash
# Periodically clean up unnecessary data
nagatha memory clear temporary  # Automatic with TTL, but can be manual
nagatha memory stats  # Monitor usage
```

## Security Considerations

- **Sensitive Data**: Be cautious when storing sensitive information; use temporary storage with appropriate TTL for credentials
- **Access Control**: Memory is currently user-scoped; future versions may include additional access controls
- **Data Persistence**: Remember that facts and preferences persist across sessions and system restarts

## Troubleshooting

### Common Issues

**Memory not persisting between sessions:**
- Check that you're using the correct section (not `temporary` or `session_state` for permanent data)
- Verify database connectivity if using database backend

**Performance issues with large datasets:**
- Use search functionality instead of listing all keys
- Consider using TTL for data that doesn't need permanent storage
- Monitor memory usage with `nagatha memory stats`

**Data not found:**
- Check that you're using the correct section and key names
- Use `nagatha memory list <section>` to see available keys
- Remember that session_state requires a session ID

### Debug Commands
```bash
# Check memory system status
nagatha memory stats

# List all keys in a section
nagatha memory list user_preferences

# Search for specific data
nagatha memory search facts "your search term"
```

## Future Enhancements

The memory system is designed to be extensible. Future versions may include:
- **Memory sharing** between users (with proper permissions)
- **Memory export/import** for backup and migration
- **Advanced search** with full-text indexing
- **Memory analytics** and usage insights
- **Integration with external knowledge bases**

For the latest features and updates, see the [CHANGELOG.md](../CHANGELOG.md) file.