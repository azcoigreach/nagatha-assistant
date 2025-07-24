#!/usr/bin/env python3
"""
Test script to check memory tools availability and registration.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.agent import get_available_tools, call_tool_or_command
from nagatha_assistant.core.plugin_manager import get_plugin_manager
from nagatha_assistant.core.memory import ensure_memory_manager_started

async def test_memory_tools():
    """Test memory tools availability and functionality."""
    print("🧠 Testing Memory Tools Availability")
    print("=" * 50)
    
    # Start memory manager
    print("Starting memory manager...")
    memory_manager = await ensure_memory_manager_started()
    print("✅ Memory manager started")
    
    # Get plugin manager and check available commands
    print("\n📋 Checking plugin commands...")
    plugin_manager = get_plugin_manager()
    available_commands = plugin_manager.get_available_commands()
    
    print(f"Total plugin commands: {len(available_commands)}")
    memory_commands = {name: info for name, info in available_commands.items() if 'memory' in name.lower()}
    
    print(f"Memory-related commands: {len(memory_commands)}")
    for name, info in memory_commands.items():
        print(f"  • {name}: {info['description']}")
        print(f"    Plugin: {info['plugin']}")
        print(f"    Parameters: {info['parameters']}")
    
    # Get all available tools (MCP + plugin commands)
    print("\n🔧 Checking all available tools...")
    all_tools = await get_available_tools()
    
    print(f"Total available tools: {len(all_tools)}")
    memory_tools = [tool for tool in all_tools if 'memory' in tool['name'].lower()]
    
    print(f"Memory-related tools: {len(memory_tools)}")
    for tool in memory_tools:
        print(f"  • {tool['name']}: {tool['description']}")
        print(f"    Server: {tool.get('server', 'unknown')}")
        if tool.get('schema'):
            print(f"    Schema: {tool['schema']}")
    
    # Test calling a memory command directly
    print("\n🧪 Testing memory command execution...")
    try:
        # Test setting a user preference
        result = await call_tool_or_command("memory_set_user_preference", {
            "key": "test_name",
            "value": "Test User"
        })
        print(f"✅ Set user preference result: {result}")
        
        # Test getting the user preference
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "test_name",
            "default": "Unknown"
        })
        print(f"✅ Get user preference result: {result}")
        
    except Exception as e:
        print(f"❌ Error testing memory commands: {e}")
        import traceback
        traceback.print_exc()
    
    # Test the specific command that failed in the logs
    print("\n🔍 Testing the specific failing command...")
    try:
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "name",
            "default": "User"
        })
        print(f"✅ memory_get_user_preference result: {result}")
    except Exception as e:
        print(f"❌ memory_get_user_preference failed: {e}")
    
    print("\n✅ Memory tools test completed!")

if __name__ == "__main__":
    asyncio.run(test_memory_tools()) 