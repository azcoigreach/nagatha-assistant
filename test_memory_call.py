#!/usr/bin/env python3
"""
Test memory command calling directly.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.agent import call_tool_or_command

async def test_memory_call():
    """Test calling memory commands directly."""
    print("🧪 Testing Memory Command Calling")
    print("=" * 40)
    
    # Test getting user preference
    print("\n🔍 Testing memory_get_user_preference...")
    try:
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "name",
            "default": "Unknown"
        })
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test setting a user preference
    print("\n📝 Testing memory_set_user_preference...")
    try:
        result = await call_tool_or_command("memory_set_user_preference", {
            "key": "name",
            "value": "Eric"
        })
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test getting it again
    print("\n🔍 Testing memory_get_user_preference again...")
    try:
        result = await call_tool_or_command("memory_get_user_preference", {
            "key": "name",
            "default": "Unknown"
        })
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n✅ Memory command test completed!")

if __name__ == "__main__":
    asyncio.run(test_memory_call()) 