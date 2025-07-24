#!/usr/bin/env python3
"""
Test script to verify memory tools work in web dashboard context.
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

from nagatha_assistant.core.agent import get_available_tools, call_tool_or_command
from web_dashboard.dashboard.nagatha_real_adapter import NagathaRealAdapter

async def test_web_dashboard_memory():
    """Test memory tools in web dashboard context."""
    print("🌐 Testing Memory Tools in Web Dashboard Context")
    print("=" * 60)
    
    # Create the adapter that the web dashboard uses
    print("Creating NagathaRealAdapter...")
    adapter = NagathaRealAdapter()
    
    # Initialize the adapter
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
    
    # Test calling memory commands directly
    print("\n🧪 Testing memory command execution...")
    try:
        # Test setting a user preference
        result = await call_tool_or_command("memory_set_user_preference", {
            "key": "web_test_name",
            "value": "Web Test User"
        })
        print(f"✅ Set user preference result: {result}")
        
        # Test getting the user preference
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "web_test_name",
            "default": "Unknown"
        })
        print(f"✅ Get user preference result: {result}")
        
    except Exception as e:
        print(f"❌ Error testing memory commands: {e}")
        import traceback
        traceback.print_exc()
    
    # Test the specific command that was failing
    print("\n🔍 Testing the specific failing command...")
    try:
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "name",
            "default": "User"
        })
        print(f"✅ memory_get_user_preference result: {result}")
    except Exception as e:
        print(f"❌ memory_get_user_preference failed: {e}")
    
    print("\n✅ Web dashboard memory test completed!")

if __name__ == "__main__":
    asyncio.run(test_web_dashboard_memory()) 