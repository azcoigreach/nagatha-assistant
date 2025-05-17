import asyncio
import os
import traceback
import sys
from pprint import pprint
from dotenv import load_dotenv, find_dotenv
import logging

# Configure logging to show debug messages (force overrides basicConfig from plugin)
logging.basicConfig(level=logging.DEBUG, force=True)
logger = logging.getLogger(__name__)

# Enable HTTP connection and library debug logging
try:
    import http.client as http_client
    http_client.HTTPConnection.debuglevel = 1
except Exception:
    pass
for log_name in ("urllib3", "requests", "mastodon"):
    logging.getLogger(log_name).setLevel(logging.DEBUG)
    logging.getLogger(log_name).propagate = True

# Adjust import path as needed if running outside the package context
from src.nagatha_assistant.plugins.mastodon_plugin import MastodonPlugin

async def test_mastodon_plugin():
    # Debug: show runtime context
    print("Working directory:", os.getcwd())
    print("Python version:", sys.version)
    print("System path:")
    pprint(sys.path)
    print("Loading environment variables...")
    load_dotenv()
    # Show which .env file was loaded
    try:
        dotenv_path = find_dotenv()
        print(f".env file path: {dotenv_path or 'Not found'}")
    except Exception:
        pass
    # Debug: show relevant environment variables (secrets masked)
    def _mask(val): return None if not val else (val[:4] + '...' + val[-4:] if len(val) > 8 else '***')
    env_debug = {
        'MASTODON_CLIENT_ID': _mask(os.getenv('MASTODON_CLIENT_ID')),
        'MASTODON_CLIENT_SECRET': _mask(os.getenv('MASTODON_CLIENT_SECRET')),
        'MASTODON_ACCESS_TOKEN': _mask(os.getenv('MASTODON_ACCESS_TOKEN')),
        'MASTODON_API_BASE_URL': os.getenv('MASTODON_API_BASE_URL')
    }
    print("Environment variables:")
    pprint(env_debug)

    # Create plugin instance
    print("Creating MastodonPlugin instance...")
    plugin = MastodonPlugin()
    # Additional plugin debug info
    try:
        print("Plugin logger:", plugin.log)
        print("Plugin logger level:", logging.getLevelName(plugin.log.level))
    except Exception:
        pass

    # Debug: available function specs before setup
    try:
        specs = plugin.function_specs()
        print("Function specs available (names):")
        pprint([spec.get('name') for spec in specs])
        print("Function specs available (full):")
        pprint(specs)
    except Exception:
        pass

    # Setup plugin (initialize Mastodon client)
    print("Setting up MastodonPlugin...")
    try:
        setup_result = await plugin.setup({})
    except Exception as e:
        print("Exception during setup:")
        traceback.print_exc()
        return
    print("Setup result:")
    pprint(setup_result)
    # Debug: function specs after setup
    try:
        print("Function specs after setup (full):")
        pprint(plugin.function_specs())
    except Exception:
        pass

    if isinstance(setup_result, dict) and "error" in setup_result:
        print("Error initializing Mastodon client. Check environment variables and credentials.")
        return
    # Inspect plugin client after setup
    print("Plugin instance:", plugin)
    print("Plugin client object:", plugin.client)
    try:
        client_attrs = vars(plugin.client)
        print("Plugin client attributes:")
        pprint(client_attrs)
    except Exception:
        pass

    # Debug: client public attributes (dir)
    try:
        client_dir = [attr for attr in dir(plugin.client) if not attr.startswith("_")]
        print("Plugin client dir (public attributes):")
        pprint(client_dir)
    except Exception:
        pass

    # Debug: client session details (if available)
    try:
        session = getattr(plugin.client, "_session", None) or getattr(plugin.client, "session", None)
        if session:
            print("Client session details:")
            session_info = {
                "headers": getattr(session, "headers", None),
                "verify": getattr(session, "verify", None),
                "trust_env": getattr(session, "trust_env", None),
                "proxies": getattr(session, "proxies", None),
            }
            pprint(session_info)
    except Exception:
        pass

    # Call read_local_timeline with limit 10
    print("Calling read_local_timeline with limit=10...")
    try:
        result = await plugin.call("read_local_timeline", {"limit": 10})
    except Exception as e:
        print("Exception during call to read_local_timeline:")
        traceback.print_exc()
        return
    print("Raw result from read_local_timeline:")
    pprint(result)
    # Debug: representation of result
    try:
        print("Result repr:")
        print(repr(result))
    except Exception:
        pass
    # Debug: examine result structure
    print("Type of raw result:", type(result))
    if isinstance(result, (list, tuple)):
        print(f"Number of items in result: {len(result)}")
        if result:
            first = result[0]
            print("Type of first item:", type(first))
            try:
                print("First item keys:")
                pprint(first.keys())
            except Exception:
                try:
                    print("First item attributes:")
                    pprint(vars(first))
                except Exception:
                    print(first)

    if isinstance(result, dict) and "error" in result:
        print("Error fetching local timeline:", result.get("error"))
    else:
        print(f"Local timeline posts (count={len(result)}):")
        for idx, post in enumerate(result, start=1):
            print(f"Post #{idx}:")
            # Detailed view of post object/dict
            try:
                pprint(post)
            except Exception:
                print(post)

if __name__ == "__main__":
    print("Starting test_mastodon_plugin...")
    asyncio.run(test_mastodon_plugin())