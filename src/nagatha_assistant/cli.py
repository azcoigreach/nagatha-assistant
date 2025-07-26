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
        server_info = manager.get_server_info()
        connected_servers = len([name for name, info in server_info.items() if info['connected']])
        click.echo(f"Reloaded with {len(manager.get_available_tools())} tools from {connected_servers} servers")
    
    asyncio.run(_reload())


@cli.group()
def memory():
    """
    Memory system management commands.
    
    The memory system allows storing and retrieving information across sessions.
    Data is organized into sections with different persistence levels:
    
    - user_preferences: Personal settings and preferences (permanent)
    - session_state: Current session context (session-scoped)
    - command_history: History of commands and interactions (permanent)
    - facts: Long-term knowledge and facts (permanent)
    - temporary: Short-term data with automatic expiration (TTL-based)
    """
    pass


@memory.command("set")
@click.argument("section")
@click.argument("key")
@click.argument("value")
@click.option("--session", "-s", type=int, help="Session ID for session-scoped storage")
@click.option("--ttl", type=int, help="Time-to-live in seconds (for temporary section)")
@click.option("--source", help="Source attribution for facts")
def memory_set(section, key, value, session, ttl, source):
    """
    Set a memory value.
    
    SECTION: Memory section (user_preferences, session_state, command_history, facts, temporary)
    KEY: The key to store the value under
    VALUE: The value to store (JSON strings will be parsed)
    
    Examples:
        nagatha memory set user_preferences theme dark
        nagatha memory set session_state current_task "writing docs" --session 123
        nagatha memory set facts meeting_time "9 AM daily" --source "calendar"
        nagatha memory set temporary api_token "token123" --ttl 3600
    """
    async def _set():
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        
        try:
            # Try to parse value as JSON for complex data types
            try:
                import json
                parsed_value = json.loads(value)
                click.echo(f"Parsed JSON value: {type(parsed_value).__name__}")
            except (json.JSONDecodeError, ValueError):
                # If not JSON, treat as string
                parsed_value = value
            
            memory = await ensure_memory_manager_started()
            
            # Handle special section logic
            if section == "facts" and source:
                await memory.store_fact(key, parsed_value, source=source)
            elif ttl is not None:
                if section != "temporary":
                    click.echo("Warning: TTL is typically used with 'temporary' section", err=True)
                await memory.set(section, key, parsed_value, session_id=session, ttl_seconds=ttl)
            else:
                await memory.set(section, key, parsed_value, session_id=session)
            
            session_info = f" (session {session})" if session else ""
            ttl_info = f" (expires in {ttl}s)" if ttl else ""
            source_info = f" (source: {source})" if source else ""
            click.echo(f"✅ Set {section}/{key}{session_info}{ttl_info}{source_info}")
            
        except Exception as e:
            click.echo(f"❌ Error setting memory: {e}", err=True)
    
    asyncio.run(_set())


@memory.command("get")
@click.argument("section")
@click.argument("key")
@click.option("--session", "-s", type=int, help="Session ID for session-scoped retrieval")
@click.option("--default", help="Default value to return if key not found")
@click.option("--format", "output_format", type=click.Choice(["value", "json", "pretty"]), 
              default="value", help="Output format")
def memory_get(section, key, session, default, output_format):
    """
    Get a memory value.
    
    SECTION: Memory section name
    KEY: The key to retrieve
    
    Examples:
        nagatha memory get user_preferences theme
        nagatha memory get session_state current_task --session 123
        nagatha memory get facts meeting_time --format pretty
    """
    async def _get():
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        import json
        
        try:
            memory = await ensure_memory_manager_started()
            
            if section == "facts":
                # Special handling for facts to show full fact data
                value = await memory.get_fact(key)
                if value is None and default is not None:
                    click.echo(default)
                    return
            else:
                value = await memory.get(section, key, session_id=session, default=default)
            
            if value is None:
                click.echo(f"❌ Key '{key}' not found in section '{section}'", err=True)
                return
            
            # Format output
            if output_format == "json":
                click.echo(json.dumps(value, indent=2, default=str))
            elif output_format == "pretty":
                if isinstance(value, dict):
                    for k, v in value.items():
                        click.echo(f"{k}: {v}")
                else:
                    click.echo(str(value))
            else:
                # value format - just the value
                if isinstance(value, (dict, list)):
                    click.echo(json.dumps(value, default=str))
                else:
                    click.echo(str(value))
                    
        except Exception as e:
            click.echo(f"❌ Error getting memory: {e}", err=True)
    
    asyncio.run(_get())


