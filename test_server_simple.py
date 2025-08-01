#!/usr/bin/env python3
"""
Simple test to debug server startup issues.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

async def test_server_startup():
    """Test server startup step by step."""
    print("Testing server startup...")
    
    try:
        # Test 1: Import ServerConfig
        print("1. Testing ServerConfig import...")
        from nagatha_assistant.server.core_server import ServerConfig
        config = ServerConfig(enable_websocket=False, enable_rest=False, enable_events=False)
        print("   ✓ ServerConfig works")
        
        # Test 2: Create server instance
        print("2. Testing server instance creation...")
        from nagatha_assistant.server.core_server import NagathaUnifiedServer
        server = NagathaUnifiedServer(config)
        print("   ✓ Server instance created")
        
        # Test 3: Initialize core components
        print("3. Testing core component initialization...")
        await server._initialize_core_components()
        print("   ✓ Core components initialized")
        
        # Test 4: Start unified components
        print("4. Testing unified component startup...")
        await server._start_unified_components()
        print("   ✓ Unified components started")
        
        # Test 5: Get server status
        print("5. Testing server status...")
        status = await server.get_server_status()
        print(f"   ✓ Server status: {status['server']['running']}")
        
        print("🎉 All tests passed!")
        
        # Clean up
        await server._stop_unified_components()
        print("Server components stopped")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_server_startup()) 