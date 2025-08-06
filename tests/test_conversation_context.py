"""
Tests for conversation context preservation across interfaces.

This module tests that conversation context is properly maintained
across different interfaces (CLI, Discord, API) and that session
management works correctly for maintaining conversation history.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest_asyncio

from nagatha_assistant.server.core_server import AgentSessionManager, NagathaUnifiedServer, ServerConfig
from nagatha_assistant.core.memory import MemoryManager


class TestConversationContext:
    """Test cases for conversation context preservation."""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_database(self):
        """Set up test database with tables."""
        from nagatha_assistant.db import engine, Base
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield
        
        # Clean up after tests
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @pytest.fixture
    def session_manager(self):
        """Create a session manager for testing."""
        return AgentSessionManager()
    
    @pytest.mark.asyncio
    async def test_discord_channel_session_consistency(self, session_manager):
        """Test that Discord messages in the same channel use the same session."""
        with patch('nagatha_assistant.server.core_server.start_session', side_effect=[101, 102]):
            
            # First message in channel
            session1 = await session_manager.get_or_create_session(
                user_id="discord:user1",
                interface="discord",
                interface_context={"channel_id": "12345", "guild_id": "67890"}
            )
            
            # Second message in same channel (different user)
            session2 = await session_manager.get_or_create_session(
                user_id="discord:user2", 
                interface="discord",
                interface_context={"channel_id": "12345", "guild_id": "67890"}
            )
            
            # Third message in different channel
            session3 = await session_manager.get_or_create_session(
                user_id="discord:user1",
                interface="discord",
                interface_context={"channel_id": "54321", "guild_id": "67890"}
            )
            
            # Same channel should use same session
            assert session1 == session2
            
            # Different channel should use different session
            assert session1 != session3
    
    @pytest.mark.asyncio
    async def test_cli_user_session_consistency(self, session_manager):
        """Test that CLI sessions are user-specific."""
        with patch('nagatha_assistant.server.core_server.start_session', side_effect=[201, 202]):
            
            # Same user, CLI interface
            session1 = await session_manager.get_or_create_session(
                user_id="user1",
                interface="cli",
                interface_context={}
            )
            
            session2 = await session_manager.get_or_create_session(
                user_id="user1",
                interface="cli", 
                interface_context={}
            )
            
            # Different user, CLI interface
            session3 = await session_manager.get_or_create_session(
                user_id="user2",
                interface="cli",
                interface_context={}
            )
            
            # Same user should reuse session
            assert session1 == session2
            
            # Different user should have different session
            assert session1 != session3
    
    @pytest.mark.asyncio
    async def test_api_session_preservation(self, session_manager):
        """Test that API sessions preserve user context."""
        with patch('nagatha_assistant.server.core_server.start_session', side_effect=[301, 302]):
            
            # API session with user ID
            session1 = await session_manager.get_or_create_session(
                user_id="api_user_123",
                interface="api",
                interface_context={"client": "mobile_app"}
            )
            
            # Same user ID, same interface
            session2 = await session_manager.get_or_create_session(
                user_id="api_user_123",
                interface="api",
                interface_context={"client": "web_app"}
            )
            
            # Different user ID
            session3 = await session_manager.get_or_create_session(
                user_id="api_user_456",
                interface="api",
                interface_context={"client": "mobile_app"}
            )
            
            # Same user should reuse session
            assert session1 == session2
            
            # Different user should have different session
            assert session1 != session3
    
    @pytest.mark.asyncio
    async def test_conversation_context_storage_and_retrieval(self):
        """Test that conversation context is stored and retrieved correctly."""
        from nagatha_assistant.core.agent import send_message, start_session
        from nagatha_assistant.core.memory import get_memory_manager
        
        # Mock OpenAI to return predictable responses
        mock_responses = [
            "Hello! I'm Nagatha, how can I help you?",
            "I remember you mentioned pizza. What else would you like to know?",
            "Your favorite color is blue, as you told me earlier."
        ]
        
        with patch('nagatha_assistant.core.agent.AsyncOpenAI') as mock_openai:
            # Mock OpenAI responses
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            mock_response_objects = []
            for response_text in mock_responses:
                mock_choice = MagicMock()
                mock_choice.message.content = response_text
                mock_response = MagicMock()
                mock_response.choices = [mock_choice]
                mock_response_objects.append(mock_response)
            
            mock_client.chat.completions.create.side_effect = mock_response_objects
            
            # Start a session and send messages
            session_id = await start_session()
            
            # First message
            response1 = await send_message(session_id, "Hello, I'm new here")
            assert response1 == mock_responses[0]
            
            # Second message - should have context from first
            response2 = await send_message(session_id, "My favorite food is pizza")
            assert response2 == mock_responses[1]
            
            # Third message - should have context from both previous
            response3 = await send_message(session_id, "My favorite color is blue")
            assert response3 == mock_responses[2]
            
            # Verify that OpenAI was called with conversation history
            calls = mock_client.chat.completions.create.call_args_list
            
            # Third call should include previous messages in conversation history
            final_call_messages = calls[2][1]['messages']
            
            # Should include system message, previous user messages, and assistant responses
            user_messages = [msg for msg in final_call_messages if msg['role'] == 'user']
            assistant_messages = [msg for msg in final_call_messages if msg['role'] == 'assistant']
            
            # Should have multiple user messages
            assert len(user_messages) >= 2
            assert any("pizza" in msg['content'] for msg in user_messages)
            assert any("blue" in msg['content'] for msg in user_messages)
    
    @pytest.mark.asyncio
    async def test_memory_context_integration(self):
        """Test integration between conversation context and memory system."""
        from nagatha_assistant.core.memory import get_memory_manager
        
        memory_manager = get_memory_manager()
        session_id = 123
        
        # Add conversation context entries
        await memory_manager.add_conversation_context(
            session_id=session_id,
            message_id=1,
            role="user",
            content="My name is Alice"
        )
        
        await memory_manager.add_conversation_context(
            session_id=session_id,
            message_id=2,
            role="assistant", 
            content="Nice to meet you, Alice!"
        )
        
        await memory_manager.add_conversation_context(
            session_id=session_id,
            message_id=3,
            role="user",
            content="What's my name?"
        )
        
        # Retrieve conversation context
        context = await memory_manager.get_conversation_context(session_id, limit=10)
        
        # Should have all three entries
        assert len(context) >= 3
        
        # Check that entries are in correct format
        user_entries = [entry for entry in context if entry['value']['role'] == 'user']
        assistant_entries = [entry for entry in context if entry['value']['role'] == 'assistant']
        
        assert len(user_entries) >= 2
        assert len(assistant_entries) >= 1
        
        # Check content preservation
        name_mention = any("Alice" in entry['value']['content'] for entry in context)
        assert name_mention
    
    @pytest.mark.asyncio
    async def test_cross_interface_session_isolation(self, session_manager):
        """Test that different interfaces maintain separate sessions."""
        with patch('nagatha_assistant.server.core_server.start_session', side_effect=range(401, 410)):
            
            user_id = "test_user"
            
            # CLI session
            cli_session = await session_manager.get_or_create_session(
                user_id=user_id,
                interface="cli",
                interface_context={}
            )
            
            # API session for same user
            api_session = await session_manager.get_or_create_session(
                user_id=user_id,
                interface="api",
                interface_context={}
            )
            
            # Discord session for same user
            discord_session = await session_manager.get_or_create_session(
                user_id=f"discord:{user_id}",
                interface="discord",
                interface_context={"channel_id": "12345"}
            )
            
            # All sessions should be different
            assert cli_session != api_session
            assert cli_session != discord_session
            assert api_session != discord_session
    
    @pytest.mark.asyncio
    async def test_session_cleanup_and_expiration(self, session_manager):
        """Test session cleanup for expired sessions."""
        from datetime import datetime, timedelta
        
        with patch('nagatha_assistant.server.core_server.start_session', side_effect=[501, 502]):
            
            # Create sessions
            session1 = await session_manager.get_or_create_session(
                user_id="user1",
                interface="cli",
                interface_context={}
            )
            
            session2 = await session_manager.get_or_create_session(
                user_id="user2", 
                interface="cli",
                interface_context={}
            )
            
            # Verify sessions exist
            assert str(session1) in session_manager.sessions
            assert str(session2) in session_manager.sessions
            
            # Mock one session as expired (older than 24 hours)
            old_time = (datetime.now() - timedelta(hours=25)).isoformat()
            session_manager.sessions[str(session1)]["last_activity"] = old_time
            
            # Run cleanup
            await session_manager.cleanup_expired_sessions(max_age_hours=24)
            
            # Expired session should be removed
            assert str(session1) not in session_manager.sessions
            
            # Active session should remain
            assert str(session2) in session_manager.sessions


class TestUnifiedServerIntegration:
    """Test unified server integration with session management."""
    
    @pytest.mark.asyncio
    async def test_unified_server_session_creation(self):
        """Test that the unified server creates sessions correctly."""
        config = ServerConfig(host="localhost", port=8080)
        
        with patch('nagatha_assistant.server.core_server.start_session', return_value=601):
            server = NagathaUnifiedServer(config)
            
            # Test Discord message processing
            response = await server.process_message(
                message="Hello from Discord",
                user_id="discord:user123",
                interface="discord", 
                interface_context={"channel_id": "98765"}
            )
            
            # Should have created a session
            assert len(server.session_manager.sessions) == 1
            
            # Session should have correct properties
            session_info = list(server.session_manager.sessions.values())[0]
            assert session_info["user_id"] == "discord:user123"
            assert session_info["interface"] == "discord"
            assert session_info["session_key"] == "discord_channel:98765"
    
    @pytest.mark.asyncio 
    async def test_session_reuse_across_requests(self):
        """Test that subsequent requests reuse the same session."""
        config = ServerConfig(host="localhost", port=8080)
        
        with patch('nagatha_assistant.server.core_server.start_session', return_value=701):
            server = NagathaUnifiedServer(config)
            
            # First message in Discord channel
            await server.process_message(
                message="First message",
                user_id="discord:user456",
                interface="discord",
                interface_context={"channel_id": "11111"}
            )
            
            # Second message in same Discord channel
            await server.process_message(
                message="Second message", 
                user_id="discord:user789",  # Different user, same channel
                interface="discord",
                interface_context={"channel_id": "11111"}  # Same channel
            )
            
            # Should only have one session (reused for same channel)
            assert len(server.session_manager.sessions) == 1
            
            # Session should be updated with latest activity
            session_info = list(server.session_manager.sessions.values())[0]
            assert session_info["session_key"] == "discord_channel:11111"