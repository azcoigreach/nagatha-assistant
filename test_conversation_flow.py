#!/usr/bin/env python3
"""
Test script to simulate the exact conversation flow from the web dashboard.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_conversation_flow():
    """Test the exact conversation flow that happens in the web dashboard."""
    
    print("🔍 Testing conversation flow for memory queries...")
    
    try:
        # Initialize the full Nagatha system first
        print("🚀 Initializing Nagatha system...")
        from nagatha_assistant.core.agent import startup, send_message, start_session
        
        startup_result = await startup()
        print(f"✅ Nagatha system startup completed: {startup_result}")
        
        # Create a new session
        print("📝 Creating new session...")
        session_id = await start_session()
        print(f"✅ Created session: {session_id}")
        
        # Test the exact query from the logs
        test_query = "what is my name"
        print(f"\n💬 Testing query: '{test_query}'")
        
        # Send the message using the same function as the web dashboard
        response = await send_message(session_id, test_query)
        print(f"🤖 Response: {response}")
        
        # Test another query
        test_query2 = "my name is Eric"
        print(f"\n💬 Testing query: '{test_query2}'")
        
        response2 = await send_message(session_id, test_query2)
        print(f"🤖 Response: {response2}")
        
        # Test asking again
        test_query3 = "what is my name"
        print(f"\n💬 Testing query: '{test_query3}'")
        
        response3 = await send_message(session_id, test_query3)
        print(f"🤖 Response: {response3}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_conversation_flow()) 