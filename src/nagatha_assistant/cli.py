import os
import logging
import click
from nagatha_assistant.utils.logger import setup_logger


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
    click.echo("Starting Nagatha Assistant...")
    # TODO: Launch Textual UI


if __name__ == "__main__":
    cli()