@memory.command("list")
@click.argument("section")
@click.option("--session", "-s", type=int, help="Session ID for session-scoped listing")
@click.option("--pattern", help="Pattern to filter keys")
@click.option("--limit", type=int, default=50, help="Maximum number of keys to show")
def memory_list(section, session, pattern, limit):
    """
    List keys in a memory section.
    
    SECTION: Memory section name
    
    Examples:
        nagatha memory list user_preferences
        nagatha memory list session_state --session 123
        nagatha memory list facts --pattern "*meeting*"
    """
    async def _list():
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        
        try:
            memory = await ensure_memory_manager_started()
            keys = await memory.list_keys(section, session_id=session, pattern=pattern)
            
            if not keys:
                session_info = f" (session {session})" if session else ""
                click.echo(f"No keys found in section '{section}'{session_info}")
                return
            
            # Limit results
            if len(keys) > limit:
                click.echo(f"Showing first {limit} of {len(keys)} keys (use --limit to see more):")
                keys = keys[:limit]
            else:
                click.echo(f"Found {len(keys)} key(s) in section '{section}':")
            
            for key in keys:
                click.echo(f"  • {key}")
                
        except Exception as e:
            click.echo(f"❌ Error listing memory: {e}", err=True)
    
    asyncio.run(_list())


@memory.command("search")
@click.argument("section")
@click.argument("query")
@click.option("--session", "-s", type=int, help="Session ID for session-scoped search")
@click.option("--limit", type=int, default=20, help="Maximum number of results to show")
@click.option("--format", "output_format", type=click.Choice(["summary", "full", "keys"]), 
              default="summary", help="Output format")
def memory_search(section, query, session, limit, output_format):
    """
    Search for values in a memory section.
    
    SECTION: Memory section name
    QUERY: Search query (text to find in stored values)
    
    Examples:
        nagatha memory search facts python
        nagatha memory search user_preferences theme
        nagatha memory search command_history help --limit 10
    """
    async def _search():
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        import json
        
        try:
            memory = await ensure_memory_manager_started()
            
            if section == "facts":
                results = await memory.search_facts(query)
            else:
                results = await memory.search(section, query, session_id=session)
            
            if not results:
                click.echo(f"No results found for '{query}' in section '{section}'")
                return
            
            # Limit results
            if len(results) > limit:
                click.echo(f"Showing first {limit} of {len(results)} results:")
                results = results[:limit]
            else:
                click.echo(f"Found {len(results)} result(s) for '{query}':")
            
            for result in results:
                key = result.get("key", "unknown")
                value = result.get("value")
                
                if output_format == "keys":
                    click.echo(f"  • {key}")
                elif output_format == "full":
                    click.echo(f"  • {key}:")
                    if isinstance(value, dict):
                        for k, v in value.items():
                            click.echo(f"    {k}: {v}")
                    else:
                        click.echo(f"    {value}")
                    click.echo()
                else:  # summary
                    if isinstance(value, dict):
                        # Show first few fields for dicts
                        preview = ", ".join(f"{k}={v}" for k, v in list(value.items())[:2])
                        if len(value) > 2:
                            preview += "..."
                        click.echo(f"  • {key}: {{{preview}}}")
                    elif isinstance(value, str) and len(value) > 60:
                        click.echo(f"  • {key}: {value[:60]}...")
                    else:
                        click.echo(f"  • {key}: {value}")
                        
        except Exception as e:
            click.echo(f"❌ Error searching memory: {e}", err=True)
    
    asyncio.run(_search())


