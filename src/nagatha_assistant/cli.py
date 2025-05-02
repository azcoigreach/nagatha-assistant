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
    send_message
)


@click.group()
@click.option("--log-level", default=None, help="Set log level (DEBUG, INFO, etc.)")
def cli(log_level):
    """
    Nagatha Assistant CLI.
    """
    level = log_level or os.getenv("LOG_LEVEL", "INFO")
    logger = setup_logger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.info(f"Logger initialized at {level.upper()}")


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

@chat.command('send')
@click.argument('session_id', type=int)
@click.argument('message', nargs=-1)
def chat_send(session_id, message):
    """
    Send a message to the model and store the reply.
    """
    text = ' '.join(message)
    reply = asyncio.run(send_message(session_id, text))
    click.echo(reply)


if __name__ == "__main__":
    cli()