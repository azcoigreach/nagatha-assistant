#!/usr/bin/env python3
"""
Simple test to verify memory functionality without full session startup.
"""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.core.memory import get_contextual_recall
from nagatha_assistant.core.storage import DatabaseStorageBackend
from nagatha_assistant.core.memory import MemoryManager

async def test_simple_memory():
    """Test memory functionality without full session startup."""
    print("🧠 Testing Simple Memory Functionality")
    print("=" * 40)
    
    try:
        # Create memory manager with database backend
        manager = MemoryManager(storage_backend=DatabaseStorageBackend())
        await manager.start()
        print("✅ Memory manager started")
        
        # Get contextual recall
        recall = get_contextual_recall()
        print("✅ Contextual recall initialized")
        
        # Test getting user name
        user_name = await recall.get_user_name()
        print(f"👤 User name: {user_name}")
        
        # Test getting startup memories
        startup_memories = await recall.get_session_startup_memories(max_results=3)
        print(f"🚀 Startup memories: {len(startup_memories)} sections")
        
        for section, memories in startup_memories.items():
            if memories:
                print(f"  📂 {section}: {len(memories)} items")
        
        await manager.stop()
        print("✅ Memory manager stopped")
        print("🎉 Simple memory test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_memory()) 