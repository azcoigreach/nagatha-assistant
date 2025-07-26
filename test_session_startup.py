#!/usr/bin/env python3
"""
Test script to simulate session startup and verify memory loading.
"""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.core.agent import start_session
from nagatha_assistant.core.memory import get_contextual_recall

async def test_session_startup():
    """Test session startup with memory loading."""
    print("🚀 Testing Session Startup with Memory Loading")
    print("=" * 55)
    
    try:
        # Start a new session (this should trigger the memory loading)
        print("Starting new session...")
        session_id = await start_session()
        print(f"✅ Session {session_id} started successfully")
        
        # Test the contextual recall directly
        print("\n🔍 Testing contextual recall...")
        recall = get_contextual_recall()
        
        # Get user name
        user_name = await recall.get_user_name()
        print(f"User name: {user_name}")
        
        # Get startup memories
        startup_memories = await recall.get_session_startup_memories(session_id)
        print(f"Startup memories found: {len(startup_memories)} sections")
        
        for section, memories in startup_memories.items():
            if memories:
                print(f"  📂 {section}: {len(memories)} items")
                for memory in memories[:2]:  # Show first 2 items
                    print(f"    - {memory['key']}")
        
        print("\n🎉 Session startup test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during session startup test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_session_startup()) 