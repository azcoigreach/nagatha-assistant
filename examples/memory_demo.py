#!/usr/bin/env python3
"""
Example script demonstrating the Nagatha Assistant Memory System.

This script shows how to use the various memory features including:
- User preferences
- Session state
- Command history
- Facts storage
- Temporary data
- Search functionality
"""

import sys
import os

# Add src directory to path so we can import nagatha_assistant
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import asyncio
import json
from datetime import datetime, timezone

from nagatha_assistant.core.memory import ensure_memory_manager_started, shutdown_memory_manager
from nagatha_assistant.core.event_bus import ensure_event_bus_started, shutdown_event_bus
from nagatha_assistant.core.event import StandardEventTypes


async def main():
    """Demonstrate memory system usage."""
    print("🧠 Nagatha Assistant Memory System Demo")
    print("=" * 50)
    
    # Start the event bus and memory system
    print("Starting memory system...")
    event_bus = await ensure_event_bus_started()
    memory_manager = await ensure_memory_manager_started()
    
    # Set up event listener to see memory events
    events_captured = []
    
    def memory_event_handler(event):
        events_captured.append(event)
        print(f"📡 Event: {event.event_type} - {event.data.get('section_name', '')}/{event.data.get('key', '')}")
    
    event_bus.subscribe("memory.*", memory_event_handler)
    
    print("✅ Memory system started!")
    print()
    
    # 1. User Preferences Demo
    print("1. 📋 User Preferences Demo")
    print("-" * 30)
    
    await memory_manager.set_user_preference("theme", "dark")
    await memory_manager.set_user_preference("language", "en")
    await memory_manager.set_user_preference("notifications", True)
    await memory_manager.set_user_preference("max_history", 100)
    
    theme = await memory_manager.get_user_preference("theme")
    language = await memory_manager.get_user_preference("language")
    notifications = await memory_manager.get_user_preference("notifications")
    
    print(f"Theme: {theme}")
    print(f"Language: {language}")
    print(f"Notifications: {notifications}")
    print()
    
    # 2. Session State Demo
    print("2. 🎯 Session State Demo")
    print("-" * 30)
    
    session_id = 12345
    await memory_manager.set_session_state(session_id, "current_task", "memory_demo")
    await memory_manager.set_session_state(session_id, "progress", 0.5)
    await memory_manager.set_session_state(session_id, "context", {
        "user_name": "Demo User",
        "conversation_topic": "Memory System",
        "started_at": datetime.now(timezone.utc).isoformat()
    })
    
    current_task = await memory_manager.get_session_state(session_id, "current_task")
    progress = await memory_manager.get_session_state(session_id, "progress")
    context = await memory_manager.get_session_state(session_id, "context")
    
    print(f"Current Task: {current_task}")
    print(f"Progress: {progress * 100}%")
    print(f"Context: {json.dumps(context, indent=2)}")
    print()
    
    # 3. Command History Demo
    print("3. 📜 Command History Demo")
    print("-" * 30)
    
    await memory_manager.add_command_to_history(
        "help", 
        "Available commands: help, status, preferences...", 
        session_id
    )
    await memory_manager.add_command_to_history(
        "status", 
        "System is running normally", 
        session_id
    )
    await memory_manager.add_command_to_history(
        "set theme dark", 
        "Theme updated to dark mode", 
        session_id
    )
    
    history = await memory_manager.get_command_history(session_id, limit=5)
    print(f"Command history (last {len(history)} commands):")
    for i, entry in enumerate(history):
        cmd_data = entry["value"]
        print(f"  {i+1}. {cmd_data['command']} -> {cmd_data['response']}")
    print()
    
    # 4. Facts Storage Demo
    print("4. 📚 Facts Storage Demo")
    print("-" * 30)
    
    await memory_manager.store_fact(
        "python_version", 
        "This system uses Python 3.12+", 
        source="system_info"
    )
    await memory_manager.store_fact(
        "memory_system", 
        "Nagatha has a persistent memory system with multiple storage backends", 
        source="documentation"
    )
    await memory_manager.store_fact(
        "user_preferences", 
        "User prefers dark theme and English language", 
        source="user_interaction"
    )
    
    # Retrieve specific fact
    python_fact = await memory_manager.get_fact("python_version")
    print(f"Python fact: {python_fact['fact']} (source: {python_fact['source']})")
    
    # Search facts
    memory_facts = await memory_manager.search_facts("memory")
    print(f"Facts about memory ({len(memory_facts)} found):")
    for fact_entry in memory_facts:
        fact_data = fact_entry["value"]
        print(f"  - {fact_data['fact']}")
    print()
    
    # 5. Temporary Storage Demo
    print("5. ⏰ Temporary Storage Demo")
    print("-" * 30)
    
    await memory_manager.set_temporary("api_token", "temp_token_12345", ttl_seconds=5)
    await memory_manager.set_temporary("cache_data", {"result": "computed_value"}, ttl_seconds=3)
    
    token = await memory_manager.get_temporary("api_token")
    cache = await memory_manager.get_temporary("cache_data")
    print(f"API Token: {token}")
    print(f"Cache Data: {cache}")
    
    print("Waiting 4 seconds for cache to expire...")
    await asyncio.sleep(4)
    
    token_after = await memory_manager.get_temporary("api_token")
    cache_after = await memory_manager.get_temporary("cache_data", default="expired")
    print(f"API Token after 4s: {token_after}")
    print(f"Cache Data after 4s: {cache_after}")
    print()
    
    # 6. Search Across Sections Demo
    print("6. 🔍 Search Across Sections Demo")
    print("-" * 30)
    
    # Search for "dark" across user preferences
    dark_prefs = await memory_manager.search("user_preferences", "dark")
    print(f"'dark' in user preferences: {len(dark_prefs)} results")
    for result in dark_prefs:
        print(f"  {result['key']}: {result['value']}")
    
    # Search for "python" in facts
    python_facts = await memory_manager.search("facts", "python")
    print(f"'python' in facts: {len(python_facts)} results")
    for result in python_facts:
        fact_data = result["value"]
        print(f"  {result['key']}: {fact_data['fact']}")
    print()
    
    # 7. Storage Statistics Demo
    print("7. 📊 Storage Statistics Demo")
    print("-" * 30)
    
    stats = await memory_manager.get_storage_stats()
    print("Memory usage statistics:")
    for section, count in stats.items():
        if isinstance(count, int):
            print(f"  {section}: {count} entries")
        else:
            print(f"  {section}: {count}")
    print()
    
    # 8. Cleanup Demo
    print("8. 🧹 Cleanup Demo")
    print("-" * 30)
    
    # Show keys before cleanup
    test_keys = await memory_manager.list_keys("user_preferences")
    print(f"User preferences before cleanup: {len(test_keys)} keys")
    
    # Clear temporary section
    cleared = await memory_manager.clear_section("temporary")
    print(f"Cleared {cleared} temporary entries")
    
    # Show events that were captured
    print()
    print("9. 📡 Captured Events Summary")
    print("-" * 30)
    event_types = {}
    for event in events_captured:
        event_type = event.event_type
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    for event_type, count in event_types.items():
        print(f"  {event_type}: {count} events")
    
    print()
    print("✨ Demo completed successfully!")
    
    # Cleanup
    print("Shutting down memory system...")
    await shutdown_memory_manager()
    await shutdown_event_bus()
    print("✅ Memory system shut down cleanly")


if __name__ == "__main__":
    asyncio.run(main())