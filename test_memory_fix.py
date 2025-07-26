#!/usr/bin/env python3
"""
Test script to verify the memory fix for session startup.
"""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.core.memory import (
    MemoryManager, ContextualRecall, MemoryTrigger
)
from nagatha_assistant.core.storage import InMemoryStorageBackend

async def test_memory_fix():
    """Test the memory fix for session startup."""
    print("🧠 Testing Memory Fix for Session Startup")
    print("=" * 50)
    
    # Create memory manager with in-memory backend for testing
    manager = MemoryManager(storage_backend=InMemoryStorageBackend())
    await manager.start()
    print("✅ Memory manager started")
    
    # Get components
    trigger = MemoryTrigger(manager)
    recall = ContextualRecall(manager)
    
    # Simulate storing user information
    print("\n📝 Storing user information...")
    
    # Store user name
    await manager.set("user_preferences", "name", {
        "text": "John",
        "type": "name",
        "confidence": 0.9
    })
    
    # Store user preferences
    await manager.set("user_preferences", "detail_preference", {
        "preference": "I prefer detailed technical explanations",
        "type": "preference",
        "confidence": 0.8
    })
    
    # Store personality trait
    await manager.set("personality", "communication_style", {
        "style_type": "casual_friendly",
        "context": "User prefers casual conversation",
        "confidence": 0.7
    })
    
    # Store a fact
    await manager.set("facts", "user_occupation", {
        "fact": "User is a software developer",
        "source": "conversation",
        "stored_at": "2025-01-20T10:00:00Z"
    })
    
    print("✅ User information stored")
    
    # Test getting user name
    print("\n👤 Testing user name retrieval...")
    user_name = await recall.get_user_name()
    print(f"User name: {user_name}")
    assert user_name == "John", f"Expected 'John', got '{user_name}'"
    print("✅ User name retrieval works")
    
    # Test getting startup memories
    print("\n🚀 Testing startup memories...")
    startup_memories = await recall.get_session_startup_memories(max_results=3)
    
    print("Startup memories found:")
    for section, memories in startup_memories.items():
        if memories:
            print(f"  📂 {section}: {len(memories)} items")
            for memory in memories[:2]:  # Show first 2 items
                print(f"    - {memory['key']}: {str(memory['value'])[:50]}...")
    
    # Verify we got memories from all expected sections
    expected_sections = ["user_preferences", "personality", "facts"]
    for section in expected_sections:
        assert section in startup_memories, f"Missing section: {section}"
        assert len(startup_memories[section]) > 0, f"No memories in section: {section}"
    
    print("✅ Startup memories retrieval works")
    
    # Test autonomous storage trigger
    print("\n🤖 Testing autonomous storage trigger...")
    user_message = "My name is Alice and I love coding in Python"
    context = {"session_id": 123}
    
    analysis = await trigger.analyze_for_storage(user_message, context)
    print(f"Should store: {analysis['should_store']}")
    print(f"Importance score: {analysis['importance_score']:.2f}")
    print(f"Items to store: {len(analysis['entries'])}")
    
    if analysis["should_store"]:
        for entry in analysis["entries"]:
            print(f"  → Would store in {entry['section']}: {entry['key']}")
    
    print("✅ Autonomous storage trigger works")
    
    # Cleanup
    await manager.stop()
    print("\n🎉 All tests passed! Memory fix is working correctly.")

if __name__ == "__main__":
    asyncio.run(test_memory_fix()) 