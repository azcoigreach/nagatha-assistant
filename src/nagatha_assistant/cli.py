import os
import sys
import logging
import click
import datetime
import asyncio
import json

# Ensure src directory is on PYTHONPATH for package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nagatha_assistant.utils.logger import setup_logger


@click.group()
@click.option("--log-level", "-l", default=None, help="Set the logging level.")
def cli(log_level):
    """
    Nagatha Assistant CLI.
    """
    # Setup logging
    level_name = (log_level or os.getenv("LOG_LEVEL") or "WARNING").upper()
    logger = setup_logger()
    level = getattr(logging, level_name, logging.WARNING)
    logger.setLevel(level)
    logging.root.setLevel(level)
    logger.info(f"Logger initialised at {level_name}")


@cli.group()
def db():
    """
    Database maintenance commands.
    """
    pass


@db.command("upgrade")
def db_upgrade():
    """
    Run Alembic migrations to the latest revision.
    """
    import os
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///nagatha.db")
    if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite+aiosqlite:///"):
        db_url = raw_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    else:
        db_url = raw_url

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        command.upgrade(cfg, "head")
        click.echo("Database successfully upgraded to the latest revision.")
    except Exception as exc:
        msg = str(exc).lower()
        if "already exists" in msg:
            click.echo(
                "Detected existing schema; stamping database to the latest Alembic revision."
            )
            try:
                command.stamp(cfg, "head")
                click.echo("Database marked as up-to-date (stamped to head).")
            except Exception as stamp_exc:
                click.echo(f"Error stamping database: {stamp_exc}", err=True)
                sys.exit(1)
        else:
            click.echo(f"Error running migrations: {exc}", err=True)
            sys.exit(1)


@db.command("backup")
@click.argument("destination", required=False, type=click.Path())
def db_backup(destination):
    """
    Backup the SQLite database file to DEST (defaults to timestamped copy).
    """
    import os
    from pathlib import Path
    import shutil

    raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///nagatha.db")
    if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite+aiosqlite:///"):
        db_url = raw_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    else:
        db_url = raw_url

    if not db_url.startswith("sqlite"):
        click.echo("Backup is only supported for SQLite databases.", err=True)
        return

    parts = db_url.split("///", 1)
    if len(parts) != 2 or not parts[1] or ":memory:" in parts[1]:
        click.echo("Cannot backup in-memory or invalid SQLite database.", err=True)
        return

    src = Path(parts[1])
    if not src.exists():
        click.echo(f"SQLite database file not found: {src}", err=True)
        return

    dest = Path(destination) if destination else None
    if dest is None:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        dest = src.with_name(f"{src.stem}_backup_{timestamp}{src.suffix}")

    try:
        shutil.copy2(src, dest)
        click.echo(f"Database backed up to {dest}")
    except Exception as exc:
        click.echo(f"Error backing up database: {exc}", err=True)
    

@cli.group()
def mcp():
    """
    MCP (Model Context Protocol) management commands.
    """
    pass

@mcp.command("status")
def mcp_status():
    """
    Show the status of MCP servers and available tools.
    """
    async def _show_status():
        from nagatha_assistant.core.agent import get_mcp_status
        status = await get_mcp_status()
        
        click.echo("=== MCP Status ===")
        click.echo(f"Initialized: {status.get('initialized', False)}")
        
        if 'error' in status:
            click.echo(f"Error: {status['error']}", err=True)
            return
        
        click.echo("\n=== Servers ===")
        for server_name, server_info in status.get('servers', {}).items():
            connected = server_info.get('connected', False)
            config = server_info.get('config')
            tools = server_info.get('tools', [])
            
            status_icon = "✓" if connected else "✗"
            click.echo(f"{status_icon} {server_name} ({config.transport if config else 'unknown'})")
            
            if config:
                if config.command:
                    click.echo(f"    Command: {config.command} {' '.join(config.args or [])}")
                if config.url:
                    click.echo(f"    URL: {config.url}")
            
            if tools:
                click.echo(f"    Tools: {', '.join(tools)}")
            click.echo()
        
        click.echo("=== Available Tools ===")
        tools = status.get('tools', [])
        if tools:
            for tool in tools:
                click.echo(f"• {tool['name']} ({tool['server']}): {tool['description']}")
        else:
            click.echo("No tools available")
    
    asyncio.run(_show_status())

