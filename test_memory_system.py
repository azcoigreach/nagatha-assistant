#!/usr/bin/env python3
"""
Test script for the new memory system.

This script tests:
1. Redis connection and short-term memory
2. Conversation context storage and retrieval
3. Session state management
4. Number and fact remembering
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.core.short_term_memory import ensure_short_term_memory_started, shutdown_short_term_memory
from nagatha_assistant.core.memory import ensure_memory_manager_started, shutdown_memory_manager
from nagatha_assistant.plugins.conversation_memory import get_conversation_memory_plugin


async def test_redis_connection():
    """Test Redis connection and basic operations."""
    print("Testing Redis connection...")
    
    try:
        short_term_memory = await ensure_short_term_memory_started()
        print("✅ Redis connection successful")
        
        # Test basic operations
        await short_term_memory.set_temporary_data("test_key", "test_value", 60)
        value = await short_term_memory.get_temporary_data("test_key")
        assert value == "test_value"
        print("✅ Basic Redis operations successful")
        
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False


async def test_conversation_context():
    """Test conversation context storage and retrieval."""
    print("\nTesting conversation context...")
    
    try:
        short_term_memory = await ensure_short_term_memory_started()
        
        # Add some test conversation context
        session_id = 123
        await short_term_memory.add_conversation_context(
            session_id, 1, "user", "Hello, my name is Alice"
        )
        await short_term_memory.add_conversation_context(
            session_id, 2, "assistant", "Hello Alice! Nice to meet you."
        )
        await short_term_memory.add_conversation_context(
            session_id, 3, "user", "My phone number is 555-1234"
        )
        
        # Retrieve conversation context
        context = await short_term_memory.get_conversation_context(session_id, limit=10)
        
        assert len(context) == 3
        assert context[0].content == "My phone number is 555-1234"  # Most recent
        assert context[2].content == "Hello, my name is Alice"  # Oldest
        
        print("✅ Conversation context storage and retrieval successful")
        return True
    except Exception as e:
        print(f"❌ Conversation context test failed: {e}")
        return False


async def test_session_state():
    """Test session state management."""
    print("\nTesting session state management...")
    
    try:
        short_term_memory = await ensure_short_term_memory_started()
        
        session_id = 456
        
        # Update session state
        await short_term_memory.update_session_state(session_id, {
            "current_topic": "memory testing",
            "user_intent": "testing functionality"
        })
        
        # Get session state
        state = await short_term_memory.get_session_state(session_id)
        
        assert state is not None
        assert state.current_topic == "memory testing"
        assert state.user_intent == "testing functionality"
        
        print("✅ Session state management successful")
        return True
    except Exception as e:
        print(f"❌ Session state test failed: {e}")
        return False


async def test_number_remembering():
    """Test number remembering functionality."""
    print("\nTesting number remembering...")
    
    try:
        plugin = get_conversation_memory_plugin()
        await plugin.initialize()
        
        session_id = 789
        
        # Remember a number
        success = await plugin.remember_number(session_id, 42, "Answer to life")
        assert success
        
        # Recall the number
        number_info = await plugin.recall_number(session_id)
        assert number_info is not None
        assert number_info["number"] == 42
        assert number_info["context"] == "Answer to life"
        
        print("✅ Number remembering successful")
        return True
    except Exception as e:
        print(f"❌ Number remembering test failed: {e}")
        return False


async def test_fact_remembering():
    """Test fact remembering functionality."""
    print("\nTesting fact remembering...")
    
    try:
        plugin = get_conversation_memory_plugin()
        await plugin.initialize()
        
        session_id = 101
        
        # Remember some facts
        await plugin.remember_fact(session_id, "Python is a programming language", "programming")
        await plugin.remember_fact(session_id, "Redis is a key-value store", "technology")
        
        # Search for facts
        facts = await plugin.search_remembered_facts(session_id, "Python")
        assert len(facts) > 0
        
        facts = await plugin.search_remembered_facts(session_id, "Redis")
        assert len(facts) > 0
        
        print("✅ Fact remembering successful")
        return True
    except Exception as e:
        print(f"❌ Fact remembering test failed: {e}")
        return False


async def test_conversation_stats():
    """Test conversation statistics."""
    print("\nTesting conversation statistics...")
    
    try:
        plugin = get_conversation_memory_plugin()
        await plugin.initialize()
        
        session_id = 202
        
        # Add some conversation context first
        short_term_memory = await ensure_short_term_memory_started()
        await short_term_memory.add_conversation_context(
            session_id, 1, "user", "First message"
        )
        await short_term_memory.add_conversation_context(
            session_id, 2, "assistant", "First response"
        )
        await short_term_memory.add_conversation_context(
            session_id, 3, "user", "Second message"
        )
        
        # Get conversation stats
        stats = await plugin.get_conversation_stats(session_id)
        
        assert stats["total_messages"] == 3
        assert stats["user_messages"] == 2
        assert stats["assistant_messages"] == 1
        
        print("✅ Conversation statistics successful")
        return True
    except Exception as e:
        print(f"❌ Conversation statistics test failed: {e}")
        return False


async def main():
    """Run all memory system tests."""
    print("🧠 Testing Nagatha Memory System")
    print("=" * 50)
    
    tests = [
        test_redis_connection,
        test_conversation_context,
        test_session_state,
        test_number_remembering,
        test_fact_remembering,
        test_conversation_stats
    ]
    
    results = []
    
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    # Cleanup
    try:
        await shutdown_short_term_memory()
        await shutdown_memory_manager()
    except Exception as e:
        print(f"Warning: Error during cleanup: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1:2d}. {test.__name__:25s} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Memory system is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 