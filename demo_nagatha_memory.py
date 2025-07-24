#!/usr/bin/env python3
"""
Demonstration of Nagatha's Memory System in Action

This script demonstrates how Nagatha uses her memory to provide
personalized and contextual conversations.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from nagatha_assistant.core.memory import get_memory_manager

async def simulate_conversation():
    """Simulate a conversation where Nagatha uses her memory."""
    
    memory_manager = get_memory_manager()
    await memory_manager.start()
    
    print("🤖 Nagatha Memory System Demo")
    print("=" * 50)
    print("This demo shows how Nagatha uses her memory to provide personalized conversations.")
    print()
    
    # Simulate first conversation (learning about user)
    print("📝 First Conversation - Learning About User")
    print("-" * 40)
    
    # User tells Nagatha about themselves
    print("User: Hi Nagatha, I'm Alice and I'm a software engineer.")
    print("User: I'm working on a Python AI project and I love machine learning.")
    print("User: I prefer dark themes and I'm in the UTC timezone.")
    
    # Nagatha stores this information
    await memory_manager.set_user_preference("name", "Alice")
    await memory_manager.set_user_preference("occupation", "Software Engineer")
    await memory_manager.set_user_preference("interests", ["Python", "AI", "Machine Learning"])
    await memory_manager.set_user_preference("theme", "dark")
    await memory_manager.set_user_preference("timezone", "UTC")
    
    await memory_manager.store_fact("alice_project", "Alice is working on a Python AI project", "conversation")
    await memory_manager.store_fact("alice_interests", "Alice loves machine learning", "conversation")
    
    print("Nagatha: Nice to meet you, Alice! I'll remember that you're a software engineer.")
    print("Nagatha: I've noted your preferences for dark themes and UTC timezone.")
    print("Nagatha: I'm excited to help with your Python AI project!")
    print()
    
    # Simulate second conversation (recalling information)
    print("🔄 Second Conversation - Recalling Information")
    print("-" * 40)
    
    # Get user preferences and facts for context
    name = await memory_manager.get_user_preference("name")
    occupation = await memory_manager.get_user_preference("occupation")
    interests = await memory_manager.get_user_preference("interests")
    theme = await memory_manager.get_user_preference("theme")
    
    facts = await memory_manager.search_facts("Alice")
    project_facts = [f for f in facts if "project" in f.get('key', '')]
    
    print("User: Hi Nagatha, can you help me with my project?")
    
    # Nagatha recalls information and responds
    print(f"Nagatha: Hello {name}! Of course I can help with your project.")
    print(f"Nagatha: I remember you're a {occupation} working on a Python AI project.")
    print(f"Nagatha: Given your interest in {', '.join(interests)}, I'm sure we can make great progress!")
    
    if project_facts:
        print("Nagatha: Let me recall what you've told me about your project:")
        for fact in project_facts:
            fact_data = fact.get('value', {})
            print(f"   - {fact_data.get('fact', '')}")
    
    print()
    
    # Simulate learning new information
    print("📚 Learning New Information")
    print("-" * 40)
    
    print("User: Actually, I'm having trouble with the memory system in my AI project.")
    print("User: I need to implement long-term storage for user preferences.")
    
    # Nagatha stores new information
    await memory_manager.store_fact("alice_challenge", "Alice is having trouble implementing memory system for user preferences", "conversation")
    await memory_manager.store_fact("alice_goal", "Alice needs to implement long-term storage for user preferences", "conversation")
    
    print("Nagatha: I understand! Memory systems are crucial for AI assistants.")
    print("Nagatha: I've noted that you're working on implementing long-term storage for user preferences.")
    print("Nagatha: This is actually something I'm quite familiar with - I use a hybrid storage system myself!")
    print()
    
    # Simulate providing help
    print("💡 Providing Contextual Help")
    print("-" * 40)
    
    print("User: Can you help me understand how to implement this?")
    
    # Nagatha provides personalized help based on memory
    print(f"Nagatha: Absolutely, {name}! Since you're working with Python and AI, let me suggest an approach.")
    print("Nagatha: Based on your project needs, I'd recommend a hybrid storage system:")
    print("   - Use Redis for fast, temporary data (session state, cache)")
    print("   - Use SQLite/PostgreSQL for long-term persistence (user preferences, facts)")
    print("   - Implement automatic synchronization between the two")
    
    # Store the advice given
    await memory_manager.store_fact("advice_given", "Provided advice on hybrid storage system for memory implementation", "conversation")
    
    print()
    
    # Simulate follow-up conversation
    print("🔄 Follow-up Conversation - Enhanced Context")
    print("-" * 40)
    
    print("User: Thanks! That's really helpful. Can you show me an example?")
    
    # Nagatha recalls the full context
    name = await memory_manager.get_user_preference("name")
    occupation = await memory_manager.get_user_preference("occupation")
    project_facts = await memory_manager.search_facts("project")
    challenge_facts = await memory_manager.search_facts("trouble")
    
    print(f"Nagatha: Of course, {name}! Let me show you how I implement this in my own system.")
    print("Nagatha: Since you're a software engineer working on AI, I'll provide a practical example:")
    print()
    print("```python")
    print("# Hybrid Memory Storage Example")
    print("class HybridMemoryStorage:")
    print("    def __init__(self):")
    print("        self.redis = Redis()  # Fast access")
    print("        self.sqlite = SQLite()  # Long-term storage")
    print()
    print("    async def set_user_preference(self, key, value):")
    print("        # Store in both Redis (fast) and SQLite (persistent)")
    print("        await self.redis.set(f'pref:{key}', value)")
    print("        await self.sqlite.store_preference(key, value)")
    print("```")
    
    print("Nagatha: This way you get both speed and persistence!")
    print()
    
    # Simulate conversation end
    print("👋 Conversation Summary")
    print("-" * 40)
    
    # Show what Nagatha learned and can recall
    all_facts = await memory_manager.search_facts("Alice")
    preferences = {
        "name": await memory_manager.get_user_preference("name"),
        "occupation": await memory_manager.get_user_preference("occupation"),
        "interests": await memory_manager.get_user_preference("interests"),
        "theme": await memory_manager.get_user_preference("theme"),
        "timezone": await memory_manager.get_user_preference("timezone")
    }
    
    print("User: Thanks Nagatha! You've been really helpful.")
    
    print(f"Nagatha: You're welcome, {preferences['name']}! I've learned a lot about you:")
    print(f"   - You're a {preferences['occupation']} interested in {', '.join(preferences['interests'])}")
    print(f"   - You prefer {preferences['theme']} themes and {preferences['timezone']} timezone")
    print(f"   - You're working on a Python AI project with memory system challenges")
    print(f"   - I've provided you with advice on hybrid storage implementation")
    
    print("Nagatha: I'll remember all of this for our next conversation!")
    print("Nagatha: Feel free to come back anytime - I'll be ready to help with your project!")
    
    await memory_manager.stop()

async def main():
    """Main demonstration function."""
    try:
        await simulate_conversation()
        
        print("\n" + "=" * 50)
        print("🎉 Memory System Demo Complete!")
        print("\n💡 Key Features Demonstrated:")
        print("   • Learning and storing user information")
        print("   • Recalling information across conversations")
        print("   • Providing personalized responses")
        print("   • Building context for better assistance")
        print("   • Long-term memory persistence")
        print("   • Natural conversation flow with memory")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 