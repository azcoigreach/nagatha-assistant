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


if __name__ == "__main__":
    cli()