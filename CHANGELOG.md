# Changelog

All notable changes to this project will be documented in this file.

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