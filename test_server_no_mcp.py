#!/usr/bin/env python3
"""
Test server startup without MCP initialization.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

async def test_server_no_mcp():
    """Test server startup without MCP."""
    print("Testing server startup without MCP...")
    
    try:
        # Test 1: Create server config
        print("1. Creating server config...")
        from nagatha_assistant.server.core_server import ServerConfig
        config = ServerConfig(
            enable_websocket=False, 
            enable_rest=False, 
            enable_events=False,
            port=8088
        )
        print("   ✓ Config created")
        
        # Test 2: Create server instance
        print("2. Creating server instance...")
        from nagatha_assistant.server.core_server import NagathaUnifiedServer
        server = NagathaUnifiedServer(config)
        print("   ✓ Server instance created")
        
        # Test 3: Initialize memory manager only
        print("3. Initializing memory manager...")
        from nagatha_assistant.core.memory import ensure_memory_manager_started
        server.memory_manager = await ensure_memory_manager_started()
        print("   ✓ Memory manager initialized")
        
        # Test 4: Initialize other components without MCP
        print("4. Initializing other components...")
        from nagatha_assistant.core.celery_app import get_celery_app
        from nagatha_assistant.core.event_bus import get_event_bus
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
        
        server.celery_app = get_celery_app()
        server.event_bus = get_event_bus()
        server.plugin_manager = get_plugin_manager()
        print("   ✓ Other components initialized")
        
        # Test 5: Start unified components
        print("5. Starting unified components...")
        await server._start_unified_components()
        print("   ✓ Unified components started")
        
        # Test 6: Set server as running
        print("6. Setting server as running...")
        server._running = True
        server._start_time = asyncio.get_event_loop().time()
        print("   ✓ Server marked as running")
        
        # Test 7: Check status
        print("7. Checking server status...")
        status = await server.get_server_status()
        print(f"   ✓ Server status: {status['server']['running']}")
        
        print("🎉 Server test without MCP passed!")
        
        # Clean up
        server._running = False
        await server._stop_unified_components()
        print("Server components stopped")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_server_no_mcp()) 