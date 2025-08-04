#!/usr/bin/env python3
"""
Test script for session context maintenance.

This script tests that Discord conversations maintain context across messages.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.server.core_server import AgentSessionManager


async def test_session_manager():
    """Test the session manager directly."""
    print("🧠 Testing Session Manager")
    print("=" * 50)
    
    try:
        # Create session manager
        session_manager = AgentSessionManager()
        
        # Test Discord-like session context
        user_id = "discord:123456"
        interface = "discord"
        channel_id = "789012"
        
        interface_context = {
            "interface": "discord",
            "channel_id": channel_id,
            "guild_id": "456789",
            "message_id": "msg1",
            "author": {
                "id": "123456",
                "name": "TestUser",
                "bot": False
            }
        }
        
        # Create first session
        print("\n📝 Creating first session...")
        session_id1 = await session_manager.get_or_create_session(
            user_id=user_id,
            interface=interface,
            interface_context=interface_context
        )
        print(f"Session ID 1: {session_id1}")
        
        # Create second session with same channel (should reuse)
        print("\n📝 Creating second session (same channel)...")
        interface_context["message_id"] = "msg2"
        session_id2 = await session_manager.get_or_create_session(
            user_id=user_id,
            interface=interface,
            interface_context=interface_context
        )
        print(f"Session ID 2: {session_id2}")
        
        # Create third session with different channel (should be new)
        print("\n📝 Creating third session (different channel)...")
        interface_context["channel_id"] = "999999"
        interface_context["message_id"] = "msg3"
        session_id3 = await session_manager.get_or_create_session(
            user_id=user_id,
            interface=interface,
            interface_context=interface_context
        )
        print(f"Session ID 3: {session_id3}")
        
        # Check results
        session_reused = session_id1 == session_id2
        session_different = session_id1 != session_id3
        
        print(f"\n📊 Results:")
        print(f"  Session 1 == Session 2: {session_reused} (should be True)")
        print(f"  Session 1 != Session 3: {session_different} (should be True)")
        
        # Check session info
        print(f"\n📋 Session Information:")
        for session_id in [session_id1, session_id2, session_id3]:
            session_info = session_manager.get_session_info(str(session_id))
            if session_info:
                print(f"  Session {session_id}:")
                print(f"    User ID: {session_info.get('user_id')}")
                print(f"    Interface: {session_info.get('interface')}")
                print(f"    Session Key: {session_info.get('session_key')}")
                print(f"    Status: {session_info.get('status')}")
        
        success = session_reused and session_different
        
        if success:
            print("\n✅ Session manager working correctly!")
            print("   - Same channel reuses session")
            print("   - Different channel creates new session")
        else:
            print("\n❌ Session manager not working correctly")
            print("   - Expected same channel to reuse session")
            print("   - Expected different channel to create new session")
        
        return success
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_server():
    """Test with a full server instance."""
    print("\n🧠 Testing Full Server Context")
    print("=" * 50)
    
    try:
        from nagatha_assistant.server.core_server import NagathaUnifiedServer, ServerConfig
        
        # Create server instance with different port
        config = ServerConfig(host="localhost", port=8082)
        server = NagathaUnifiedServer(config)
        
        # Start the server
        await server.start()
        print("✅ Server started successfully")
        
        # Test Discord-like session context
        user_id = "discord:123456"
        interface = "discord"
        channel_id = "789012"
        
        interface_context = {
            "interface": "discord",
            "channel_id": channel_id,
            "guild_id": "456789",
            "message_id": "msg1",
            "author": {
                "id": "123456",
                "name": "TestUser",
                "bot": False
            }
        }
        
        # Send first message
        print("\n📝 Sending first message...")
        response1 = await server.process_message(
            message="My name is Alice and I'm 25 years old",
            user_id=user_id,
            interface=interface,
            interface_context=interface_context
        )
        print(f"Response 1: {response1[:100]}...")
        
        # Send second message (should maintain context)
        print("\n📝 Sending second message...")
        interface_context["message_id"] = "msg2"
        response2 = await server.process_message(
            message="What's my name?",
            user_id=user_id,
            interface=interface,
            interface_context=interface_context
        )
        print(f"Response 2: {response2[:100]}...")
        
        # Send third message (should remember the number)
        print("\n📝 Sending third message...")
        interface_context["message_id"] = "msg3"
        response3 = await server.process_message(
            message="How old am I?",
            user_id=user_id,
            interface=interface,
            interface_context=interface_context
        )
        print(f"Response 3: {response3[:100]}...")
        
        # Check if context was maintained
        context_maintained = (
            "Alice" in response2.lower() and 
            "25" in response3.lower()
        )
        
        if context_maintained:
            print("\n✅ Session context maintained successfully!")
            print("   - Nagatha remembered the name 'Alice'")
            print("   - Nagatha remembered the age '25'")
        else:
            print("\n❌ Session context not maintained")
            print("   - Expected to see 'Alice' in response 2")
            print("   - Expected to see '25' in response 3")
        
        return context_maintained
        
    except Exception as e:
        print(f"❌ Full server test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            await server.stop()
            print("\n✅ Server stopped successfully")
        except Exception as e:
            print(f"⚠️  Error stopping server: {e}")


async def main():
    """Run the session context tests."""
    print("🧠 Testing Nagatha Session Context")
    print("=" * 50)
    
    # Test session manager directly
    session_manager_success = await test_session_manager()
    
    # Test full server (optional - comment out if port conflicts)
    full_server_success = await test_full_server()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    print(f"Session Manager Test: {'✅ PASSED' if session_manager_success else '❌ FAILED'}")
    print(f"Full Server Test: {'✅ PASSED' if full_server_success else '❌ FAILED'}")
    
    if session_manager_success and full_server_success:
        print("\n🎉 All tests PASSED!")
        print("   Nagatha is now maintaining conversation context properly.")
        return 0
    else:
        print("\n⚠️  Some tests FAILED!")
        print("   Session context may not be working correctly.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 