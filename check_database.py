#!/usr/bin/env python3
"""
Check what's stored in the database.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.memory import get_memory_manager

async def check_database():
    """Check what's stored in the database."""
    print("🔍 Checking Database Contents")
    print("=" * 40)
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    # Check user preferences
    print("\n👤 User Preferences:")
    try:
        name = await memory_manager.get_user_preference("name")
        print(f"  Name: {name}")
    except Exception as e:
        print(f"  Name: Error - {e}")
    
    try:
        occupation = await memory_manager.get_user_preference("occupation")
        print(f"  Occupation: {occupation}")
    except Exception as e:
        print(f"  Occupation: Error - {e}")
    
    # List all user preferences
    print("\n📋 All User Preferences:")
    try:
        results = await memory_manager.search("user_preferences", "")
        for result in results:
            print(f"  {result['key']}: {result['value']}")
    except Exception as e:
        print(f"  Error listing preferences: {e}")
    
    # Check facts
    print("\n🧠 Facts:")
    try:
        results = await memory_manager.search("facts", "")
        for result in results:
            print(f"  {result['key']}: {result['value']}")
    except Exception as e:
        print(f"  Error listing facts: {e}")
    
    # Test setting a new preference
    print("\n🧪 Testing setting a new preference...")
    try:
        await memory_manager.set_user_preference("test_name", "Eric")
        print("  ✅ Set test_name to 'Eric'")
        
        retrieved = await memory_manager.get_user_preference("test_name")
        print(f"  ✅ Retrieved: {retrieved}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    await memory_manager.stop()
    print("\n✅ Database check completed!")

if __name__ == "__main__":
    asyncio.run(check_database()) 