@mcp.command("reload")
def mcp_reload():
    """
    Reload MCP configuration and reconnect to servers.
    """
    async def _reload():
        from nagatha_assistant.core.mcp_manager import shutdown_mcp_manager, get_mcp_manager
        click.echo("Shutting down existing MCP connections...")
        await shutdown_mcp_manager()
        click.echo("Reloading MCP configuration...")
        manager = await get_mcp_manager()
        click.echo(f"Reloaded with {len(manager.get_available_tools())} tools from {len(manager.sessions)} servers")
    
    asyncio.run(_reload())

# Command to launch the Textual UI chat client
@cli.command(name="run")
def run():
    """
    Launch the Textual UI client for Nagatha.
    """
    async def _run_with_lifecycle():
        from nagatha_assistant.core.agent import startup, shutdown, format_mcp_status_for_chat
        from nagatha_assistant.ui import run_app
        from nagatha_assistant.utils.logger import setup_logger_with_env_control
        
        # Set up enhanced logging
        logger = setup_logger_with_env_control()
        
        try:
            # Show configuration info
            click.echo("Initializing Nagatha Assistant...")
            
            # Check for mcp.json
            if os.path.exists("mcp.json"):
                try:
                    with open("mcp.json", 'r') as f:
                        config = json.load(f)
                    server_count = len(config.get("mcpServers", {}))
                    click.echo(f"Found {server_count} MCP servers configured in mcp.json")
                except Exception as e:
                    click.echo(f"⚠️  Warning: Could not read mcp.json: {e}")
            else:
                click.echo("ℹ️  No mcp.json found - running without MCP servers")
            
            # Show timeout settings
            conn_timeout = os.getenv("NAGATHA_MCP_CONNECTION_TIMEOUT", "5")
            disc_timeout = os.getenv("NAGATHA_MCP_DISCOVERY_TIMEOUT", "3")
            click.echo(f"Connection timeout: {conn_timeout}s, Discovery timeout: {disc_timeout}s")
            
            # Initialize MCP and database
            click.echo("Connecting to MCP servers...")
            init_summary = await startup()
            
            # Show initialization results
            if init_summary['connected'] > 0:
                click.echo(f"✅ Connected to {init_summary['connected']}/{init_summary['total_configured']} MCP servers")
                click.echo(f"🔧 {init_summary['total_tools']} tools available")
                if init_summary['connected_servers']:
                    click.echo(f"Connected: {', '.join(init_summary['connected_servers'])}")
                logger.info(f"Startup successful: {init_summary['connected']} servers, {init_summary['total_tools']} tools")
            else:
                click.echo(f"⚠️  No MCP servers connected")
                if init_summary['total_configured'] > 0:
                    click.echo(f"   ({init_summary['total_configured']} configured but failed)")
                logger.warning("Startup completed but no MCP servers connected")
            
            if init_summary['failed_servers']:
                click.echo("❌ Failed connections:")
                for server_name, error in init_summary['failed_servers']:
                    click.echo(f"   • {server_name}: {error}")
            
            click.echo("\nStarting Nagatha UI...")
            
            # Run the UI
            await run_app()
        except KeyboardInterrupt:
            click.echo("\nShutting down Nagatha...")
        except Exception as e:
            click.echo(f"Error during startup: {e}", err=True)
            logger.exception("Error during startup")
        finally:
            # Clean up MCP connections
            try:
                await shutdown()
                click.echo("Shutdown complete.")
            except Exception as e:
                click.echo(f"Error during shutdown: {e}", err=True)
                logger.exception("Error during shutdown")
    
    asyncio.run(_run_with_lifecycle())

if __name__ == "__main__":
    cli()