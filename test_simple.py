#!/usr/bin/env python3
"""
Very simple test for the unified server components.
"""

from datetime import datetime
from nagatha_assistant.server.core.session_manager import SessionContext
from nagatha_assistant.server.core.connection_pool import ConnectionInfo, ConnectionState

def test_session_context():
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
    
    print("✓ SessionContext tests passed!")

def test_connection_info():
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
    
    print("✓ ConnectionInfo tests passed!")

def main():
    """Run all tests."""
    print("🧪 Testing Basic Components")
    print("=" * 30)
    
    try:
        test_session_context()
        test_connection_info()
        
        print("\n" + "=" * 30)
        print("✅ All basic tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 