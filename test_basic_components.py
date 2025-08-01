#!/usr/bin/env python3
"""
Basic test for the unified server components.

This script tests the basic functionality without requiring external dependencies.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from nagatha_assistant.server.core.session_manager import SessionContext, UnifiedSessionManager
from nagatha_assistant.server.core.connection_pool import ConnectionInfo, ConnectionState, SharedMCPConnectionPool


async def test_session_context():
    """Test SessionContext class."""
    print("Testing SessionContext...")
    
    # Create session context
    session = SessionContext(
        session_id="test_session",
        user_id="test_user",
        created_at=datetime.now(),
        last_activity=datetime.now()
    )
    
    # Test interface management
    session.add_interface("cli", {"terminal": "xterm"})
    session.add_interface("discord", {"guild_id": "123456"})
    
    assert "cli" in session.interfaces
    assert "discord" in session.interfaces
    assert len(session.interfaces) == 2
    assert not session.is_empty()
    
    # Test interface removal
    session.remove_interface("cli")
    assert "cli" not in session.interfaces
    assert "discord" in session.interfaces
    
    session.remove_interface("discord")
    assert session.is_empty()
    
    # Test serialization
    session_dict = session.to_dict()
    assert session_dict["session_id"] == "test_session"
    assert session_dict["user_id"] == "test_user"
    
    print("✓ SessionContext tests passed!")


async def test_connection_info():
    """Test ConnectionInfo class."""
    print("Testing ConnectionInfo...")
    
    # Create connection info
    conn = ConnectionInfo(
        server_name="test_server",
        connection_id="test_conn",
        state=ConnectionState.IDLE,
        created_at=datetime.now(),
        last_used=datetime.now()
    )
    
    # Test state changes
    assert conn.state == ConnectionState.IDLE
    
    conn.mark_used()
    assert conn.state == ConnectionState.BUSY
    assert conn.use_count == 1
    
    conn.mark_idle()
    assert conn.state == ConnectionState.IDLE
    
    conn.mark_error("Test error")
    assert conn.state == ConnectionState.ERROR
    assert conn.error_count == 1
    assert conn.last_error == "Test error"
    
    # Test serialization
    conn_dict = conn.to_dict()
    assert conn_dict["server_name"] == "test_server"
    assert conn_dict["connection_id"] == "test_conn"
    
    print("✓ ConnectionInfo tests passed!")


async def test_session_manager_basic():
    """Test basic session manager functionality without dependencies."""
    print("Testing SessionManager basic functionality...")
    
    # Create session manager
    session_manager = UnifiedSessionManager()
    
    # Test session ID generation
    session_id1 = session_manager._generate_session_id()
    session_id2 = session_manager._generate_session_id()
    
    assert session_id1 != session_id2
    assert session_id1.startswith("session_")
    assert len(session_id1) > 10
    
    print("✓ SessionManager basic tests passed!")


async def test_connection_pool_basic():
    """Test basic connection pool functionality without dependencies."""
    print("Testing ConnectionPool basic functionality...")
    
    # Create connection pool
    pool = SharedMCPConnectionPool(max_connections_per_server=2)
    
    # Test connection creation logic
    assert pool._can_create_connection("test_server") == True
    
    # Simulate adding connections
    pool.connections["test_server"] = [None, None]  # 2 connections
    assert pool._can_create_connection("test_server") == False
    
    pool.connections["test_server"] = [None]  # 1 connection
    assert pool._can_create_connection("test_server") == True
    
    print("✓ ConnectionPool basic tests passed!")


async def main():
    """Run all basic tests."""
    print("🧪 Testing Basic Unified Server Components")
    print("=" * 50)
    
    try:
        # Test basic components
        await test_session_context()
        await test_connection_info()
        await test_session_manager_basic()
        await test_connection_pool_basic()
        
        print("\n" + "=" * 50)
        print("✅ All basic component tests passed!")
        print("\nThe core data structures and logic are working correctly.")
        print("Next: Test with actual dependencies (memory, MCP, etc.)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 