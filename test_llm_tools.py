#!/usr/bin/env python3
"""
Test what tools are being sent to the LLM.
"""

import sys
import os
import asyncio

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

from nagatha_assistant.core.agent import startup, get_available_tools, _select_relevant_tools

async def test_llm_tools():
    """Test what tools are being sent to the LLM."""
    print("🤖 Testing LLM Tool Selection")
    print("=" * 40)
    
    # Start the system
    await startup()
    
    # Get all available tools
    all_tools = await get_available_tools()
    print(f"Total available tools: {len(all_tools)}")
    
    # Test tool selection for different user messages
    test_messages = [
        "what is my name?",
        "what are my preferences?",
        "do you remember my name?",
        "load user preferences",
        "search for my name in memory"
    ]
    
    for message in test_messages:
        print(f"\n🔍 Testing message: '{message}'")
        selected_tools = _select_relevant_tools(all_tools, message, max_tools=125)
        
        memory_tools = [tool for tool in selected_tools if 'memory' in tool['name'].lower()]
        print(f"  Selected tools: {len(selected_tools)}")
        print(f"  Memory tools: {len(memory_tools)}")
        
        if memory_tools:
            for tool in memory_tools:
                print(f"    • {tool['name']}: {tool['description']}")
        else:
            print("    ❌ No memory tools selected!")
    
    print("\n✅ LLM tool selection test completed!")

if __name__ == "__main__":
    asyncio.run(test_llm_tools()) 