@memory.command("clear")
@click.argument("section")
@click.option("--session", "-s", type=int, help="Session ID for session-scoped clearing")
@click.option("--confirm", is_flag=True, help="Confirm clearing (required for some sections)")
@click.option("--key", help="Clear specific key instead of entire section")
def memory_clear(section, session, confirm, key):
    """
    Clear memory data.
    
    SECTION: Memory section name
    
    Examples:
        nagatha memory clear temporary
        nagatha memory clear session_state --session 123
        nagatha memory clear user_preferences --confirm
        nagatha memory clear facts --key "old_info"
    """
    async def _clear():
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        
        try:
            memory = await ensure_memory_manager_started()
            
            # Safety check for important sections
            protected_sections = ["user_preferences", "facts", "command_history"]
            if section in protected_sections and not key and not confirm:
                click.echo(f"❌ Clearing '{section}' requires --confirm flag for safety", err=True)
                click.echo(f"Use: nagatha memory clear {section} --confirm")
                return
            
            if key:
                # Clear specific key
                deleted = await memory.delete(section, key, session_id=session)
                if deleted:
                    session_info = f" (session {session})" if session else ""
                    click.echo(f"✅ Deleted {section}/{key}{session_info}")
                else:
                    click.echo(f"❌ Key '{key}' not found in section '{section}'", err=True)
            else:
                # Clear entire section
                cleared_count = await memory.clear_section(section)
                session_info = f" (session {session})" if session else ""
                click.echo(f"✅ Cleared {cleared_count} entries from section '{section}'{session_info}")
                
        except Exception as e:
            click.echo(f"❌ Error clearing memory: {e}", err=True)
    
    asyncio.run(_clear())


@memory.command("stats")
@click.argument("section", required=False)
@click.option("--detailed", is_flag=True, help="Show detailed statistics")
def memory_stats(section, detailed):
    """
    Show memory usage statistics.
    
    SECTION: Optional specific section to show stats for
    
    Examples:
        nagatha memory stats
        nagatha memory stats user_preferences
        nagatha memory stats --detailed
    """
    async def _stats():
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        
        try:
            memory = await ensure_memory_manager_started()
            stats = await memory.get_storage_stats()
            
            if section:
                # Show stats for specific section
                if section in stats:
                    count = stats[section]
                    click.echo(f"Section '{section}': {count} entries")
                    
                    if detailed:
                        # Show sample keys
                        keys = await memory.list_keys(section)
                        if keys:
                            click.echo("Sample keys:")
                            for key in keys[:10]:  # Show first 10
                                click.echo(f"  • {key}")
                            if len(keys) > 10:
                                click.echo(f"  ... and {len(keys) - 10} more")
                else:
                    click.echo(f"❌ Section '{section}' not found", err=True)
            else:
                # Show all stats
                click.echo("📊 Memory Usage Statistics:")
                click.echo()
                
                total_entries = 0
                for section_name, count in stats.items():
                    if isinstance(count, int):
                        total_entries += count
                        click.echo(f"  {section_name}: {count} entries")
                    else:
                        click.echo(f"  {section_name}: {count}")
                
                click.echo()
                click.echo(f"Total entries: {total_entries}")
                
                if detailed:
                    click.echo()
                    click.echo("Section details:")
                    for section_name in ["user_preferences", "session_state", "command_history", "facts", "temporary"]:
                        if section_name in stats and isinstance(stats[section_name], int):
                            count = stats[section_name]
                            if count > 0:
                                keys = await memory.list_keys(section_name)
                                click.echo(f"  {section_name} ({count} entries):")
                                for key in keys[:3]:  # Show first 3
                                    click.echo(f"    • {key}")
                                if len(keys) > 3:
                                    click.echo(f"    ... and {len(keys) - 3} more")
                                click.echo()
                
        except Exception as e:
            click.echo(f"❌ Error getting memory stats: {e}", err=True)
    
    asyncio.run(_stats())


@cli.group()
def discord():
    """
    Discord bot management commands.
    """
    pass


