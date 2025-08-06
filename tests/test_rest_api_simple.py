"""
Simple tests for the REST API endpoints.

This module tests the HTTP REST API functionality using a more straightforward approach.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest_asyncio

from nagatha_assistant.server.api.rest import RESTAPI
from nagatha_assistant.server.core_server import NagathaUnifiedServer, ServerConfig


class MockRequest:
    """Simple mock request for testing."""
    
    def __init__(self, method='GET', path='/', json_data=None, match_info=None):
        self.method = method
        self.path = path
        self._json_data = json_data
        self.match_info = match_info or {}
    
    async def json(self):
        if self._json_data is None:
            raise ValueError("No JSON data")
        return self._json_data


class TestRESTAPISimple:
    """Simplified test cases for the REST API endpoints."""
    
    @pytest.fixture
    def mock_server(self):
        """Create a mock unified server for testing."""
        config = ServerConfig(host="localhost", port=8080)
        server = MagicMock(spec=NagathaUnifiedServer)
        server.config = config
        server.session_manager = MagicMock()
        return server
    
    @pytest.fixture
    def rest_api(self, mock_server):
        """Create a REST API instance for testing."""
        return RESTAPI(mock_server)
    
    @pytest.mark.asyncio
    async def test_health_check(self, rest_api):
        """Test the health check endpoint."""
        request = MockRequest()
        
        response = await rest_api._health_check(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data['status'] == 'healthy'
        assert response_data['service'] == 'nagatha_unified_server'
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, rest_api, mock_server):
        """Test successful message processing."""
        # Mock server response
        mock_server.process_message.return_value = "Hello! How can I help you?"
        
        # Create request with valid data
        request_data = {
            "message": "Hello",
            "user_id": "test_user",
            "interface": "api",
            "interface_context": {"test": "context"}
        }
        request = MockRequest(method='POST', path='/process_message', json_data=request_data)
        
        response = await rest_api._process_message(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data['response'] == "Hello! How can I help you?"
        
        # Verify server was called with correct parameters
        mock_server.process_message.assert_called_once_with(
            message="Hello",
            user_id="test_user",
            interface="api",
            interface_context={"test": "context"}
        )
    
    @pytest.mark.asyncio
    async def test_process_message_missing_fields(self, rest_api):
        """Test message processing with missing required fields."""
        # Missing message field
        request_data = {"user_id": "test_user"}
        request = MockRequest(method='POST', path='/process_message', json_data=request_data)
        
        response = await rest_api._process_message(request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert "Missing required fields" in response_data['error']
    
    @pytest.mark.asyncio
    async def test_create_session(self, rest_api, mock_server):
        """Test session creation endpoint."""
        # Mock session manager response (needs to be awaitable)
        mock_server.session_manager.get_or_create_session = AsyncMock(return_value=123)
        
        request_data = {
            "user_id": "test_user",
            "interface": "discord",
            "interface_context": {"channel_id": "12345"}
        }
        request = MockRequest(method='POST', path='/sessions', json_data=request_data)
        
        response = await rest_api._create_session(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data['session_id'] == 123
        
        # Verify session manager was called correctly
        mock_server.session_manager.get_or_create_session.assert_called_once_with(
            user_id="test_user",
            interface="discord",
            interface_context={"channel_id": "12345"}
        )
    
    @pytest.mark.asyncio
    async def test_get_session_found(self, rest_api, mock_server):
        """Test getting session information when session exists."""
        # Mock session info
        session_info = {
            "session_id": 123,
            "user_id": "test_user",
            "interface": "discord",
            "status": "active"
        }
        mock_server.get_session_info.return_value = session_info
        
        request = MockRequest(method='GET', path='/sessions/123', match_info={'session_id': '123'})
        
        response = await rest_api._get_session(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data == session_info
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, rest_api, mock_server):
        """Test getting session information when session doesn't exist."""
        mock_server.get_session_info.return_value = None
        
        request = MockRequest(method='GET', path='/sessions/999', match_info={'session_id': '999'})
        
        response = await rest_api._get_session(request)
        
        assert response.status == 404
        response_data = json.loads(response.text)
        assert "Session not found" in response_data['error']
    
    @pytest.mark.asyncio
    async def test_send_message_to_session(self, rest_api, mock_server):
        """Test sending a message to a specific session."""
        # Mock session info with session_key
        session_info = {
            "session_id": 123,
            "user_id": "test_user",
            "interface": "discord",
            "session_key": "discord_channel:12345",
            "interface_context": {"channel_id": "12345"}
        }
        mock_server.get_session_info.return_value = session_info
        mock_server.process_message.return_value = "Response from session"
        
        request_data = {"message": "Hello from session"}
        request = MockRequest(
            method='POST', 
            path='/sessions/123/messages', 
            json_data=request_data,
            match_info={'session_id': '123'}
        )
        
        response = await rest_api._send_message(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data['response'] == "Response from session"
        
        # Verify the session key was preserved as user_id (this is the key fix!)
        mock_server.process_message.assert_called_once_with(
            message="Hello from session",
            user_id="discord_channel:12345",  # Should use session_key, not original user_id
            interface="discord",
            interface_context={"channel_id": "12345"}
        )
    
    @pytest.mark.asyncio
    async def test_send_message_missing_message(self, rest_api):
        """Test sending message with missing message field."""
        request_data = {}
        request = MockRequest(
            method='POST', 
            path='/sessions/123/messages', 
            json_data=request_data,
            match_info={'session_id': '123'}
        )
        
        response = await rest_api._send_message(request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert "Missing required field: message" in response_data['error']
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, rest_api, mock_server):
        """Test listing active sessions."""
        # Mock sessions list
        sessions = [
            {"session_id": 123, "user_id": "user1", "interface": "discord"},
            {"session_id": 124, "user_id": "user2", "interface": "api"}
        ]
        mock_server.list_active_sessions.return_value = sessions
        
        request = MockRequest(method='GET', path='/sessions')
        
        response = await rest_api._list_sessions(request)
        
        assert response.status == 200
        response_data = json.loads(response.text)
        assert response_data['sessions'] == sessions
    
    @pytest.mark.asyncio
    async def test_server_error_handling(self, rest_api, mock_server):
        """Test error handling when server throws an exception."""
        mock_server.process_message.side_effect = Exception("Server error")
        
        request_data = {
            "message": "Hello",
            "user_id": "test_user"
        }
        request = MockRequest(method='POST', path='/process_message', json_data=request_data)
        
        response = await rest_api._process_message(request)
        
        assert response.status == 500
        response_data = json.loads(response.text)
        assert "Server error" in response_data['error']


class TestDiscordSessionKeyFix:
    """Tests specifically for the Discord session key preservation fix."""
    
    @pytest.fixture
    def mock_server(self):
        """Create a mock unified server for testing."""
        config = ServerConfig(host="localhost", port=8080)
        server = MagicMock(spec=NagathaUnifiedServer)
        server.config = config
        return server
    
    @pytest.fixture
    def rest_api(self, mock_server):
        """Create a REST API instance for testing."""
        return RESTAPI(mock_server)
    
    @pytest.mark.asyncio
    async def test_discord_session_key_preservation(self, rest_api, mock_server):
        """Test that Discord session keys are preserved correctly."""
        # This is the core test for the bug fix we implemented
        
        # Mock session info that represents a Discord channel session
        session_info = {
            "session_id": 160,
            "user_id": "discord:12345",  # Original user ID
            "interface": "discord",
            "session_key": "discord_channel:67890",  # Channel-based session key
            "interface_context": {
                "channel_id": "67890",
                "guild_id": "11111"
            }
        }
        mock_server.get_session_info.return_value = session_info
        mock_server.process_message.return_value = "I remember our conversation!"
        
        # Send a message to the session
        request_data = {"message": "Do you remember what we talked about?"}
        request = MockRequest(
            method='POST',
            path='/sessions/160/messages',
            json_data=request_data,
            match_info={'session_id': '160'}
        )
        
        response = await rest_api._send_message(request)
        
        # Verify successful response
        assert response.status == 200
        
        # THE KEY TEST: Verify that the session_key was used as user_id
        # This ensures that all messages in the same Discord channel use the same session
        mock_server.process_message.assert_called_once_with(
            message="Do you remember what we talked about?",
            user_id="discord_channel:67890",  # Should be session_key, not original user_id
            interface="discord",
            interface_context={
                "channel_id": "67890",
                "guild_id": "11111"
            }
        )
    
    @pytest.mark.asyncio
    async def test_fallback_to_user_id_when_no_session_key(self, rest_api, mock_server):
        """Test fallback to user_id when session_key is not available."""
        # Mock session info without session_key (legacy sessions)
        session_info = {
            "session_id": 150,
            "user_id": "api_user_123",
            "interface": "api",
            "interface_context": {"client": "mobile"}
        }
        mock_server.get_session_info.return_value = session_info
        mock_server.process_message.return_value = "Response"
        
        request_data = {"message": "Test message"}
        request = MockRequest(
            method='POST',
            path='/sessions/150/messages',
            json_data=request_data,
            match_info={'session_id': '150'}
        )
        
        response = await rest_api._send_message(request)
        
        assert response.status == 200
        
        # Should fall back to user_id when session_key is not present
        mock_server.process_message.assert_called_once_with(
            message="Test message",
            user_id="api_user_123",  # Should use user_id as fallback
            interface="api",
            interface_context={"client": "mobile"}
        )