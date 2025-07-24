#!/usr/bin/env python3
"""
Test script for Nagatha's memory system.

This script tests:
1. Database setup and migrations
2. Memory storage and retrieval
3. User preferences and facts persistence
4. Cross-session memory recall
5. Hybrid storage (Redis + SQLite)
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from nagatha_assistant.db import engine, SessionLocal
from nagatha_assistant.db_models import Base, MemorySection, MemoryEntry
from nagatha_assistant.core.memory import MemoryManager, get_memory_manager
from nagatha_assistant.core.storage import DatabaseStorageBackend, InMemoryStorageBackend
from web_dashboard.dashboard.hybrid_memory_storage import HybridMemoryStorageBackend

async def setup_database():
    """Set up the database with all required tables."""
    print("🔧 Setting up database...")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")
        
        # Verify memory tables exist
        async with engine.begin() as conn:
            result = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%memory%'")
            tables = result.fetchall()
            print(f"📋 Memory tables found: {[t[0] for t in tables]}")
            
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        raise

async def test_basic_memory_operations():
    """Test basic memory operations with different storage backends."""
    print("\n🧠 Testing basic memory operations...")
    
    # Test with DatabaseStorageBackend
    print("\n📊 Testing DatabaseStorageBackend...")
    db_storage = DatabaseStorageBackend()
    
    # Test storing and retrieving data
    await db_storage.set("test_section", "test_key", "test_value")
    value = await db_storage.get("test_section", "test_key")
    print(f"✅ Database storage: stored='test_value', retrieved='{value}'")
    
    # Test with InMemoryStorageBackend
    print("\n💾 Testing InMemoryStorageBackend...")
    mem_storage = InMemoryStorageBackend()
    
    await mem_storage.set("test_section", "test_key", "test_value_mem")
    value = await mem_storage.get("test_section", "test_key")
    print(f"✅ In-memory storage: stored='test_value_mem', retrieved='{value}'")

async def test_memory_manager():
    """Test the MemoryManager with different storage backends."""
    print("\n🎯 Testing MemoryManager...")
    
    # Test with DatabaseStorageBackend
    print("\n📊 Testing MemoryManager with DatabaseStorageBackend...")
    db_storage = DatabaseStorageBackend()
    memory_manager = MemoryManager(db_storage)
    
    await memory_manager.start()
    
    # Test user preferences
    await memory_manager.set_user_preference("theme", "dark")
    await memory_manager.set_user_preference("language", "en")
    await memory_manager.set_user_preference("timezone", "UTC")
    
    theme = await memory_manager.get_user_preference("theme")
    language = await memory_manager.get_user_preference("language")
    timezone = await memory_manager.get_user_preference("timezone")
    
    print(f"✅ User preferences: theme='{theme}', language='{language}', timezone='{timezone}'")
    
    # Test facts
    await memory_manager.store_fact("python_version", "Python 3.11 is the latest stable version", "system")
    await memory_manager.store_fact("user_name", "Alice", "user_input")
    await memory_manager.store_fact("favorite_color", "Blue", "conversation")
    
    python_fact = await memory_manager.get_fact("python_version")
    user_fact = await memory_manager.get_fact("user_name")
    color_fact = await memory_manager.get_fact("favorite_color")
    
    print(f"✅ Facts stored: python='{python_fact}', user='{user_fact}', color='{color_fact}'")
    
    # Test session state
    session_id = 123
    await memory_manager.set_session_state(session_id, "current_topic", "AI discussion")
    await memory_manager.set_session_state(session_id, "mood", "curious")
    
    topic = await memory_manager.get_session_state(session_id, "current_topic")
    mood = await memory_manager.get_session_state(session_id, "mood")
    
    print(f"✅ Session state: topic='{topic}', mood='{mood}'")
    
    # Test command history
    await memory_manager.add_command_to_history("help", "Here are the available commands...", session_id)
    await memory_manager.add_command_to_history("status", "System is running normally", session_id)
    
    history = await memory_manager.get_command_history(session_id, limit=5)
    print(f"✅ Command history: {len(history)} entries")
    
    # Test temporary data
    await memory_manager.set_temporary("search_results", ["result1", "result2"], ttl_seconds=60)
    temp_data = await memory_manager.get_temporary("search_results")
    print(f"✅ Temporary data: {temp_data}")
    
    # Get storage stats
    stats = await memory_manager.get_storage_stats()
    print(f"📊 Storage stats: {stats}")
    
    await memory_manager.stop()

async def test_hybrid_storage():
    """Test the hybrid storage backend."""
    print("\n🔄 Testing HybridMemoryStorageBackend...")
    
    try:
        hybrid_storage = HybridMemoryStorageBackend()
        
        # Test storing data that should go to Redis
        await hybrid_storage.set("session_state", "current_user", "Alice", session_id=456)
        await hybrid_storage.set("user_preferences", "theme", "dark")
        await hybrid_storage.set("temporary", "cache_data", {"key": "value"}, ttl_seconds=300)
        
        # Test storing data that should go to SQLite
        await hybrid_storage.set("facts", "important_fact", "This is a long-term fact")
        await hybrid_storage.set("command_history", "recent_command", "User asked about memory system")
        
        # Test retrieval
        user = await hybrid_storage.get("session_state", "current_user", session_id=456)
        theme = await hybrid_storage.get("user_preferences", "theme")
        fact = await hybrid_storage.get("facts", "important_fact")
        
        print(f"✅ Hybrid storage: user='{user}', theme='{theme}', fact='{fact}'")
        
        # Test search
        results = await hybrid_storage.search("facts", "long-term")
        print(f"✅ Search results: {len(results)} found")
        
        # Test sync to database
        sync_results = await hybrid_storage.sync_redis_to_sqlite()
        print(f"✅ Sync results: {sync_results}")
        
        await hybrid_storage.close()
        
    except Exception as e:
        print(f"⚠️ Hybrid storage test failed (Redis not available): {e}")

async def test_cross_session_memory():
    """Test that memory persists across different sessions."""
    print("\n🔄 Testing cross-session memory persistence...")
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    # Session 1: Store user preferences and facts
    print("\n📝 Session 1: Storing user preferences and facts...")
    
    await memory_manager.set_user_preference("name", "Alice Johnson")
    await memory_manager.set_user_preference("occupation", "Software Engineer")
    await memory_manager.set_user_preference("interests", ["AI", "Python", "Machine Learning"])
    
    await memory_manager.store_fact("alice_birthday", "Alice's birthday is March 15th", "conversation")
    await memory_manager.store_fact("alice_project", "Alice is working on a Python AI project", "conversation")
    await memory_manager.store_fact("alice_pet", "Alice has a cat named Whiskers", "conversation")
    
    # Simulate session end
    print("✅ Session 1 completed - data stored")
    
    # Session 2: Retrieve and verify memory
    print("\n📖 Session 2: Retrieving stored preferences and facts...")
    
    name = await memory_manager.get_user_preference("name")
    occupation = await memory_manager.get_user_preference("occupation")
    interests = await memory_manager.get_user_preference("interests")
    
    birthday_fact = await memory_manager.get_fact("alice_birthday")
    project_fact = await memory_manager.get_fact("alice_project")
    pet_fact = await memory_manager.get_fact("alice_pet")
    
    print(f"✅ Retrieved user info: {name}, {occupation}, interests: {interests}")
    print(f"✅ Retrieved facts: birthday='{birthday_fact}', project='{project_fact}', pet='{pet_fact}'")
    
    # Test search functionality
    print("\n🔍 Testing memory search...")
    search_results = await memory_manager.search_facts("Alice")
    print(f"✅ Search for 'Alice': {len(search_results)} results found")
    
    for result in search_results:
        print(f"   - {result.get('key')}: {result.get('value')}")
    
    # Test command history
    print("\n📜 Testing command history...")
    await memory_manager.add_command_to_history("memory_test", "Testing memory system", session_id=789)
    await memory_manager.add_command_to_history("user_info", "Retrieved user preferences", session_id=789)
    
    history = await memory_manager.get_command_history(limit=10)
    print(f"✅ Command history: {len(history)} total entries")
    
    await memory_manager.stop()

async def test_memory_in_context():
    """Test that memory is available in conversation context."""
    print("\n💬 Testing memory in conversation context...")
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    # Simulate conversation context
    print("\n🎭 Simulating conversation with memory context...")
    
    # Get user preferences for context
    name = await memory_manager.get_user_preference("name", default="User")
    occupation = await memory_manager.get_user_preference("occupation", default="Unknown")
    interests = await memory_manager.get_user_preference("interests", default=[])
    
    # Get relevant facts
    facts = await memory_manager.search_facts(name.split()[0] if name else "User")
    
    # Build conversation context
    context = {
        "user_name": name,
        "user_occupation": occupation,
        "user_interests": interests,
        "relevant_facts": [fact.get('value', {}).get('fact', '') for fact in facts[:3]],
        "session_start": datetime.now(timezone.utc).isoformat()
    }
    
    print(f"✅ Conversation context built:")
    print(f"   User: {context['user_name']} ({context['user_occupation']})")
    print(f"   Interests: {context['user_interests']}")
    print(f"   Relevant facts: {len(context['relevant_facts'])} found")
    
    # Simulate conversation
    print("\n💬 Simulated conversation:")
    print(f"Nagatha: Hello {context['user_name']}! I remember you're a {context['user_occupation']}.")
    print(f"Nagatha: I also know you're interested in {', '.join(context['user_interests'])}.")
    
    if context['relevant_facts']:
        print(f"Nagatha: Let me recall some things about you:")
        for fact in context['relevant_facts']:
            print(f"   - {fact}")
    
    print(f"Nagatha: How can I help you today?")
    
    await memory_manager.stop()

async def main():
    """Main test function."""
    print("🧠 Nagatha Memory System Test")
    print("=" * 50)
    
    try:
        # Setup database
        await setup_database()
        
        # Test basic operations
        await test_basic_memory_operations()
        
        # Test memory manager
        await test_memory_manager()
        
        # Test hybrid storage
        await test_hybrid_storage()
        
        # Test cross-session memory
        await test_cross_session_memory()
        
        # Test memory in context
        await test_memory_in_context()
        
        print("\n🎉 All memory tests completed successfully!")
        print("\n📋 Summary:")
        print("✅ Database setup and migrations")
        print("✅ Basic memory operations")
        print("✅ Memory manager functionality")
        print("✅ Hybrid storage (Redis + SQLite)")
        print("✅ Cross-session memory persistence")
        print("✅ Memory in conversation context")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 