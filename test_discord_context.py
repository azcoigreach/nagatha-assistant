#!/usr/bin/env python3
"""
Test script for Discord context and firecrawl issues.
"""

import asyncio
import sys
import os
import aiohttp
import json

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_discord_context():
    """Test Discord conversation context."""
    print("🧠 Testing Discord Context")
    print("=" * 50)
    
    try:
        # Test the server API directly
        async with aiohttp.ClientSession() as session:
            # First message
            print("\n📝 Sending first message...")
            response1 = await session.post(
                "http://localhost:8081/process_message",
                json={
                    "message": "My name is Alice and I'm 25 years old",
                    "user_id": "discord:123456",
                    "interface": "discord",
                    "interface_context": {
                        "interface": "discord",
                        "channel_id": "789012",
                        "guild_id": "456789",
                        "message_id": "msg1",
                        "author": {
                            "id": "123456",
                            "name": "TestUser",
                            "bot": False
                        }
                    }
                }
            )
            
            if response1.status == 200:
                data1 = await response1.json()
                print(f"Response 1: {data1.get('response', '')[:100]}...")
            else:
                print(f"Error 1: {response1.status} - {await response1.text()}")
                return False
            
            # Second message (should maintain context)
            print("\n📝 Sending second message...")
            response2 = await session.post(
                "http://localhost:8081/process_message",
                json={
                    "message": "What's my name?",
                    "user_id": "discord:123456",
                    "interface": "discord",
                    "interface_context": {
                        "interface": "discord",
                        "channel_id": "789012",
                        "guild_id": "456789",
                        "message_id": "msg2",
                        "author": {
                            "id": "123456",
                            "name": "TestUser",
                            "bot": False
                        }
                    }
                }
            )
            
            if response2.status == 200:
                data2 = await response2.json()
                response_text2 = data2.get('response', '')
                print(f"Response 2: {response_text2[:100]}...")
                
                # Check if context was maintained
                context_maintained = "Alice" in response_text2.lower()
                print(f"Context maintained: {context_maintained}")
                
                return context_maintained
            else:
                print(f"Error 2: {response2.status} - {await response2.text()}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_firecrawl():
    """Test firecrawl MCP functionality."""
    print("\n🔥 Testing Firecrawl MCP")
    print("=" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test a simple firecrawl search
            print("\n📝 Testing firecrawl search...")
            response = await session.post(
                "http://localhost:8081/process_message",
                json={
                    "message": "Search for 'Python programming' on the web",
                    "user_id": "discord:123456",
                    "interface": "discord",
                    "interface_context": {
                        "interface": "discord",
                        "channel_id": "789012",
                        "guild_id": "456789",
                        "message_id": "msg3",
                        "author": {
                            "id": "123456",
                            "name": "TestUser",
                            "bot": False
                        }
                    }
                }
            )
            
            if response.status == 200:
                data = await response.json()
                response_text = data.get('response', '')
                print(f"Response: {response_text[:200]}...")
                
                # Check for firecrawl errors
                firecrawl_error = "json is not defined" in response_text.lower()
                if firecrawl_error:
                    print("❌ Firecrawl error detected: 'json is not defined'")
                    return False
                else:
                    print("✅ Firecrawl working correctly")
                    return True
            else:
                print(f"Error: {response.status} - {await response.text()}")
                return False
                
    except Exception as e:
        print(f"❌ Firecrawl test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the tests."""
    print("🧠 Testing Nagatha Discord Context and Firecrawl")
    print("=" * 50)
    
    # Test Discord context
    context_success = await test_discord_context()
    
    # Test firecrawl
    firecrawl_success = await test_firecrawl()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    print(f"Discord Context Test: {'✅ PASSED' if context_success else '❌ FAILED'}")
    print(f"Firecrawl Test: {'✅ PASSED' if firecrawl_success else '❌ FAILED'}")
    
    if context_success and firecrawl_success:
        print("\n🎉 All tests PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests FAILED!")
        if not context_success:
            print("   - Discord context not working")
        if not firecrawl_success:
            print("   - Firecrawl MCP has issues")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 