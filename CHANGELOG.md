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