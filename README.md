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
- Cross-session memory: configurable inclusion of messages from past
  conversations so Nagatha can remember previous interactions.
- Usage & cost tracking: automatically records total tokens and estimated USD
  spend per model.

Key Features (DB & Chat)
- AI Chat: interactive chat sessions with LLM (OpenAI), with persistent session history
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
   .venv/bin/nagatha_assistant.cli run    # launches Textual UI
   # or use console script:
   nagatha run
   ```

Chat via CLI:

   ```
   nagatha chat new                     # create new session
   nagatha chat list                    # list sessions
   nagatha chat history <session_id>    # show session history
   # Send a message and include the last 15 messages from *other* sessions
   nagatha chat send <session_id> "Hello" --context-limit 15

Show cumulative usage/cost:

   ```
   nagatha usage
   ```

List available models:

   ```
   nagatha models
   ```
   ```

Textual UI shortcuts:

   * `/help`         – list all commands  
   * `/sessions`     – list existing sessions  
   * `/new`          – create and switch to a new session  
   * `/switch <id>`  – change to a past session  
   * `/history`      – re-print current session history  
   * `/context [N]`  – get or set number **N** of cross-session messages to
     prepend as additional context (same as `--context-limit` flag).
   * `/models`       – list available OpenAI models (same as `nagatha models`)  
   * `/usage`        – show aggregated token usage & cost (same as `nagatha usage`)

Configuration
-------------
Environment variables are loaded via `python-dotenv`. Key vars:
- `OPENAI_API_KEY`: your OpenAI API token
- `LOG_LEVEL`: default log verbosity (DEBUG, INFO, WARNING, ERROR)
- `LOG_FILE`: path to the rotating log file
- `CONTEXT_MEMORY_MESSAGES`: default number of messages from *other* sessions
  to include as context (overridable per-run via CLI/UI). 0 = disabled.
- `OPENAI_MODEL`: default chat model (e.g. `gpt-3.5-turbo`)
- `NAGATHA_USAGE_FILE`: override path for cumulative usage JSON (optional)


Logging & Telemetry
-------------------
- Uses Python's built-in `logging` with a `RotatingFileHandler`
- Five levels supported: DEBUG, INFO, WARNING, ERROR, CRITICAL (default
  project-wide level is **WARNING**)
- Logs written to `nagatha.log` by default, rotated at 10 MB with 5 backups
- Logging level adjustable at runtime via CLI `--log-level` flag, UI, or
  `LOG_LEVEL` env-var.
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