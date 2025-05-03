import os
import sys
# Ensure src directory is on PYTHONPATH for package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
import click
from nagatha_assistant.utils.logger import setup_logger
import asyncio

# Import chat operations
from nagatha_assistant.modules.chat import (
    start_session,
    list_sessions,
    get_messages,
    send_message,
)

from nagatha_assistant.utils.usage_tracker import load_usage
import shutil
from pathlib import Path
from datetime import datetime
from nagatha_assistant.modules.tasks import list_tasks
from nagatha_assistant.modules.reminders import list_reminders


# -----------------------------
# Main entry point / CLI group
# -----------------------------
# A single ``--log-level`` option allows a user to raise or lower the verbosity
# at runtime.  If the flag is not supplied we fall back to the
# ``LOG_LEVEL`` environment variable or ultimately to ``WARNING`` which is the
# library-wide default defined in ``utils.logger``.


@click.group()
@click.option(
    "--log-level",
    default=None,
    help="Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
def cli(log_level):
    """
    Nagatha Assistant CLI.
    """
    # 1) Defer to the command-line flag if present
    # 2) Else fall back to ``LOG_LEVEL`` env var
    # 3) Else rely on project default (WARNING)

    resolved_level_name = (log_level or os.getenv("LOG_LEVEL") or "WARNING").upper()

    # Initialise the shared logger instance
    logger = setup_logger()

    # Apply the requested level to *both* this module's logger and the root
    # logger so that all log records respect the CLI flag.
    resolved_level = getattr(logging, resolved_level_name, logging.WARNING)
    logger.setLevel(resolved_level)
    logging.root.setLevel(resolved_level)

    logger.info(f"Logger initialised at {resolved_level_name}")


# ------------------------------------------------------------------
# Utility commands – model listing & usage stats
# ------------------------------------------------------------------


@cli.command()
def models():
    """List available chat/completion models from the OpenAI account."""
    import openai

    client = openai.OpenAI()
    try:
        model_list = client.models.list()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error fetching models: {exc}")
        return

    click.echo("Available models:")
    for m in model_list.data:
        click.echo(f"- {m.id}")


@cli.command()
def usage():
    """Show cumulative token counts & estimated spend per model."""

    data = load_usage()
    if not data:
        click.echo("No usage recorded yet.")
        return

    click.echo("Model usage:")
    fmt = "{:<30} {:>10} {:>10} {:>12}"
    click.echo(fmt.format("MODEL", "PROMPT", "COMP", "COST (USD)"))
    for model, stats in data.items():
        click.echo(
            fmt.format(
                model,
                int(stats["prompt_tokens"]),
                int(stats["completion_tokens"]),
                f"{stats['cost_usd']:.4f}",
            )
        )


@cli.command()
def run():
    """
    Run the Nagatha Textual UI.
    """
    click.echo("Starting Nagatha Assistant Textual UI...")
    from nagatha_assistant.ui import run_app
    run_app()


@cli.group()
def chat():
    """
    Chat commands: start sessions, send messages, view history.
    """
    pass

@chat.command('new')
def chat_new():
    """
    Start a new chat session.
    """
    sid = asyncio.run(start_session())
    click.echo(f"New session ID: {sid}")

@chat.command('list')
def chat_list():
    """
    List existing chat sessions.
    """
    sessions = asyncio.run(list_sessions())
    if not sessions:
        click.echo("No sessions found.")
        return
    for s in sessions:
        click.echo(f"Session {s.id} created at {s.created_at}")

@chat.command('history')
@click.argument('session_id', type=int)
def chat_history(session_id):
    """
    Show message history for a session.
    """
    msgs = asyncio.run(get_messages(session_id))
    if not msgs:
        click.echo("No messages in this session.")
        return
    for m in msgs:
        click.echo(f"[{m.timestamp}] {m.role}: {m.content}")

# -----------------------------
# Send message command
# -----------------------------


@chat.command('send')
@click.argument('session_id', type=int)
@click.argument('message', nargs=-1)
@click.option(
    '--context-limit',
    type=int,
    default=None,
    help='Number of recent messages from other sessions to include as context.',
)
def chat_send(session_id, message, context_limit):
    """
    Send a message to the model and store the reply.
    """
    text = ' '.join(message)
    reply = asyncio.run(send_message(session_id, text, memory_limit=context_limit))
    click.echo(reply)

# ------------------------------------------------------------------
# Task management commands
# ------------------------------------------------------------------
@cli.group()
def task():
    """Task commands: list and manage tasks."""
    pass

@task.command('list')
@click.option('--status', type=str, default=None, help='Filter by task status')
@click.option('--priority', type=str, default=None, help='Filter by task priority')
@click.option('--tag', 'tags', multiple=True, help='Filter by tag (repeatable)')
def task_list(status, priority, tags):  # noqa: A002
    """List tasks, optionally filtering by status, priority, and tags."""
    tasks = asyncio.run(list_tasks(status=status, priority=priority, tags=list(tags) if tags else None))
    if not tasks:
        click.echo("No tasks found.")
        return
    for t in tasks:
        click.echo(f"ID: {t['id']}")
        click.echo(f"  Title      : {t['title']}")
        click.echo(f"  Description: {t['description']}")
        click.echo(f"  Status     : {t['status']}")
        click.echo(f"  Priority   : {t['priority']}")
        click.echo(f"  Due At     : {t['due_at']}")
        click.echo(f"  Created At : {t['created_at']}")
        click.echo(f"  Updated At : {t['updated_at']}")
        click.echo(f"  Tags       : {', '.join(t['tags']) if t['tags'] else ''}")

# ------------------------------------------------------------------
# Reminder management commands
# ------------------------------------------------------------------
@cli.group()
def reminder():
    """Reminder commands: list and view reminders."""
    pass

@reminder.command('list')
@click.option('--task-id', type=int, default=None, help='Filter by task ID')
@click.option('--delivered', type=bool, default=None, help='Filter by delivered status')
def reminder_list(task_id, delivered):  # noqa: A002
    """List reminders, optionally filtering by task ID and delivery status."""
    rems = asyncio.run(list_reminders(task_id=task_id, delivered=delivered))
    if not rems:
        click.echo("No reminders found.")
        return
    for r in rems:
        click.echo(f"ID         : {r['id']}")
        click.echo(f"  Task ID      : {r['task_id']}")
        click.echo(f"  Remind At    : {r['remind_at']}")
        click.echo(f"  Delivered    : {r['delivered']}")
        click.echo(f"  Recurrence   : {r['recurrence']}")
        click.echo(f"  Last Sent At : {r['last_sent_at']}")

# ------------------------------------------------------------------
# Database management commands
# ------------------------------------------------------------------
@cli.group()
def db():
    """Database management: run migrations and backup the database."""
    pass

@db.command('upgrade')
def db_upgrade():
    """Run Alembic migrations to the latest revision."""
    # Dynamically read DATABASE_URL from environment
    import os
    raw_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///nagatha.db')
    # Normalize SQLite URL to async driver
    if raw_url.startswith('sqlite:///') and not raw_url.startswith('sqlite+aiosqlite:///'):
        db_url = raw_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    else:
        db_url = raw_url
    # Configure Alembic
    from alembic.config import Config  # type: ignore
    from alembic import command  # type: ignore
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / 'alembic.ini'))
    cfg.set_main_option('script_location', str(root / 'migrations'))
    cfg.set_main_option('sqlalchemy.url', db_url)
    # Attempt upgrade; if tables already exist, stamp to head
    try:
        command.upgrade(cfg, 'head')
        click.echo('Database successfully upgraded to the latest revision.')
    except Exception as exc:
        msg = str(exc)
        if 'already exists' in msg.lower():
            click.echo('Detected existing schema; stamping database to the latest Alembic revision.')
            try:
                command.stamp(cfg, 'head')
                click.echo('Database marked as up-to-date (stamped to head).')
            except Exception as stamp_exc:
                click.echo(f'Error stamping database: {stamp_exc}', err=True)
                sys.exit(1)
        else:
            click.echo(f'Error running migrations: {exc}', err=True)
            sys.exit(1)

