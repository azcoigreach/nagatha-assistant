#!/usr/bin/env python3
"""
Test script to debug tool selection for memory queries.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_tool_selection():
    """Test what tools are selected for memory queries."""
    
    print("🔍 Testing tool selection for memory queries...")
    
    try:
        # Initialize the full Nagatha system first
        print("🚀 Initializing Nagatha system...")
        from nagatha_assistant.core.agent import startup, get_available_tools, _select_relevant_tools
        
        startup_result = await startup()
        print(f"✅ Nagatha system startup completed: {startup_result}")
        
        # Get all available tools
        print("📋 Getting all available tools...")
        all_tools = await get_available_tools()
        print(f"✅ Found {len(all_tools)} total tools")
        
        # Show all tool names for debugging
        print("🔧 All available tools:")
        for i, tool in enumerate(all_tools):
            print(f"   {i+1:2d}. {tool['name']}: {tool.get('description', 'No description')}")
        
        # Test different queries
        test_queries = [
            "what is my name",
            "what's my name", 
            "do you remember my name",
            "what are my preferences",
            "my name is Eric"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Testing query: '{query}'")
            
            # Select relevant tools
            selected_tools = _select_relevant_tools(all_tools, query)
            print(f"📊 Selected {len(selected_tools)} tools out of {len(all_tools)}")
            
            # Look for memory tools
            memory_tools = [t for t in selected_tools if 'memory' in t.get('name', '').lower()]
            if memory_tools:
                print(f"✅ Found {len(memory_tools)} memory tools:")
                for tool in memory_tools:
                    print(f"   - {tool['name']}: {tool.get('description', 'No description')}")
            else:
                print("❌ No memory tools selected!")
                
                # Show what memory tools are available
                all_memory_tools = [t for t in all_tools if 'memory' in t.get('name', '').lower()]
                if all_memory_tools:
                    print(f"   Available memory tools ({len(all_memory_tools)}):")
                    for tool in all_memory_tools:
                        print(f"     - {tool['name']}: {tool.get('description', 'No description')}")
                else:
                    print("   No memory tools found in available tools!")
        
        # Test the specific memory tool
        print(f"\n🔍 Testing specific memory tool call...")
        from nagatha_assistant.core.agent import call_tool_or_command
        
        try:
            result = await call_tool_or_command("memory_get_user_preference", {"key": "name"})
            print(f"✅ memory_get_user_preference result: {result}")
        except Exception as e:
            print(f"❌ memory_get_user_preference failed: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tool_selection()) 