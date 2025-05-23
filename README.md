# nagatha-assistant

nagatha-assistant is a personal AI agent/assistant built in Python. It leverages the OpenAI API to interface with the user, perform tasks, and integrate with external tools and services. The design follows a modular, agent-based architecture with support for asynchronous operations, detailed logging, and a command-line/terminal UI using Click and Textual.

Key features
------------
- Note-taking: capture and persist user notes in Markdown with titles, tags, and full-text search
- Audio transcription: convert audio files into text
- Task management: add, list, update, complete, and close tasks with priorities, tags, and due dates
- Reminders: create and schedule reminders tied to tasks, with support for recurrence and background notifications
- Reminders & notifications: schedule and trigger reminders
- Plugin System: dynamic discovery and management of feature plugins
- Integrations: (planned) connect with Obsidian and other services
- Cross-session memory: configurable inclusion of messages from past
  conversations so Nagatha can remember previous interactions.
- Usage & cost tracking: automatically records total tokens and estimated USD
  spend per model.
- Plugin architecture: extend Nagatha with self-contained modules that expose
  callable *functions*; the chat agent can invoke these at runtime via the
  OpenAI function-calling interface.
- Web search plugin: allows the agent to query the internet via SearXNG and
-  summarise findings, with transparent citation of sources.
- Time retrieval plugin: fetch the current date and time from NIST time server (time.nist.gov) and return it in the specified timezone (default MST).

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
│   ├── echo.py            # EchoPlugin (v0.1.0)
│   ├── web_search.py      # WebSearchPlugin (v0.1.0)
│   └── nist_time.py       # NistTimePlugin (v0.1.0)
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

Creating a plugin
-----------------
Plugins live in `src/nagatha_assistant/plugins/`.
They are discovered automatically at runtime and exposed to the LLM through
OpenAI’s *function-calling* interface.

See `docs/plugins.md` for the complete guide and a minimal template.
   ```

5. Start the core server and UI:

   # Start the Nagatha core server (API + plugin manager):
   ```bash
   nagatha server [--host HOST] [--port PORT]
   ```

   # Launch the Textual UI (chat client):
   ```bash
   nagatha run [--host HOST] [--port PORT]
   ```

Chat via CLI:

   ```
   # Chat commands
   nagatha chat new                     # create new session
   nagatha chat list                    # list sessions
   nagatha chat history <session_id>    # show session history
   # Send a message and include the last 15 messages from *other* sessions
   nagatha chat send <session_id> "Hello" --context-limit 15

   # Notes commands
   nagatha note add "My Note" "This is the content" --tag tag1 --tag tag2
   nagatha note list
   nagatha note get <note_id>

   # Task commands
   nagatha task add "My Task" "Do something" --due-at 2025-05-10T12:00:00 --priority high --tag work
   nagatha task list --status pending
   nagatha task complete <task_id>
   nagatha task close <task_id>

   # Reminder commands
   nagatha reminder add <task_id> 2025-05-11T09:00:00 --recurrence daily
   nagatha reminder list --task-id <task_id>
   nagatha reminder deliver <reminder_id>

Show cumulative usage/cost:

   ```
   nagatha usage
   ```

List available models:

   ```
   nagatha models
   ```
   ```

Database management:

   ```
   nagatha db upgrade           # run Alembic migrations to latest revision
   nagatha db backup [DEST]     # backup SQLite database (defaults to timestamped copy)
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
- `DATABASE_URL`: SQLAlchemy URL (SQLite default). Alembic migrations use the
  same value during `alembic upgrade head`.

Database migrations (Alembic)
-----------------------------
We’ve migrated from programmatic `Base.metadata.create_all()` to proper schema
versioning with Alembic.

1. The initial schema is captured in `migrations/versions/0001_initial.py`.
2. `src/nagatha_assistant/db.ensure_schema()` runs **once per process** and
   calls `alembic upgrade head` programmatically (falling back to
   `create_all()` if Alembic isn’t installed).
3. All code paths that need a database now `await ensure_schema()` (e.g.
   `modules/chat.init_db`).

Developer workflow:

```bash
# autogenerate after editing models
alembic revision --autogenerate -m "add foo column"

# apply latest
alembic upgrade head
```

Alembic picks up `DATABASE_URL` from the environment if set.


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