#!/usr/bin/env python3
"""
Test memory keyword matching.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.agent import startup, get_available_tools, _select_relevant_tools

async def test_memory_keywords():
    """Test memory keyword matching."""
    print("🔍 Testing Memory Keyword Matching")
    print("=" * 40)
    
    # Start the system
    await startup()
    
    # Get all available tools
    all_tools = await get_available_tools()
    print(f"Total available tools: {len(all_tools)}")
    
    # Test messages that should trigger memory tools
    test_messages = [
        "what is my name?",
        "what are my preferences?",
        "do you remember my name?",
        "load user preferences",
        "search for my name in memory",
        "what do you know about me?",
        "can you remember my preferences?",
        "what's stored about me?",
        "my name is Eric",
        "save my preferences"
    ]
    
    for message in test_messages:
        print(f"\n🔍 Testing: '{message}'")
        selected_tools = _select_relevant_tools(all_tools, message, max_tools=125)
        
        memory_tools = [tool for tool in selected_tools if 'memory' in tool['name'].lower()]
        print(f"  Selected tools: {len(selected_tools)}")
        print(f"  Memory tools: {len(memory_tools)}")
        
        if memory_tools:
            print("  ✅ Memory tools selected!")
            for tool in memory_tools[:3]:  # Show first 3
                print(f"    • {tool['name']}: {tool['description']}")
            if len(memory_tools) > 3:
                print(f"    ... and {len(memory_tools) - 3} more")
        else:
            print("  ❌ No memory tools selected!")
    
    print("\n✅ Memory keyword test completed!")

if __name__ == "__main__":
    asyncio.run(test_memory_keywords()) 