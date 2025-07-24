#!/usr/bin/env python3
"""
Test plugin system initialization.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.agent import startup, get_available_tools, call_tool_or_command

async def test_plugin_init():
    """Test plugin system initialization."""
    print("🔌 Testing Plugin System Initialization")
    print("=" * 50)
    
    # Start the full system
    print("Starting Nagatha system...")
    try:
        startup_result = await startup()
        print(f"✅ Startup completed: {startup_result}")
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Get available tools
    print("\n📋 Getting available tools...")
    try:
        tools = await get_available_tools()
        print(f"Total tools: {len(tools)}")
        
        memory_tools = [tool for tool in tools if 'memory' in tool['name'].lower()]
        print(f"Memory tools: {len(memory_tools)}")
        for tool in memory_tools:
            print(f"  • {tool['name']}: {tool['description']}")
            
    except Exception as e:
        print(f"❌ Error getting tools: {e}")
    
    # Test calling memory command
    print("\n🧪 Testing memory command...")
    try:
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "name",
            "default": "Unknown"
        })
        print(f"✅ Memory command result: {result}")
    except Exception as e:
        print(f"❌ Memory command failed: {e}")
    
    print("\n✅ Plugin initialization test completed!")

if __name__ == "__main__":
    asyncio.run(test_plugin_init()) 