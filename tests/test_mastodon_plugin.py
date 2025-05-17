import sys
import os
import asyncio

# Adjust sys.path to include the src directory so that nagatha_assistant package can be found
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nagatha_assistant.plugins.mastodon_plugin import MastodonPlugin

async def main():
    plugin = MastodonPlugin()

    # Test authentication using auto-loaded .env credentials
    auth_result = await plugin.call("authenticate", {})
    print("Authentication Result:", auth_result)

    # Test reading the local timeline (fetch a limited number of posts)
    try:
        timeline_result = await plugin.call("read_local_timeline", {"limit": 1})
        print("Local Timeline:", timeline_result)
    except Exception as e:
        print("Error reading local timeline:", str(e))

if __name__ == "__main__":
    asyncio.run(main())