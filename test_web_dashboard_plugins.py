#!/usr/bin/env python3
"""
Test plugin system initialization in web dashboard context.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Add web_dashboard to path
web_dashboard_path = os.path.join(os.path.dirname(__file__), 'web_dashboard')
sys.path.insert(0, web_dashboard_path)

from dashboard.nagatha_real_adapter import NagathaRealAdapter
from nagatha_assistant.core.agent import call_tool_or_command

async def test_web_dashboard_plugins():
    """Test plugin system in web dashboard context."""
    print("🌐 Testing Web Dashboard Plugin System")
    print("=" * 50)
    
    # Create the adapter that the web dashboard uses
    print("Creating NagathaRealAdapter...")
    adapter = NagathaRealAdapter()
    
    # Initialize the adapter (this should now start plugins)
    print("Initializing adapter...")
    await adapter._ensure_initialized()
    print("✅ Adapter initialized")
    
    # Get available tools through the adapter
    print("\n📋 Getting available tools through adapter...")
    tools_info = await adapter.get_available_tools()
    print(f"Total tools: {tools_info['total']}")
    print(f"Note: {tools_info['note']}")
    
    # Find memory tools
    tools = tools_info.get('tools', [])
    memory_tools = [tool for tool in tools if 'memory' in tool['name'].lower()]
    
    print(f"\nMemory tools found: {len(memory_tools)}")
    for tool in memory_tools:
        print(f"  • {tool['name']}: {tool['description']}")
    
    # Test calling memory command directly
    print("\n🧪 Testing memory command execution...")
    try:
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "name",
            "default": "Unknown"
        })
        print(f"✅ Memory command result: {result}")
    except Exception as e:
        print(f"❌ Memory command failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Web dashboard plugin test completed!")

if __name__ == "__main__":
    asyncio.run(test_web_dashboard_plugins()) 