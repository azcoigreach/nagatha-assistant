#!/usr/bin/env python3
"""
Test script for the unified server implementation.

This script tests the core functionality of the unified server without
requiring the full API layer to be implemented.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from nagatha_assistant.server.core_server import NagathaUnifiedServer, ServerConfig
from nagatha_assistant.utils.logger import setup_logger_with_env_control


async def test_session_management():
    """Test session management functionality."""
    print("Testing session management...")
    
    # Create server instance
    config = ServerConfig(
        enable_websocket=False,
        enable_rest=False,
        enable_events=False
    )
    server = NagathaUnifiedServer(config)
    
    try:
        # Start server
        await server._initialize_core_components()
        await server._start_unified_components()
        
        # Test session creation
        session_id1 = await server.session_manager.get_or_create_session(
            user_id="test_user_1",
            interface="cli",
            interface_context={"terminal": "xterm"}
        )
        print(f"Created session 1: {session_id1}")
        
        # Test joining existing session
        session_id2 = await server.session_manager.get_or_create_session(
            user_id="test_user_1",
            interface="discord",
            interface_context={"guild_id": "123456"}
        )
        print(f"Joined session 2: {session_id2}")
        
        # Verify sessions are the same
        assert session_id1 == session_id2, "Sessions should be the same for same user"
        print("✓ Session joining works correctly")
        
        # Test different user gets different session
        session_id3 = await server.session_manager.get_or_create_session(
            user_id="test_user_2",
            interface="cli"
        )
        print(f"Created session 3: {session_id3}")
        assert session_id1 != session_id3, "Different users should have different sessions"
        print("✓ Different users get different sessions")
        
        # Test session info
        session_info = await server.get_session_info(session_id1)
        print(f"Session info: {session_info['session']['interfaces']}")
        assert "cli" in session_info['session']['interfaces']
        assert "discord" in session_info['session']['interfaces']
        print("✓ Session info contains all interfaces")
        
        # Test session stats
        stats = await server.session_manager.get_session_stats()
        print(f"Session stats: {stats}")
        assert stats['total_sessions'] >= 2
        assert stats['total_users'] >= 2
        print("✓ Session statistics work correctly")
        
        # Test message processing
        response = await server.process_message(
            message="Hello, this is a test message",
            user_id="test_user_1",
            interface="cli"
        )
        print(f"Message response: {response[:100]}...")
        print("✓ Message processing works")
        
        # Test server status
        status = await server.get_server_status()
        print(f"Server status: {status['server']['running']}")
        assert status['server']['total_requests'] >= 1
        print("✓ Server status works correctly")
        
        print("🎉 All session management tests passed!")
        
    finally:
        # Clean up
        await server._stop_unified_components()
        print("Server components stopped")


async def test_connection_pool():
    """Test connection pool functionality."""
    print("\nTesting connection pool...")
    
    from nagatha_assistant.server.core.connection_pool import SharedMCPConnectionPool
    
    # Create connection pool
    pool = SharedMCPConnectionPool(max_connections_per_server=2)
    
    try:
        # Start pool
        await pool.start()
        
        # Test connection creation
        conn1 = await pool.get_connection("test_server", "session_1")
        print(f"Created connection 1: {conn1}")
        assert conn1 is not None
        
        # Test connection reuse
        conn2 = await pool.get_connection("test_server", "session_2")
        print(f"Created connection 2: {conn2}")
        assert conn2 is not None
        assert conn1 != conn2
        
        # Test connection limit
        conn3 = await pool.get_connection("test_server", "session_3")
        print(f"Connection 3 result: {conn3}")
        # Should return None since we're at the limit
        
        # Test connection release
        await pool.release_connection(conn1, "session_1", success=True)
        print("Released connection 1")
        
        # Now we should be able to get a new connection
        conn4 = await pool.get_connection("test_server", "session_4")
        print(f"Created connection 4: {conn4}")
        assert conn4 is not None
        
        # Test tool calling
        result = await pool.call_tool_shared(
            "test_server",
            "test_tool",
            {"param": "value"},
            "session_1"
        )
        print(f"Tool call result: {result}")
        assert "result" in result
        print("✓ Tool calling works")
        
        # Test statistics
        stats = pool.get_connection_stats()
        print(f"Connection stats: {stats}")
        assert stats['total_connections'] >= 2
        print("✓ Connection statistics work")
        
        # Test usage statistics
        usage_stats = pool.get_usage_stats("session_1")
        print(f"Usage stats: {usage_stats}")
        assert "test_server" in usage_stats
        print("✓ Usage statistics work")
        
        print("🎉 All connection pool tests passed!")
        
    finally:
        # Clean up
        await pool.stop()
        print("Connection pool stopped")


async def main():
    """Run all tests."""
    print("🧪 Testing Nagatha Unified Server")
    print("=" * 50)
    
    # Set up logging
    os.environ["LOG_LEVEL"] = "INFO"
    logger = setup_logger_with_env_control()
    
    try:
        # Test session management
        await test_session_management()
        
        # Test connection pool
        await test_connection_pool()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! The unified server foundation is working correctly.")
        print("\nNext steps:")
        print("1. Transform CLI interface to connect to unified server")
        print("2. Transform Discord bot to connect to unified server")
        print("3. Add new CLI commands for server management")
        print("4. Implement actual API components (WebSocket, REST, Events)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 