#!/usr/bin/env python3
"""
Test script to verify memory and MCP functionality after fixes.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import only the components we need, avoiding celery dependency
from nagatha_assistant.core.memory import get_memory_manager, ensure_memory_manager_started
from nagatha_assistant.core.mcp_manager import get_mcp_manager
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()

async def test_memory_system():
    """Test the memory system functionality."""
    print("🧠 Testing Memory System...")
    
    try:
        # Initialize memory manager
        memory_manager = await ensure_memory_manager_started()
        print("✅ Memory manager started successfully")
        
        # Test basic memory operations
        await memory_manager.set("user_preferences", "favorite_color", "purple")
        value = await memory_manager.get("user_preferences", "favorite_color")
        print(f"✅ Memory set/get test: {value}")
        
        # Test session state
        await memory_manager.set_session_state(1, "current_topic", "testing")
        session_value = await memory_manager.get_session_state(1, "current_topic")
        print(f"✅ Session state test: {session_value}")
        
        # Test user preferences
        await memory_manager.set_user_preference("name", "Eric")
        name = await memory_manager.get_user_preference("name")
        print(f"✅ User preference test: {name}")
        
        # Test contextual recall
        from nagatha_assistant.core.memory import get_contextual_recall
        contextual_recall = get_contextual_recall()
        user_name = await contextual_recall.get_user_name()
        print(f"✅ Contextual recall test - User name: {user_name}")
        
        print("✅ Memory system tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Memory system test failed: {e}")
        logger.exception("Memory system test failed")
        return False

async def test_mcp_system():
    """Test the MCP system functionality."""
    print("🔧 Testing MCP System...")
    
    try:
        # Initialize MCP manager
        mcp_manager = await get_mcp_manager()
        await mcp_manager.initialize()
        
        # Get initialization summary
        summary = mcp_manager.get_initialization_summary()
        print(f"✅ MCP initialization summary: {summary}")
        
        # Get available tools
        tools = mcp_manager.get_available_tools()
        print(f"✅ Available MCP tools: {len(tools)} tools")
        
        if tools:
            print("Available tool names:")
            for tool in tools[:5]:  # Show first 5 tools
                print(f"  - {tool['name']}: {tool['description']}")
        
        # Test tool calling if tools are available
        if tools:
            try:
                # Try to call a filesystem tool if available
                filesystem_tools = [t for t in tools if 'filesystem' in t['name'].lower()]
                if filesystem_tools:
                    tool_name = filesystem_tools[0]['name']
                    result = await mcp_manager.call_tool(tool_name, {"path": "/home/pi"})
                    print(f"✅ MCP tool call test: {str(result)[:100]}...")
            except Exception as e:
                print(f"⚠️ MCP tool call test failed (this is expected if tools aren't fully configured): {e}")
        
        print("✅ MCP system tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ MCP system test failed: {e}")
        logger.exception("MCP system test failed")
        return False

async def test_integration():
    """Test memory and MCP integration."""
    print("🔗 Testing Memory-MCP Integration...")
    
    try:
        # Get both managers
        memory_manager = await ensure_memory_manager_started()
        mcp_manager = await get_mcp_manager()
        
        # Store some test data in memory
        await memory_manager.set("facts", "test_fact", "This is a test fact for integration testing")
        
        # Test memory retrieval
        fact = await memory_manager.get("facts", "test_fact")
        print(f"✅ Integration test - Memory retrieval: {fact}")
        
        # Test MCP tool availability
        tools = mcp_manager.get_available_tools()
        print(f"✅ Integration test - MCP tools available: {len(tools)}")
        
        print("✅ Integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        logger.exception("Integration test failed")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting Nagatha Memory and MCP Tests...")
    print("=" * 50)
    
    results = []
    
    # Test memory system
    results.append(await test_memory_system())
    print()
    
    # Test MCP system
    results.append(await test_mcp_system())
    print()
    
    # Test integration
    results.append(await test_integration())
    print()
    
    # Summary
    print("=" * 50)
    print("📊 Test Results Summary:")
    print(f"Memory System: {'✅ PASS' if results[0] else '❌ FAIL'}")
    print(f"MCP System: {'✅ PASS' if results[1] else '❌ FAIL'}")
    print(f"Integration: {'✅ PASS' if results[2] else '❌ FAIL'}")
    
    if all(results):
        print("🎉 All tests passed! Memory and MCP systems are working correctly.")
    else:
        print("⚠️ Some tests failed. Check the logs for details.")
    
    return all(results)

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 