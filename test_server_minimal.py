#!/usr/bin/env python3
"""
Minimal test to debug server startup issues.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

async def test_minimal_server():
    """Test minimal server startup."""
    print("Testing minimal server startup...")
    
    try:
        # Test 1: Create server config
        print("1. Creating server config...")
        from nagatha_assistant.server.core_server import ServerConfig
        config = ServerConfig(
            enable_websocket=False, 
            enable_rest=False, 
            enable_events=False,
            port=8085
        )
        print("   ✓ Config created")
        
        # Test 2: Create server instance
        print("2. Creating server instance...")
        from nagatha_assistant.server.core_server import NagathaUnifiedServer
        server = NagathaUnifiedServer(config)
        print("   ✓ Server instance created")
        
        # Test 3: Initialize core components only
        print("3. Initializing core components...")
        await server._initialize_core_components()
        print("   ✓ Core components initialized")
        
        # Test 4: Start unified components
        print("4. Starting unified components...")
        await server._start_unified_components()
        print("   ✓ Unified components started")
        
        # Test 5: Set server as running
        print("5. Setting server as running...")
        server._running = True
        server._start_time = asyncio.get_event_loop().time()
        print("   ✓ Server marked as running")
        
        # Test 6: Check status
        print("6. Checking server status...")
        status = await server.get_server_status()
        print(f"   ✓ Server status: {status['server']['running']}")
        
        print("🎉 Minimal server test passed!")
        
        # Clean up
        server._running = False
        await server._stop_unified_components()
        print("Server components stopped")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_minimal_server()) 