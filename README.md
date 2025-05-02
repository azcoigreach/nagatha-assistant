# nagatha-assistant

nagatha-assistant is a personal AI agent/assistant built in Python. It leverages the OpenAI API to interface with the user, perform tasks, and integrate with external tools and services. The design follows a modular, agent-based architecture with support for asynchronous operations, detailed logging, and a command-line/terminal UI using Click and Textual.

Key features
------------
- Note-taking: capture and persist user notes
- Audio transcription: convert audio files into text
- Task management: add, list, and track tasks
- Reminders & notifications: schedule and trigger reminders
- Plugin System: dynamic discovery and management of feature plugins
- Integrations: (planned) connect with Obsidian and other services

Architecture
------------
The source code is organized under `src/nagatha_assistant/`:

```
src/nagatha_assistant/
├── cli.py                 # Click-based command-line entrypoint
├── core/                  # Base Agent classes and orchestrator
│   └── agent.py
├── modules/               # Functional modules (notes, tasks, etc.)
│   ├── notes.py
│   ├── transcription.py
│   ├── tasks.py
│   └── reminders.py
├── plugins/               # Plugin modules for custom features
│   └── (template plugin files)
├── integrations/          # Third-party service integrations (e.g. Obsidian)
│   └── obsidian.py
└── utils/                 # Utilities (logging, helpers)
    └── logger.py
tests/                     # Pytest test suite following TDD approach
docs/                      # Project documentation and design notes
```

Getting Started
---------------

Prerequisites:
- Python 3.11+
- Git
- Docker (optional)

1. Clone the repository:

   ```
   git clone https://github.com/AZcoigreach/nagatha-assistant.git
   cd nagatha-assistant
   git checkout dev
   ```

2. Create a virtual environment and install dependencies:

   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables:

   ```
   cp .env.example .env
   # Edit .env to set OPENAI_API_KEY, LOG_LEVEL, etc.
   ```

4. Run tests (TDD workflow):

   ```
   pytest -q
   ```

5. Start the CLI:

   ```
   .venv/bin/python -m nagatha_assistant.cli run
   ```

Configuration
-------------
Environment variables are loaded via `python-dotenv`. Key vars:
- `OPENAI_API_KEY`: your OpenAI API token
- `LOG_LEVEL`: default log verbosity (DEBUG, INFO, WARNING, ERROR)
- `LOG_FILE`: path to the rotating log file

Logging & Telemetry
-------------------
- Uses Python's built-in `logging` with a `RotatingFileHandler`
- Five levels supported: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Logs written to `nagatha.log` by default, rotated at 10 MB with 5 backups
- Logging level adjustable at runtime via CLI flags and UI
- API usage metrics and cost tracking will be logged

Development Workflow
--------------------
We follow TDD:
1. Define feature requirements
2. Write a failing test in `tests/`
3. Implement code in `src/nagatha_assistant/`
4. Run `pytest` to ensure tests pass

Branches:
- `dev`: active development
- `main`: stable releases

License
-------
TBD