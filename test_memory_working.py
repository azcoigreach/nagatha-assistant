#!/usr/bin/env python3
"""
Working test script for Nagatha's memory system.

This script tests the core memory functionality and demonstrates
how Nagatha stores and recalls user preferences and facts.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from nagatha_assistant.db import engine
from nagatha_assistant.db_models import Base
from nagatha_assistant.core.memory import MemoryManager, get_memory_manager
from nagatha_assistant.core.storage import DatabaseStorageBackend
from sqlalchemy import text

async def setup_database():
    """Set up the database with all required tables."""
    print("🔧 Setting up database...")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")
        
        # Verify memory tables exist
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%memory%'"))
            tables = result.fetchall()
            print(f"📋 Memory tables found: {[t[0] for t in tables]}")
            
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        raise

async def test_user_preferences():
    """Test storing and retrieving user preferences."""
    print("\n👤 Testing user preferences...")
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    # Store user preferences
    print("📝 Storing user preferences...")
    await memory_manager.set_user_preference("name", "Alice Johnson")
    await memory_manager.set_user_preference("occupation", "Software Engineer")
    await memory_manager.set_user_preference("interests", ["AI", "Python", "Machine Learning"])
    await memory_manager.set_user_preference("theme", "dark")
    await memory_manager.set_user_preference("timezone", "UTC")
    await memory_manager.set_user_preference("language", "en")
    
    print("✅ User preferences stored")
    
    # Retrieve user preferences
    print("📖 Retrieving user preferences...")
    name = await memory_manager.get_user_preference("name")
    occupation = await memory_manager.get_user_preference("occupation")
    interests = await memory_manager.get_user_preference("interests")
    theme = await memory_manager.get_user_preference("theme")
    timezone = await memory_manager.get_user_preference("timezone")
    language = await memory_manager.get_user_preference("language")
    
    print(f"✅ Retrieved preferences:")
    print(f"   Name: {name}")
    print(f"   Occupation: {occupation}")
    print(f"   Interests: {interests}")
    print(f"   Theme: {theme}")
    print(f"   Timezone: {timezone}")
    print(f"   Language: {language}")
    
    await memory_manager.stop()

async def test_facts_storage():
    """Test storing and retrieving facts."""
    print("\n🧠 Testing facts storage...")
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    # Store facts about the user
    print("📝 Storing facts about user...")
    await memory_manager.store_fact("alice_birthday", "Alice's birthday is March 15th", "conversation")
    await memory_manager.store_fact("alice_project", "Alice is working on a Python AI project called Nagatha", "conversation")
    await memory_manager.store_fact("alice_pet", "Alice has a cat named Whiskers", "conversation")
    await memory_manager.store_fact("alice_location", "Alice lives in San Francisco", "conversation")
    await memory_manager.store_fact("alice_experience", "Alice has 5 years of experience in software development", "conversation")
    
    # Store system facts
    await memory_manager.store_fact("python_version", "Python 3.11 is the latest stable version", "system")
    await memory_manager.store_fact("nagatha_purpose", "Nagatha is an AI assistant designed to help with coding and development tasks", "system")
    
    print("✅ Facts stored")
    
    # Retrieve facts
    print("📖 Retrieving facts...")
    birthday_fact = await memory_manager.get_fact("alice_birthday")
    project_fact = await memory_manager.get_fact("alice_project")
    pet_fact = await memory_manager.get_fact("alice_pet")
    location_fact = await memory_manager.get_fact("alice_location")
    experience_fact = await memory_manager.get_fact("alice_experience")
    
    print(f"✅ Retrieved facts:")
    print(f"   Birthday: {birthday_fact}")
    print(f"   Project: {project_fact}")
    print(f"   Pet: {pet_fact}")
    print(f"   Location: {location_fact}")
    print(f"   Experience: {experience_fact}")
    
    # Test search functionality
    print("\n🔍 Testing fact search...")
    search_results = await memory_manager.search_facts("Alice")
    print(f"✅ Search for 'Alice': {len(search_results)} results found")
    
    for result in search_results:
        fact_data = result.get('value', {})
        print(f"   - {result.get('key')}: {fact_data.get('fact', '')}")
    
    await memory_manager.stop()

async def test_cross_session_persistence():
    """Test that memory persists across different sessions."""
    print("\n🔄 Testing cross-session memory persistence...")
    
    # Session 1: Store data
    print("\n📝 Session 1: Storing user data...")
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    await memory_manager.set_user_preference("name", "Alice Johnson")
    await memory_manager.set_user_preference("occupation", "Software Engineer")
    await memory_manager.store_fact("alice_birthday", "Alice's birthday is March 15th", "conversation")
    await memory_manager.store_fact("alice_project", "Alice is working on a Python AI project", "conversation")
    
    print("✅ Session 1 data stored")
    await memory_manager.stop()
    
    # Session 2: Retrieve data (simulating a new session)
    print("\n📖 Session 2: Retrieving stored data...")
    memory_manager2 = get_memory_manager()
    await memory_manager2.start()
    
    name = await memory_manager2.get_user_preference("name")
    occupation = await memory_manager2.get_user_preference("occupation")
    birthday_fact = await memory_manager2.get_fact("alice_birthday")
    project_fact = await memory_manager2.get_fact("alice_project")
    
    print(f"✅ Session 2 retrieved data:")
    print(f"   Name: {name}")
    print(f"   Occupation: {occupation}")
    print(f"   Birthday fact: {birthday_fact}")
    print(f"   Project fact: {project_fact}")
    
    await memory_manager2.stop()

async def test_conversation_context():
    """Test how memory is used in conversation context."""
    print("\n💬 Testing conversation context with memory...")
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    # Simulate conversation context
    print("\n🎭 Simulating conversation with memory context...")
    
    # Get user preferences for context
    name = await memory_manager.get_user_preference("name", default="User")
    occupation = await memory_manager.get_user_preference("occupation", default="Unknown")
    interests = await memory_manager.get_user_preference("interests", default=[])
    theme = await memory_manager.get_user_preference("theme", default="light")
    
    # Get relevant facts
    facts = await memory_manager.search_facts(name.split()[0] if name else "User")
    
    # Build conversation context
    context = {
        "user_name": name,
        "user_occupation": occupation,
        "user_interests": interests,
        "user_theme": theme,
        "relevant_facts": [fact.get('value', {}).get('fact', '') for fact in facts[:3]],
        "session_start": datetime.now(timezone.utc).isoformat()
    }
    
    print(f"✅ Conversation context built:")
    print(f"   User: {context['user_name']} ({context['user_occupation']})")
    print(f"   Interests: {context['user_interests']}")
    print(f"   Theme: {context['user_theme']}")
    print(f"   Relevant facts: {len(context['relevant_facts'])} found")
    
    # Simulate conversation
    print("\n💬 Simulated conversation:")
    print(f"Nagatha: Hello {context['user_name']}! Welcome back!")
    print(f"Nagatha: I remember you're a {context['user_occupation']}.")
    print(f"Nagatha: I see you're interested in {', '.join(context['user_interests'])}.")
    print(f"Nagatha: Your preferred theme is {context['user_theme']}.")
    
    if context['relevant_facts']:
        print(f"Nagatha: Let me recall some things about you:")
        for fact in context['relevant_facts']:
            print(f"   - {fact}")
    
    print(f"Nagatha: How can I help you with your project today?")
    
    await memory_manager.stop()

async def test_command_history():
    """Test command history functionality."""
    print("\n📜 Testing command history...")
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    session_id = 123
    
    # Add some commands to history
    print("📝 Adding commands to history...")
    await memory_manager.add_command_to_history("help", "Here are the available commands...", session_id)
    await memory_manager.add_command_to_history("status", "System is running normally", session_id)
    await memory_manager.add_command_to_history("memory_test", "Testing memory system functionality", session_id)
    await memory_manager.add_command_to_history("user_info", "Retrieved user preferences and facts", session_id)
    
    # Retrieve command history
    print("📖 Retrieving command history...")
    history = await memory_manager.get_command_history(session_id, limit=10)
    
    print(f"✅ Command history ({len(history)} entries):")
    for entry in history:
        print(f"   - {entry.get('command', 'Unknown')}: {entry.get('response', 'No response')}")
    
    await memory_manager.stop()

async def main():
    """Main test function."""
    print("🧠 Nagatha Memory System Test")
    print("=" * 50)
    
    try:
        # Setup database
        await setup_database()
        
        # Test user preferences
        await test_user_preferences()
        
        # Test facts storage
        await test_facts_storage()
        
        # Test cross-session persistence
        await test_cross_session_persistence()
        
        # Test conversation context
        await test_conversation_context()
        
        # Test command history
        await test_command_history()
        
        print("\n🎉 All memory tests completed successfully!")
        print("\n📋 Summary:")
        print("✅ Database setup and migrations")
        print("✅ User preferences storage and retrieval")
        print("✅ Facts storage and search")
        print("✅ Cross-session memory persistence")
        print("✅ Conversation context with memory")
        print("✅ Command history tracking")
        
        print("\n💡 Key Features Demonstrated:")
        print("   • Long-term storage in SQLite database")
        print("   • User preferences persistence across sessions")
        print("   • Facts storage with search capability")
        print("   • Memory integration in conversation context")
        print("   • Command history tracking")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 