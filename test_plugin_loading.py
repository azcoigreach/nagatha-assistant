#!/usr/bin/env python3
"""
Test script to check plugin system initialization and memory plugin loading.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.plugin_manager import get_plugin_manager
from nagatha_assistant.core.agent import startup

async def test_plugin_loading():
    """Test plugin system initialization and memory plugin loading."""
    print("🔌 Testing Plugin System Loading")
    print("=" * 50)
    
    # Test startup (which should initialize plugins)
    print("Starting Nagatha system...")
    try:
        startup_result = await startup()
        print(f"✅ Startup completed: {startup_result}")
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Get plugin manager
    print("\n📋 Checking plugin manager...")
    plugin_manager = get_plugin_manager()
    
    # Check plugin status
    plugin_status = plugin_manager.get_plugin_status()
    print(f"Plugin status: {plugin_status}")
    
    # Check available commands
    available_commands = plugin_manager.get_available_commands()
    print(f"Available commands: {len(available_commands)}")
    for name, info in available_commands.items():
        print(f"  • {name}: {info['description']} (plugin: {info['plugin']})")
    
    # Check if memory plugin is loaded
    memory_plugin = plugin_manager.get_plugin("memory")
    if memory_plugin:
        print(f"\n✅ Memory plugin found: {memory_plugin.name} v{memory_plugin.version}")
        print(f"State: {memory_plugin.state}")
        print(f"Registered commands: {list(memory_plugin.get_registered_commands())}")
    else:
        print("\n❌ Memory plugin not found!")
        
        # Check what plugins are available
        print("\nAvailable plugins:")
        for name, plugin in plugin_manager._plugins.items():
            print(f"  • {name}: {plugin.state}")
    
    print("\n✅ Plugin loading test completed!")

if __name__ == "__main__":
    asyncio.run(test_plugin_loading()) 