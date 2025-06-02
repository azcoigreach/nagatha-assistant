#!/usr/bin/env python3
"""
Pytest tests for the agent module functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from nagatha_assistant.core import agent
from nagatha_assistant.db_models import ConversationSession, Message


@pytest.mark.asyncio
class TestAgent:
    """Test cases for the agent module."""

    async def test_startup_and_shutdown(self):
        """Test agent startup and shutdown cycle."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.initialize = AsyncMock()
            mock_manager.get_initialization_summary.return_value = {
                'connected': 1,
                'total_configured': 1,
                'total_tools': 5,
                'connected_servers': ['test_server'],
                'failed': 0,
                'failed_servers': []
            }
            mock_get_manager.return_value = mock_manager
            
            # Test startup
            result = await agent.startup()
            assert isinstance(result, dict)
            assert 'connected' in result
            assert 'total_tools' in result
            
            # Test shutdown
            with patch('nagatha_assistant.core.agent.shutdown_mcp_manager') as mock_shutdown:
                mock_shutdown.return_value = AsyncMock()
                await agent.shutdown()
                mock_shutdown.assert_called_once()

    async def test_startup_failure(self):
        """Test agent startup when initialization fails."""
        with patch('nagatha_assistant.core.agent.mcp_manager') as mock_manager:
            mock_manager.initialize = AsyncMock(side_effect=Exception("Init failed"))
            
            with pytest.raises(Exception, match="Init failed"):
                await agent.startup()

    async def test_get_mcp_status(self):
        """Test getting MCP status information."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager._initialized = True
            mock_manager.get_server_info.return_value = {'test_server': {'connected': True}}
            mock_manager.get_available_tools.return_value = [
                {'name': 'test_tool', 'server': 'test_server', 'description': 'Test tool'}
            ]
            mock_get_manager.return_value = mock_manager
            
            status = await agent.get_mcp_status()
            assert status['initialized'] is True
            assert 'servers' in status
            assert 'tools' in status

    async def test_get_mcp_status_not_initialized(self):
        """Test MCP status when not initialized."""
        with patch('nagatha_assistant.core.agent.mcp_manager') as mock_manager:
            mock_manager._initialized = False
            
            status = await agent.get_mcp_status()
            assert status['initialized'] is False
            assert 'servers' in status
            assert 'tools' in status

    async def test_get_mcp_status_error_handling(self):
        """Test MCP status error handling."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_server_info.side_effect = Exception("Test error")
            mock_get_manager.return_value = mock_manager
            
            status = await agent.get_mcp_status()
            assert 'error' in status
            assert status['initialized'] is False

    def test_register_push_callback(self):
        """Test registering push callbacks."""
        # Clear any existing callbacks
        agent._push_callbacks.clear()
        
        callback = MagicMock()
        session_id = 123
        
        agent.register_push_callback(session_id, callback)
        
        # Verify callback is registered
        assert session_id in agent._push_callbacks
        assert callback in agent._push_callbacks[session_id]

    def test_register_multiple_callbacks(self):
        """Test registering multiple callbacks for same session."""
        agent._push_callbacks.clear()
        
        callback1 = MagicMock()
        callback2 = MagicMock()
        session_id = 123
        
        agent.register_push_callback(session_id, callback1)
        agent.register_push_callback(session_id, callback2)
        
        # Should have both callbacks
        assert len(agent._push_callbacks[session_id]) == 2
        assert callback1 in agent._push_callbacks[session_id]
        assert callback2 in agent._push_callbacks[session_id]

    async def test_push_message(self):
        """Test pushing messages to callbacks."""
        agent._push_callbacks.clear()
        
        callback = AsyncMock()
        session_id = 123
        message = "Test message"
        
        # Register callback
        agent.register_push_callback(session_id, callback)
        
        # Push message
        await agent.push_message(session_id, message)
        
        # Verify callback was called
        callback.assert_called_once_with(message)

    async def test_push_message_multiple_callbacks(self):
        """Test pushing message to multiple callbacks."""
        agent._push_callbacks.clear()
        
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        session_id = 123
        message = "Test message"
        
        # Register callbacks
        agent.register_push_callback(session_id, callback1)
        agent.register_push_callback(session_id, callback2)
        
        # Push message
        await agent.push_message(session_id, message)
        
        # Verify both callbacks were called
        callback1.assert_called_once_with(message)
        callback2.assert_called_once_with(message)

    async def test_push_message_callback_error(self):
        """Test pushing message when callback raises error."""
        agent._push_callbacks.clear()
        
        callback = AsyncMock(side_effect=Exception("Callback error"))
        session_id = 123
        message = "Test message"
        
        # Register callback
        agent.register_push_callback(session_id, callback)
        
        # Should not raise an error
        await agent.push_message(session_id, message)

    async def test_push_message_no_callbacks(self):
        """Test pushing message when no callbacks are registered."""
        agent._push_callbacks.clear()
        
        # Should not raise an error
        await agent.push_message(999, "Test message")

    def test_get_startup_message(self):
        """Test getting startup message."""
        summary = {
            'connected': 2,
            'total_configured': 3,
            'total_tools': 10,
            'connected_servers': ['server1', 'server2'],
            'failed': 1,
            'failed_servers': [('server3', 'Connection failed')]
        }
        
        message = agent.get_startup_message(summary)
        assert "Connected to 2/3 MCP servers" in message
        assert "10 tools available" in message
        assert "server1, server2" in message
        assert "server3: Connection failed" in message

    def test_get_startup_message_no_servers(self):
        """Test startup message when no servers are connected."""
        summary = {
            'connected': 0,
            'total_configured': 0,
            'total_tools': 0,
            'connected_servers': [],
            'failed': 0,
            'failed_servers': []
        }
        
        message = agent.get_startup_message(summary)
        assert "No MCP servers connected" in message

    def test_get_startup_message_all_failed(self):
        """Test startup message when all servers failed."""
        summary = {
            'connected': 0,
            'total_configured': 2,
            'total_tools': 0,
            'connected_servers': [],
            'failed': 2,
            'failed_servers': [('server1', 'Error 1'), ('server2', 'Error 2')]
        }
        
        message = agent.get_startup_message(summary)
        assert "Connected to 0/2 MCP servers" in message
        assert "server1: Error 1" in message
        assert "server2: Error 2" in message

    @patch('nagatha_assistant.core.agent.client')
    async def test_chat_with_user_simple(self, mock_client):
        """Test simple chat without tool calls."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_status:
            mock_status.return_value = {'tools': [], 'initialized': True}
            
            result = await agent.chat_with_user(1, "Hello")
            
            assert result == "Hello! How can I help you?"
            mock_client.chat.completions.create.assert_called_once()

    @patch('nagatha_assistant.core.agent.client')
    @patch('nagatha_assistant.core.agent.mcp_manager')
    async def test_chat_with_user_tool_call(self, mock_manager, mock_client):
        """Test chat with tool call."""
        # Mock tool call response
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"param": "value"}'
        
        # First response with tool call
        mock_response1 = MagicMock()
        mock_response1.choices = [MagicMock()]
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage.prompt_tokens = 10
        mock_response1.usage.completion_tokens = 5
        
        # Second response after tool call
        mock_response2 = MagicMock()
        mock_response2.choices = [MagicMock()]
        mock_response2.choices[0].message.content = "Tool result processed"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage.prompt_tokens = 15
        mock_response2.usage.completion_tokens = 8
        
        mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response1, mock_response2])
        mock_manager.call_tool = AsyncMock(return_value={"result": "success"})
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_status:
            mock_status.return_value = {
                'tools': [{'name': 'test_tool', 'description': 'Test tool'}],
                'initialized': True
            }
            
            result = await agent.chat_with_user(1, "Use the test tool")
            
            assert result == "Tool result processed"
            assert mock_client.chat.completions.create.call_count == 2
            mock_manager.call_tool.assert_called_once_with("test_tool", {"param": "value"})

    @patch('nagatha_assistant.core.agent.client')
    async def test_chat_with_user_error_handling(self, mock_client):
        """Test chat error handling."""
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_status:
            mock_status.return_value = {'tools': [], 'initialized': True}
            
            result = await agent.chat_with_user(1, "Hello")
            
            assert "I encountered an error" in result
            assert "API Error" in result

    @patch('nagatha_assistant.core.agent.client')
    @patch('nagatha_assistant.core.agent.mcp_manager')
    async def test_chat_with_tool_call_error(self, mock_manager, mock_client):
        """Test chat when tool call fails."""
        # Mock tool call response
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "failing_tool"
        mock_tool_call.function.arguments = '{"param": "value"}'
        
        # First response with tool call
        mock_response1 = MagicMock()
        mock_response1.choices = [MagicMock()]
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage.prompt_tokens = 10
        mock_response1.usage.completion_tokens = 5
        
        # Second response after tool error
        mock_response2 = MagicMock()
        mock_response2.choices = [MagicMock()]
        mock_response2.choices[0].message.content = "I encountered an error with the tool"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage.prompt_tokens = 15
        mock_response2.usage.completion_tokens = 8
        
        mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response1, mock_response2])
        mock_manager.call_tool = AsyncMock(side_effect=Exception("Tool error"))
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_status:
            mock_status.return_value = {
                'tools': [{'name': 'failing_tool', 'description': 'Failing tool'}],
                'initialized': True
            }
            
            result = await agent.chat_with_user(1, "Use the failing tool")
            
            assert result == "I encountered an error with the tool"
            assert mock_client.chat.completions.create.call_count == 2

    @patch('nagatha_assistant.core.agent.client')
    async def test_chat_with_invalid_tool_args(self, mock_client):
        """Test chat with invalid tool arguments."""
        # Mock tool call with invalid JSON
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = 'invalid json'
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_status:
            mock_status.return_value = {
                'tools': [{'name': 'test_tool', 'description': 'Test tool'}],
                'initialized': True
            }
            
            result = await agent.chat_with_user(1, "Use test tool")
            
            # Should handle JSON decode error gracefully
            assert "error" in result.lower()

    @patch('nagatha_assistant.core.agent.usage_tracker')
    @patch('nagatha_assistant.core.agent.client')
    async def test_usage_tracking(self, mock_client, mock_tracker):
        """Test that usage is tracked correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.model = "gpt-4"
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_status:
            mock_status.return_value = {'tools': [], 'initialized': True}
            
            await agent.chat_with_user(1, "Hello")
            
            # Should track usage
            mock_tracker.record_usage.assert_called_once_with("gpt-4", 100, 50)

    def test_push_message_function_exists(self):
        """Test that push_message function exists."""
        assert hasattr(agent, 'push_message')
        assert callable(agent.push_message)

    async def test_push_message_basic(self):
        """Test pushing a basic message."""
        # Test that the function can be called without error
        await agent.push_message(123, "test message")

    def test_subscribe_unsubscribe_session(self):
        """Test session subscription functions."""
        callback = MagicMock()
        session_id = 123
        
        # Test subscribe
        agent.subscribe_session(session_id, callback)
        
        # Test unsubscribe  
        agent.unsubscribe_session(session_id, callback)

    async def test_start_session(self):
        """Test starting a new session."""
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_conversation = MagicMock()
            mock_conversation.id = 1
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            
            with patch('nagatha_assistant.core.agent.ConversationSession') as mock_conv_class:
                mock_conv_class.return_value = mock_conversation
                
                session_id = await agent.start_session()
                assert session_id == 1

    async def test_get_messages(self):
        """Test getting messages for a session."""
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_messages = [MagicMock(), MagicMock()]
            mock_query = MagicMock()
            mock_query.filter.return_value.order_by.return_value.all = AsyncMock(return_value=mock_messages)
            mock_session.execute = AsyncMock(return_value=mock_query)
            
            messages = await agent.get_messages(1)
            assert len(messages) == 2

    async def test_send_message(self):
        """Test sending a message."""
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            
            # Mock the actual chat functionality
            with patch('nagatha_assistant.core.agent.client') as mock_client:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Response"
                mock_response.choices[0].message.tool_calls = None
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 5
                mock_response.model = "gpt-4"
                
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                
                with patch('nagatha_assistant.core.agent.Message') as mock_message_class:
                    mock_message_class.return_value = MagicMock()
                    
                    response = await agent.send_message(1, "Hello")
                    assert response == "Response"

    async def test_call_mcp_tool(self):
        """Test calling an MCP tool."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.call_tool = AsyncMock(return_value={"result": "success"})
            mock_get_manager.return_value = mock_manager
            
            result = await agent.call_mcp_tool("test_tool", {"param": "value"})
            assert result == {"result": "success"}

    async def test_get_available_tools(self):
        """Test getting available tools."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_available_tools.return_value = [
                {'name': 'test_tool', 'description': 'Test tool'}
            ]
            mock_get_manager.return_value = mock_manager
            
            tools = await agent.get_available_tools()
            assert len(tools) == 1
            assert tools[0]['name'] == 'test_tool'

    async def test_list_sessions(self):
        """Test listing sessions."""
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_sessions = [MagicMock(), MagicMock()]
            mock_query = MagicMock()
            mock_query.order_by.return_value.all = AsyncMock(return_value=mock_sessions)
            mock_session.execute = AsyncMock(return_value=mock_query)
            
            sessions = await agent.list_sessions()
            assert len(sessions) == 2

    def test_format_mcp_status_for_chat(self):
        """Test formatting MCP status for chat."""
        status = {
            'initialized': True,
            'servers': {'test_server': {'connected': True}},
            'tools': [{'name': 'test_tool', 'server': 'test_server'}]
        }
        
        formatted = agent.format_mcp_status_for_chat(status)
        assert isinstance(formatted, str)
        assert 'test_server' in formatted
        assert 'test_tool' in formatted

    def test_get_system_prompt(self):
        """Test getting system prompt."""
        tools = [{'name': 'test_tool', 'description': 'Test tool'}]
        prompt = agent.get_system_prompt(tools)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch('nagatha_assistant.core.agent.record_usage')
    def test_record_usage_integration(self, mock_record):
        """Test that usage recording is integrated."""
        agent.record_usage("gpt-4", 100, 50)
        mock_record.assert_called_once_with("gpt-4", 100, 50)

    async def test_shutdown_mcp_manager(self):
        """Test shutting down MCP manager."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.shutdown = AsyncMock()
            mock_get_manager.return_value = mock_manager
            
            await agent.shutdown_mcp_manager()
            mock_manager.shutdown.assert_called_once()

    async def test_push_system_message(self):
        """Test pushing a system message."""
        # Should not raise an error
        await agent.push_system_message(123, "System message")

    def test_agent_module_constants(self):
        """Test that agent module has expected constants and imports."""
        assert hasattr(agent, 'CONVERSATION_TIMEOUT')
        assert hasattr(agent, '_push_callbacks')
        assert hasattr(agent, 'client') 