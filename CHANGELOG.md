## [0.10.0] - 2025-07-26

### Added
- **Celery Task Scheduling System**: Complete distributed task execution and scheduling capabilities
  - Redis-based message broker and result backend
  - Celery Beat scheduler for recurring and one-time tasks
  - Natural language time parsing (e.g., "every 5 minutes", "tomorrow at 2pm")
  - Task persistence across application restarts
  - Comprehensive CLI commands for service management and task control
  - Flower web-based monitoring interface
  - Task execution history with detailed tracking
  - Integration with existing event bus and plugin systems
  - Built-in system tasks (health checks, backups, cleanup, notifications)

### Changed
- Enhanced CLI with new `celery` command group for task management
- Extended plugin system with TaskManagerPlugin for programmatic task control
- Updated requirements.txt with Celery, Redis, and related dependencies

### Fixed
- Event bus integration for task lifecycle events
- Natural language parsing for time specifications including seconds
- Task persistence and schedule reloading functionality

## [0.9.0] - 2025-07-26

### Current Application State
Nagatha Assistant is now a comprehensive AI agent platform with:

**Core Systems:**
- **AI Agent**: GPT-4 powered conversations with context-aware responses
- **MCP Integration**: Model Context Protocol for extensible tool integration
- **Plugin System**: Extensible architecture with event-driven communication
- **Event Bus**: Centralized event system for component coordination
- **Memory System**: Persistent cross-session storage with TTL support
- **Database**: SQLite with Alembic migrations, PostgreSQL support

**User Interfaces:**
- **Dashboard UI**: Multi-panel interface with real-time monitoring (recommended)
- **Textual UI**: Terminal-based chat interface
- **Discord Bot**: Slash commands with plugin extensibility
- **CLI**: Comprehensive command-line interface
- **Programmatic API**: Python library for integration

**Core Features:**
- **Notes**: Rich note-taking with markdown, tags, and full-text search
- **Tasks**: Complete task management with priorities, due dates, and statuses
- **Reminders**: Automated scheduling with recurring patterns
- **Web Research**: MCP-powered scraping and content analysis
- **Usage Tracking**: Token usage monitoring with cost analysis and reset functionality

**Integration Capabilities:**
- **MCP Servers**: Support for firecrawl-mcp, mastodon-mcp, memory-mcp, and custom servers
- **Discord Integration**: Slash commands, plugin extensibility, MCP tool integration
- **Event System**: Publish/subscribe pattern with priorities and history
- **Plugin Development**: Easy custom plugin creation and integration

### Added
- Enhanced Dashboard UI with multi-panel layout and real-time monitoring
- Persistent Memory System with CLI, AI tools, and event integration
- Discord Bot integration with slash commands and plugin extensibility
- Event Bus System for centralized component communication
- Plugin System with lifecycle management and dependency resolution
- Usage tracking with reset functionality and enhanced metrics
- Comprehensive documentation for all major systems

### Changed
- Refactored architecture to use event-driven plugin system
- Enhanced MCP integration with on-demand connections
- Improved conversation handling with better context management
- Updated all documentation to reflect current functionality

### Fixed
- Token usage tracking for multi-turn conversations
- Database migration handling for existing installations
- Event system memory management and cleanup

## [0.8.0] - 2025-05-07

### Changed
- Refactor to use Model Context Protocol (MCP) for improved integration and standardized communication.

## [0.7.2] - 2025-05-06

### Added
- Weather features: Introduce new weather forecast module, real-time temperature checks, and severe weather alerts.


### Added
- Introduce `run` CLI command (`nagatha run`) to launch the Textual UI chat client.

## [0.7.0] - 2025-05-05

### Added
- Renamed CLI command `serve` to `server` for starting the core API service.
- Updated documentation (README, docs) to reflect the new `server` command.

## [0.5.0] - 2025-05-03

### Added
- CLI commands for database management: `db upgrade` and `db backup`.

### Changed
- `db upgrade` now automatically stamps existing schemas to the latest Alembic revision when tables already exist.

## [0.4.0] - 2025-05-03

### Added
- Task and Reminder models with tags, priorities, statuses, due dates, and associations (migration 0003).
- Modules for tasks (`modules/tasks.py`) and reminders (`modules/reminders.py`) with full CRUD and scheduling support.
- Background scheduler for automated notifications (via `start_scheduler`).
- Tests for tasks (`tests/test_tasks_module.py`) and reminders (`tests/test_reminders_module.py`).
- README documentation for time management features.

### Changed
- Bumped project version to 0.4.0 in setup.py and `__init__.py`.
## [0.3.0] - 2025-05-03

### Added
- Database models for notes and tags (migration 0002).
- Notes module with functions `take_note`, `get_note`, and `search_notes`.
- Tests for notes module (`tests/test_notes_module.py`).
- Documentation updates: README and CHANGELOG.

### Changed
- Bumped project version to 0.3.0 in setup.py and `__init__.py`.

## [0.2.0] - 2025-05-03

### Added
- NistTimePlugin for official time retrieval from NIST with timezone support.
- `CHANGELOG.md` file to track project changes.
- Documentation updates: README and docs/plugins.md.

### Changed
- Bumped project version to 0.2.0 in setup.py and `__init__.py`.

## [0.1.0] - Initial release
Original feature set including note-taking, transcription, tasks, reminders, web search, and plugin architecture.