@discord.command("start")
def discord_start():
    """
    Start the Discord bot in the background.
    """
    from nagatha_assistant.utils.daemon import DaemonManager
    import os
    
    # Check if Discord token is configured
    if not os.getenv('DISCORD_BOT_TOKEN'):
        click.echo("❌ Discord bot token not configured", err=True)
        click.echo("Set DISCORD_BOT_TOKEN in your .env file or environment")
        return
    
    # Create daemon manager
    daemon = DaemonManager("discord_bot")
    
    # Check if already running
    if daemon.is_running():
        click.echo("❌ Discord bot is already running")
        click.echo("Use 'nagatha discord status' to check status or 'nagatha discord stop' to stop it")
        return
    
    async def _run_discord_daemon():
        """Run the Discord bot in daemon mode."""
        import asyncio
        import signal
        try:
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            from nagatha_assistant.utils.logger import setup_logger_with_env_control
            
            # Set up logging for daemon
            logger = setup_logger_with_env_control()
            logger.info("Starting Discord bot daemon")
            
            # Get the plugin manager with timeout
            try:
                logger.info("Getting plugin manager...")
                plugin_manager = get_plugin_manager()
                
                # Initialize if needed with timeout
                if not plugin_manager._initialized:
                    logger.info("Initializing plugin manager...")
                    await asyncio.wait_for(plugin_manager.initialize(), timeout=30.0)
                
                # Get the Discord bot plugin
                logger.info("Getting Discord bot plugin...")
                discord_plugin = plugin_manager.get_plugin("discord_bot")
                if not discord_plugin:
                    logger.error("Discord bot plugin not found or not enabled")
                    return False
                
                # Start the Discord bot with timeout
                logger.info("Starting Discord bot...")
                result = await asyncio.wait_for(
                    discord_plugin.start_discord_bot(), 
                    timeout=60.0
                )
                logger.info(f"Discord bot start result: {result}")
                
                # Keep the bot running indefinitely
                if "started successfully" in result.lower():
                    logger.info("Discord bot daemon running, waiting for termination signal")
                    
                    # Set up signal handlers for graceful shutdown
                    shutdown_event = asyncio.Event()
                    
                    def signal_handler(signum, frame):
                        logger.info(f"Discord daemon received signal {signum}, initiating shutdown")
                        shutdown_event.set()
                    
                    # Register signal handlers
                    signal.signal(signal.SIGTERM, signal_handler)
                    signal.signal(signal.SIGINT, signal_handler)
                    
                    try:
                        # Keep the event loop running until shutdown is requested
                        while discord_plugin.is_running and not shutdown_event.is_set():
                            try:
                                # Wait for shutdown event with timeout
                                await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)
                            except asyncio.TimeoutError:
                                # Timeout means no shutdown signal, continue running
                                continue
                            
                    except (KeyboardInterrupt, SystemExit):
                        logger.info("Discord bot daemon received termination signal")
                    finally:
                        # Clean up Discord bot
                        logger.info("Stopping Discord bot...")
                        await discord_plugin.stop_discord_bot()
                        logger.info("Discord bot daemon stopped")
                else:
                    logger.error(f"Failed to start Discord bot: {result}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error("Discord bot daemon initialization timed out")
                return False
                
        except Exception as e:
            logger.error(f"Discord bot daemon crashed: {e}")
            logger.exception("Full traceback:")
            return False
    
    # Start the daemon
    if daemon.start_daemon(_run_discord_daemon):
        click.echo("✅ Discord bot started successfully in the background")
        click.echo("Use 'nagatha discord status' to check status")
        click.echo("Use 'nagatha discord stop' to stop the bot")
    else:
        click.echo("❌ Failed to start Discord bot daemon", err=True)


@discord.command("stop")
def discord_stop():
    """
    Stop the Discord bot running in the background.
    """
    from nagatha_assistant.utils.daemon import DaemonManager
    
    # Create daemon manager
    daemon = DaemonManager("discord_bot")
    
    # Check if running
    if not daemon.is_running():
        click.echo("❌ Discord bot is not running")
        return
    
    # Stop the daemon
    if daemon.stop_daemon():
        click.echo("✅ Discord bot stopped successfully")
    else:
        click.echo("❌ Failed to stop Discord bot", err=True)


@discord.command("status")
def discord_status():
    """
    Get the Discord bot status.
    """
    from nagatha_assistant.utils.daemon import DaemonManager
    import datetime
    
    # Create daemon manager
    daemon = DaemonManager("discord_bot")
    
    # Get detailed status
    status = daemon.get_status()
    
    if not status["running"]:
        click.echo("❌ Discord bot: Stopped")
        return
    
    # Format detailed status
    click.echo("✅ Discord bot: Running")
    click.echo(f"   PID: {status['pid']}")
    click.echo(f"   Status: {status['status']}")
    
    if "memory" in status:
        memory_mb = status["memory"] / (1024 * 1024)
        click.echo(f"   Memory: {memory_mb:.1f} MB")
    
    if "cpu_percent" in status:
        click.echo(f"   CPU: {status['cpu_percent']:.1f}%")
    
    if "create_time" in status:
        start_time = datetime.datetime.fromtimestamp(status["create_time"])
        uptime = datetime.datetime.now() - start_time
        click.echo(f"   Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"   Uptime: {str(uptime).split('.')[0]}")  # Remove microseconds


@discord.command("setup")
def discord_setup():
    """
    Interactive setup for Discord bot configuration.
    """
    click.echo("Discord Bot Setup")
    click.echo("=" * 17)
    click.echo()
    
    # Check current configuration
    token = os.getenv('DISCORD_BOT_TOKEN')
    guild_id = os.getenv('DISCORD_GUILD_ID')
    prefix = os.getenv('DISCORD_COMMAND_PREFIX', '!')
    
    if token:
        masked_token = token[:8] + "..." if len(token) > 8 else "***"
        click.echo(f"Current bot token: {masked_token}")
    else:
        click.echo("Bot token: Not configured")
    
    click.echo(f"Guild ID: {guild_id or 'Not configured'}")
    click.echo(f"Command prefix: {prefix}")
    click.echo()
    
    # Setup instructions
    click.echo("To set up your Discord bot:")
    click.echo()
    click.echo("1. Go to https://discord.com/developers/applications")
    click.echo("2. Create a new application")
    click.echo("3. Go to the 'Bot' section")
    click.echo("4. Create a bot and copy the token")
    click.echo("5. Enable 'Message Content Intent' in the bot settings")
    click.echo("6. Add the bot to your server with appropriate permissions")
    click.echo()
    click.echo("Required environment variables in your .env file:")
    click.echo("DISCORD_BOT_TOKEN=your_bot_token_here")
    click.echo("DISCORD_GUILD_ID=your_guild_id_here  # Optional")
    click.echo("DISCORD_COMMAND_PREFIX=!  # Optional, defaults to !")
    click.echo()
    
    if not token:
        click.echo("❌ Please configure DISCORD_BOT_TOKEN in your .env file to use the Discord bot")


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


# Command to launch the enhanced Dashboard UI
@cli.command(name="dashboard")
def dashboard():
    """
    Launch the enhanced Dashboard UI for Nagatha.
    """
    async def _run_dashboard_with_lifecycle():
        from nagatha_assistant.core.agent import startup, shutdown
        from nagatha_assistant.ui.dashboard import run_dashboard
        from nagatha_assistant.utils.logger import setup_logger_with_env_control
        
        # Set up enhanced logging
        logger = setup_logger_with_env_control()
        
        try:
            # Show configuration info
            click.echo("Initializing Nagatha Assistant Dashboard...")
            
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
                logger.info(f"Dashboard startup successful: {init_summary['connected']} servers, {init_summary['total_tools']} tools")
            else:
                click.echo(f"⚠️  No MCP servers connected")
                if init_summary['total_configured'] > 0:
                    click.echo(f"   ({init_summary['total_configured']} configured but failed)")
                logger.warning("Dashboard startup completed but no MCP servers connected")
            
            if init_summary['failed_servers']:
                click.echo("❌ Failed connections:")
                for server_name, error in init_summary['failed_servers']:
                    click.echo(f"   • {server_name}: {error}")
            
            click.echo("\nStarting Nagatha Dashboard...")
            click.echo("Use Ctrl+Q to quit, F1 for help, Ctrl+1 to focus command input")
            
            # Run the dashboard
            await run_dashboard()
        except KeyboardInterrupt:
            click.echo("\nShutting down Nagatha Dashboard...")
        except Exception as e:
            click.echo(f"Error during dashboard startup: {e}", err=True)
            logger.exception("Error during dashboard startup")
        finally:
            # Clean up MCP connections
            try:
                await shutdown()
                click.echo("Dashboard shutdown complete.")
            except Exception as e:
                click.echo(f"Error during dashboard shutdown: {e}", err=True)
                logger.exception("Error during dashboard shutdown")
    
    asyncio.run(_run_dashboard_with_lifecycle())


@cli.group()
def scheduler():
    """
    Task scheduler management commands.
    """
    pass


@scheduler.command("schedule")
@click.argument("task_type", type=click.Choice(["mcp_tool", "plugin_command", "notification", "shell_command"]))
@click.argument("schedule_spec")
@click.option("--name", help="Optional name for the task")
@click.option("--description", help="Optional description of the task")
@click.option("--server-name", help="MCP server name (for mcp_tool)")
@click.option("--tool-name", help="MCP tool name (for mcp_tool)")
@click.option("--plugin-name", help="Plugin name (for plugin_command)")
@click.option("--command-name", help="Command name (for plugin_command)")
@click.option("--message", help="Message content (for notification)")
@click.option("--command", help="Shell command to execute (for shell_command)")
@click.option("--args", help="JSON-encoded arguments for the task")
def schedule_task(task_type, schedule_spec, name, description, server_name, tool_name, 
                 plugin_name, command_name, message, command, args):
    """
    Schedule a task for execution.
    
    TASK_TYPE: Type of task (mcp_tool, plugin_command, notification, shell_command)
    SCHEDULE_SPEC: When to run the task (cron expression, natural language, or ISO datetime)
    
    Examples:
    
    \b
    # Schedule an MCP tool call
    nagatha scheduler schedule mcp_tool "in 30 minutes" --server-name time --tool-name get_current_time
    
    \b
    # Schedule a notification
    nagatha scheduler schedule notification "0 9 * * *" --message "Daily reminder"
    
    \b
    # Schedule a plugin command
    nagatha scheduler schedule plugin_command "tomorrow at 2pm" --plugin-name echo --command-name echo --args '{"text": "Hello"}'
    """
    async def _schedule():
        from nagatha_assistant.plugins.scheduler import get_scheduler
        from nagatha_assistant.core.event_bus import ensure_event_bus_started
        
        # Start event bus
        await ensure_event_bus_started()
        
        scheduler = get_scheduler()
        
        # Parse arguments
        task_args = {}
        if args:
            try:
                task_args.update(json.loads(args))
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON in --args: {e}", err=True)
                return
        
        # Set up task-specific arguments
        if task_type == "mcp_tool":
            if not server_name or not tool_name:
                click.echo("mcp_tool requires --server-name and --tool-name", err=True)
                return
            task_args.update({
                "server_name": server_name,
                "tool_name": tool_name,
                "arguments": task_args.get("arguments", {})
            })
        elif task_type == "plugin_command":
            if not plugin_name or not command_name:
                click.echo("plugin_command requires --plugin-name and --command-name", err=True)
                return
            task_args.update({
                "plugin_name": plugin_name,
                "command_name": command_name,
                "arguments": task_args.get("arguments", {})
            })
        elif task_type == "notification":
            if not message:
                click.echo("notification requires --message", err=True)
                return
            task_args.update({
                "message": message,
                "notification_type": task_args.get("notification_type", "info")
            })
        elif task_type == "shell_command":
            if not command:
                click.echo("shell_command requires --command", err=True)
                return
            task_args.update({
                "command": command
            })
        
        try:
            task_id = await scheduler.schedule_task(
                task_type=task_type,
                task_args=task_args,
                schedule_spec=schedule_spec,
                task_name=name,
                description=description
            )
            click.echo(f"✅ Task scheduled successfully with ID: {task_id}")
            
            # Show task info
            task_info = scheduler.get_task_info(task_id)
            if task_info:
                click.echo(f"Task Type: {task_info['task_type']}")
                click.echo(f"Schedule Type: {task_info['schedule_type']}")
                if task_info.get('name'):
                    click.echo(f"Name: {task_info['name']}")
                if task_info.get('description'):
                    click.echo(f"Description: {task_info['description']}")
                
        except Exception as e:
            click.echo(f"❌ Failed to schedule task: {e}", err=True)
            logger.exception("Failed to schedule task")
    
    logger = setup_logger()
    asyncio.run(_schedule())


@scheduler.command("list")
@click.option("--status", type=click.Choice(["scheduled", "running", "completed", "failed", "cancelled"]), 
              help="Filter tasks by status")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table",
              help="Output format")
def list_tasks(status, output_format):
    """
    List scheduled tasks.
    """
    async def _list():
        from nagatha_assistant.plugins.scheduler import get_scheduler
        from nagatha_assistant.core.event_bus import ensure_event_bus_started
        
        # Start event bus
        await ensure_event_bus_started()
        
        scheduler = get_scheduler()
        tasks = scheduler.get_scheduled_tasks(status_filter=status)
        
        if not tasks:
            click.echo("No scheduled tasks found.")
            return
        
        if output_format == "json":
            click.echo(json.dumps(tasks, indent=2, default=str))
        else:
            # Table format
            click.echo(f"Found {len(tasks)} scheduled tasks:\n")
            
            # Header
            click.echo(f"{'ID':<12} {'Name':<20} {'Type':<15} {'Schedule':<15} {'Status':<10}")
            click.echo("-" * 80)
            
            # Tasks
            for task in tasks:
                task_id = task["task_id"][:10] + "..." if len(task["task_id"]) > 10 else task["task_id"]
                name = task.get("name", task["task_type"])[:18] + "..." if len(task.get("name", task["task_type"])) > 18 else task.get("name", task["task_type"])
                task_type = task["task_type"][:13] + "..." if len(task["task_type"]) > 13 else task["task_type"]
                schedule_type = task["schedule_type"][:13] + "..." if len(task["schedule_type"]) > 13 else task["schedule_type"]
                status = task["status"]
                
                click.echo(f"{task_id:<12} {name:<20} {task_type:<15} {schedule_type:<15} {status:<10}")
    
    logger = setup_logger()
    asyncio.run(_list())


@scheduler.command("info")
@click.argument("task_id")
def task_info(task_id):
    """
    Show detailed information about a scheduled task.
    """
    async def _info():
        from nagatha_assistant.plugins.scheduler import get_scheduler
        from nagatha_assistant.core.event_bus import ensure_event_bus_started
        
        # Start event bus
        await ensure_event_bus_started()
        
        scheduler = get_scheduler()
        task_info = scheduler.get_task_info(task_id)
        
        if not task_info:
            click.echo(f"Task {task_id} not found.", err=True)
            return
        
        click.echo(f"Task Information: {task_id}\n")
        click.echo(f"Name: {task_info.get('name', 'N/A')}")
        click.echo(f"Description: {task_info.get('description', 'N/A')}")
        click.echo(f"Type: {task_info['task_type']}")
        click.echo(f"Schedule Type: {task_info['schedule_type']}")
        click.echo(f"Status: {task_info['status']}")
        click.echo(f"Created: {task_info['created_at']}")
        
        if task_info.get('eta'):
            click.echo(f"ETA: {task_info['eta']}")
        if task_info.get('schedule'):
            click.echo(f"Schedule: {task_info['schedule']}")
        if task_info.get('cancelled_at'):
            click.echo(f"Cancelled: {task_info['cancelled_at']}")
        
        click.echo(f"\nTask Arguments:")
        click.echo(json.dumps(task_info['task_args'], indent=2))
    
    logger = setup_logger()
    asyncio.run(_info())


@scheduler.command("cancel")
@click.argument("task_id")
@click.option("--confirm", is_flag=True, help="Confirm cancellation")
def cancel_task(task_id, confirm):
    """
    Cancel a scheduled task.
    """
    async def _cancel():
        from nagatha_assistant.plugins.scheduler import get_scheduler
        from nagatha_assistant.core.event_bus import ensure_event_bus_started
        
        # Start event bus
        await ensure_event_bus_started()
        
        scheduler = get_scheduler()
        
        if not confirm:
            task_info = scheduler.get_task_info(task_id)
            if not task_info:
                click.echo(f"Task {task_id} not found.", err=True)
                return
            
            click.echo(f"Task: {task_info.get('name', task_info['task_type'])}")
            click.echo(f"Status: {task_info['status']}")
            
            if not click.confirm("Are you sure you want to cancel this task?"):
                click.echo("Cancellation aborted.")
                return
        
        try:
            cancelled = await scheduler.cancel_task(task_id)
            if cancelled:
                click.echo(f"✅ Task {task_id} cancelled successfully.")
            else:
                click.echo(f"❌ Task {task_id} not found or could not be cancelled.", err=True)
        except Exception as e:
            click.echo(f"❌ Failed to cancel task: {e}", err=True)
            logger.exception("Failed to cancel task")
    
    logger = setup_logger()
    asyncio.run(_cancel())


if __name__ == "__main__":
    cli()