#!/usr/bin/env python3
"""
Demo script to test autonomous memory and personality management functionality.
"""

import asyncio
import os
from nagatha_assistant.core.memory import (
    MemoryTrigger, ContextualRecall, PersonalityMemory,
    MemoryMaintenance, MemoryManager
)
from nagatha_assistant.core.storage import InMemoryStorageBackend

async def main():
    """Demo the autonomous memory system."""
    print("🧠 Nagatha Autonomous Memory & Personality Management Demo")
    print("=" * 60)
    
    # Create memory manager with in-memory backend for demo
    manager = MemoryManager(storage_backend=InMemoryStorageBackend())
    await manager.start()
    print("✅ Memory manager started (using in-memory backend for demo)")
    
    # Get autonomous memory components
    trigger = MemoryTrigger(manager)
    recall = ContextualRecall(manager)
    personality = PersonalityMemory(manager)
    maintenance = MemoryMaintenance(manager)
    
    print("\n📝 Testing Memory Trigger - Analyzing User Messages")
    print("-" * 50)
    
    # Test user preference detection
    user_message1 = "I prefer detailed technical explanations and always like to see code examples."
    context1 = {"session_id": 123}
    
    result1 = await trigger.analyze_for_storage(user_message1, context1)
    print(f"Message: '{user_message1}'")
    print(f"Should store: {result1['should_store']}")
    print(f"Importance score: {result1['importance_score']:.2f}")
    print(f"Items to store: {len(result1['entries'])}")
    
    if result1["should_store"]:
        for entry in result1["entries"]:
            await manager.set(
                section=entry["section"],
                key=entry["key"],
                value=entry["value"],
                session_id=entry.get("session_id"),
                ttl_seconds=entry.get("ttl_seconds")
            )
            print(f"  → Stored in {entry['section']}: {entry['key']}")
    
    print("\n🎭 Testing Personality Cue Detection")
    print("-" * 40)
    
    # Test personality cue detection
    user_message2 = "I feel frustrated when responses are too formal. I enjoy casual, friendly conversation."
    context2 = {"session_id": 123}
    
    result2 = await trigger.analyze_for_storage(user_message2, context2)
    print(f"Message: '{user_message2}'")
    print(f"Should store: {result2['should_store']}")
    print(f"Items to store: {len(result2['entries'])}")
    
    if result2["should_store"]:
        for entry in result2["entries"]:
            await manager.set(
                section=entry["section"],
                key=entry["key"],
                value=entry["value"],
                session_id=entry.get("session_id"),
                ttl_seconds=entry.get("ttl_seconds")
            )
            print(f"  → Stored in {entry['section']}: {entry['key']}")
    
    print("\n🔍 Testing Contextual Recall")
    print("-" * 30)
    
    # Test contextual recall
    context = "I need help with programming"
    memories = await recall.get_relevant_memories(context, session_id=123, max_results=3)
    
    print(f"Context: '{context}'")
    print("Relevant memories found:")
    for section, memory_list in memories.items():
        if memory_list:
            print(f"  📂 {section}:")
            for memory in memory_list:
                print(f"    - {memory['key']}: {str(memory['value'])[:100]}...")
    
    print("\n🎨 Testing Personality Adaptations")
    print("-" * 35)
    
    # Test personality adaptations
    adaptations = await recall.get_personality_adaptations(context, session_id=123)
    print(f"Personality adaptations for context '{context}':")
    for key, value in adaptations.items():
        print(f"  • {key}: {value}")
    
    print("\n🔧 Testing Personality Memory Updates")
    print("-" * 40)
    
    # Update personality traits
    await personality.update_personality_trait(
        "communication_style", 
        "casual_friendly", 
        session_id=123,
        confidence=0.8
    )
    print("✅ Updated communication_style trait")
    
    # Get personality profile
    profile = await personality.get_personality_profile(session_id=123)
    print("Current personality profile:")
    for category, traits in profile.items():
        if traits:
            print(f"  📋 {category}: {len(traits)} traits")
    
    print("\n🧹 Testing Memory Maintenance")
    print("-" * 30)
    
    # Add some test duplicates
    await manager.set("user_preferences", "test1", "duplicate_value")
    await manager.set("user_preferences", "test2", "duplicate_value")
    
    # Run maintenance
    results = await maintenance.perform_maintenance()
    print("Maintenance results:")
    for operation, count in results.items():
        print(f"  • {operation}: {count}")
    
    print("\n📊 Memory Statistics")
    print("-" * 20)
    
    # Show storage stats
    stats = await manager.get_storage_stats()
    print("Current memory usage:")
    for section, count in stats.items():
        if isinstance(count, int):
            print(f"  📁 {section}: {count} entries")
    
    print("\n🎉 Demo completed successfully!")
    print("Autonomous memory and personality management is working! 🧠✨")
    
    # Clean up
    await manager.stop()

if __name__ == "__main__":
    asyncio.run(main())