@db.command('backup')
@click.argument('destination', required=False, type=click.Path())
def db_backup(destination):
    """Backup the SQLite database file to DEST (defaults to timestamped copy)."""
    # Dynamically read DATABASE_URL from environment
    import os
    raw_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///nagatha.db')
    # Normalize SQLite URL to async driver
    if raw_url.startswith('sqlite:///') and not raw_url.startswith('sqlite+aiosqlite:///'):
        db_url = raw_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    else:
        db_url = raw_url
    if not db_url.startswith('sqlite'):
        click.echo('Backup is only supported for SQLite databases.', err=True)
        return
    # Extract file path after '///'
    parts = db_url.split('///', 1)
    if len(parts) != 2 or not parts[1] or ':memory:' in parts[1]:
        click.echo('Cannot backup in-memory or invalid SQLite database.', err=True)
        return
    src = Path(parts[1])
    if not src.exists():
        click.echo(f'SQLite database file not found: {src}', err=True)
        return
    # Determine destination path
    dest = Path(destination) if destination else None
    if dest is None:
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        dest = src.with_name(f"{src.stem}_backup_{timestamp}{src.suffix}")
    try:
        shutil.copy2(src, dest)
        click.echo(f'Database backed up to {dest}')
    except Exception as exc:
        click.echo(f'Error backing up database: {exc}', err=True)


if __name__ == "__main__":
    cli()