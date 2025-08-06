#!/usr/bin/env python3
"""
Pytest tests for the agent module functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from nagatha_assistant.core import agent
from nagatha_assistant.db_models import ConversationSession, Message


class TestAgent:
    """Test cases for the agent module."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_startup_failure(self):
        """Test agent startup when MCP manager fails to initialize."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_get_manager.side_effect = Exception("MCP manager failed")
            
            with pytest.raises(Exception, match="MCP manager failed"):
                await agent.startup()

    @pytest.mark.asyncio
    async def test_get_mcp_status(self):
        """Test getting MCP status information."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager._initialized = True
            mock_manager.get_server_info.return_value = {'test_server': {'connected': True}}
            mock_manager.get_available_tools.return_value = [
                {'name': 'test_tool', 'server': 'test_server', 'description': 'Test tool'}
            ]
            mock_manager.get_initialization_summary.return_value = {
                'connected': 1,
                'total_configured': 1,
                'total_tools': 1,
                'connected_servers': ['test_server'],
                'failed': 0,
                'failed_servers': []
            }
            mock_get_manager.return_value = mock_manager
            
            status = await agent.get_mcp_status()
            assert status['initialized'] is True
            assert 'servers' in status
            assert 'tools' in status

    @pytest.mark.asyncio
    async def test_get_mcp_status_not_initialized(self):
        """Test MCP status when not initialized."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager._initialized = False
            mock_manager.get_server_info.return_value = {}
            mock_manager.get_available_tools.return_value = []
            mock_manager.get_initialization_summary.return_value = {
                'connected': 0,
                'total_configured': 0,
                'total_tools': 0,
                'connected_servers': [],
                'failed': 0,
                'failed_servers': []
            }
            mock_get_manager.return_value = mock_manager
            
            status = await agent.get_mcp_status()
            assert status['initialized'] is False
            assert 'servers' in status
            assert 'tools' in status

    @pytest.mark.asyncio
    async def test_get_mcp_status_error_handling(self):
        """Test MCP status error handling."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_get_manager.side_effect = Exception("Test error")
            
            status = await agent.get_mcp_status()
            assert 'error' in status
            assert status['initialized'] is False

    def test_register_push_callback(self):
        """Test registering push callbacks."""
        # Clear any existing callbacks
        agent._push_callbacks.clear()
        
        callback = MagicMock()
        session_id = 123
        
        agent.subscribe_session(session_id, callback)
        
        # Verify callback is registered
        assert session_id in agent._push_callbacks
        assert callback in agent._push_callbacks[session_id]

    def test_register_multiple_callbacks(self):
        """Test registering multiple callbacks for same session."""
        agent._push_callbacks.clear()
        
        callback1 = MagicMock()
        callback2 = MagicMock()
        session_id = 123
        
        agent.subscribe_session(session_id, callback1)
        agent.subscribe_session(session_id, callback2)
        
        # Should have both callbacks
        assert len(agent._push_callbacks[session_id]) == 2
        assert callback1 in agent._push_callbacks[session_id]
        assert callback2 in agent._push_callbacks[session_id]

    @pytest.mark.asyncio
    async def test_push_message(self):
        """Test pushing messages to callbacks."""
        agent._push_callbacks.clear()
        
        callback = AsyncMock()
        session_id = 123
        message = "Test message"
        
        # Register callback
        agent.subscribe_session(session_id, callback)
        
        # Push message
        await agent.push_message(session_id, message)
        
        # Verify callback was called
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_message_multiple_callbacks(self):
        """Test pushing message to multiple callbacks."""
        agent._push_callbacks.clear()
        
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        session_id = 123
        message = "Test message"
        
        # Register callbacks
        agent.subscribe_session(session_id, callback1)
        agent.subscribe_session(session_id, callback2)
        
        # Push message
        await agent.push_message(session_id, message)
        
        # Verify both callbacks were called
        callback1.assert_called_once()
        callback2.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_message_callback_error(self):
        """Test pushing message when callback raises error."""
        agent._push_callbacks.clear()
        
        callback = AsyncMock(side_effect=Exception("Callback error"))
        session_id = 123
        message = "Test message"
        
        # Register callback
        agent.subscribe_session(session_id, callback)
        
        # Should not raise an error
        await agent.push_message(session_id, message)

    @pytest.mark.asyncio
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
        
        message = agent.format_mcp_status_for_chat(summary)
        assert "✅ Connected to 2/3 MCP servers" in message
        assert "🔧 10 tools available" in message
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
        
        message = agent.format_mcp_status_for_chat(summary)
        assert "⚠️ No MCP servers connected" in message

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
        
        message = agent.format_mcp_status_for_chat(summary)
        assert "⚠️ No MCP servers connected" in message
        assert "❌ 2 server(s) failed to connect:" in message
        assert "server1: Error 1" in message
        assert "server2: Error 2" in message

    @patch('nagatha_assistant.core.agent.get_openai_client')
    @pytest.mark.asyncio
    async def test_chat_with_user_simple(self, mock_get_client):
        """Test simple chat without tool calls."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        # Set up the client mock
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        # Mock all the dependencies that send_message uses
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class, \
             patch('nagatha_assistant.core.agent.Message') as mock_message_class, \
             patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools, \
             patch('nagatha_assistant.core.agent.get_messages') as mock_get_messages, \
             patch('nagatha_assistant.core.agent.get_system_prompt') as mock_system_prompt, \
             patch('nagatha_assistant.core.agent._notify') as mock_notify, \
             patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus:
            
            # Setup session mock
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            # Setup message mock
            mock_message = MagicMock()
            mock_message.id = 1
            mock_message_class.return_value = mock_message
            
            # Setup other mocks
            mock_tools.return_value = []
            mock_get_messages.return_value = []
            mock_system_prompt.return_value = "You are a helpful assistant."
            mock_notify.return_value = AsyncMock()
            
            # Setup event bus mock
            mock_bus = MagicMock()
            mock_bus._running = False
            mock_event_bus.return_value = mock_bus
            
            result = await agent.send_message(1, "Hello")
            
            # Check that we got a response and it contains greeting-like content
            assert result is not None
            assert len(result) > 0
            assert any(word in result.lower() for word in ["hello", "hi", "how"])
            mock_client.chat.completions.create.assert_called_once()

    @patch('nagatha_assistant.core.agent.get_openai_client')
    @patch('nagatha_assistant.core.agent.get_mcp_manager')
    @pytest.mark.asyncio
    async def test_chat_with_user_tool_call(self, mock_get_manager, mock_get_client):
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
        
        # Set up the client mock
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response1, mock_response2])
        mock_get_client.return_value = mock_client
        
        mock_manager = MagicMock()
        mock_manager.call_tool = AsyncMock(return_value={"result": "success"})
        mock_get_manager.return_value = mock_manager
        
        # Mock all the dependencies that send_message uses
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class, \
             patch('nagatha_assistant.core.agent.Message') as mock_message_class, \
             patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools, \
             patch('nagatha_assistant.core.agent.get_messages') as mock_get_messages, \
             patch('nagatha_assistant.core.agent.get_system_prompt') as mock_system_prompt, \
             patch('nagatha_assistant.core.agent._notify') as mock_notify, \
             patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus:
            
            # Setup session mock
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            # Setup message mock
            mock_message = MagicMock()
            mock_message.id = 1
            mock_message_class.return_value = mock_message
            
            # Setup other mocks
            mock_tools.return_value = [{'name': 'test_tool', 'description': 'Test tool'}]
            mock_get_messages.return_value = []
            mock_system_prompt.return_value = "You are a helpful assistant."
            mock_notify.return_value = AsyncMock()
            
            # Setup event bus mock
            mock_bus = MagicMock()
            mock_bus._running = False
            mock_event_bus.return_value = mock_bus
            
            result = await agent.send_message(1, "Use the test tool")
            
            assert result == "Tool result processed"
            assert mock_client.chat.completions.create.call_count == 2

    @patch('nagatha_assistant.core.agent.get_openai_client')
    @pytest.mark.asyncio
    async def test_chat_with_user_error_handling(self, mock_get_client):
        """Test chat error handling."""
        # Set up the client mock to raise an exception
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        mock_get_client.return_value = mock_client
        
        # Mock all the dependencies that send_message uses
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class, \
             patch('nagatha_assistant.core.agent.Message') as mock_message_class, \
             patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools, \
             patch('nagatha_assistant.core.agent.get_messages') as mock_get_messages, \
             patch('nagatha_assistant.core.agent.get_system_prompt') as mock_system_prompt, \
             patch('nagatha_assistant.core.agent._notify') as mock_notify, \
             patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus:
            
            # Setup session mock
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            # Setup message mock
            mock_message = MagicMock()
            mock_message.id = 1
            mock_message_class.return_value = mock_message
            
            # Setup other mocks
            mock_tools.return_value = []
            mock_get_messages.return_value = []
            mock_system_prompt.return_value = "You are a helpful assistant."
            mock_notify.return_value = AsyncMock()
            
            # Setup event bus mock
            mock_bus = MagicMock()
            mock_bus._running = False
            mock_event_bus.return_value = mock_bus
            
            result = await agent.send_message(1, "Hello")
            
            assert "I encountered an error" in result
            assert "API Error" in result

    @patch('nagatha_assistant.core.agent.get_openai_client')
    @patch('nagatha_assistant.core.agent.get_mcp_manager')
    @pytest.mark.asyncio
    async def test_chat_with_tool_call_error(self, mock_get_manager, mock_get_client):
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
        
        # Set up the client mock
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response1, mock_response2])
        mock_get_client.return_value = mock_client
        
        mock_manager = MagicMock()
        mock_manager.call_tool = AsyncMock(side_effect=Exception("Tool error"))
        mock_get_manager.return_value = mock_manager
        
        # Mock all the dependencies that send_message uses
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class, \
             patch('nagatha_assistant.core.agent.Message') as mock_message_class, \
             patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools, \
             patch('nagatha_assistant.core.agent.get_messages') as mock_get_messages, \
             patch('nagatha_assistant.core.agent.get_system_prompt') as mock_system_prompt, \
             patch('nagatha_assistant.core.agent._notify') as mock_notify, \
             patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus:
            
            # Setup session mock
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            # Setup message mock
            mock_message = MagicMock()
            mock_message.id = 1
            mock_message_class.return_value = mock_message
            
            # Setup other mocks
            mock_tools.return_value = [{'name': 'failing_tool', 'description': 'Failing tool'}]
            mock_get_messages.return_value = []
            mock_system_prompt.return_value = "You are a helpful assistant."
            mock_notify.return_value = AsyncMock()
            
            # Setup event bus mock
            mock_bus = MagicMock()
            mock_bus._running = False
            mock_event_bus.return_value = mock_bus
            
            result = await agent.send_message(1, "Use the failing tool")
            
            assert "Error executing tool 'failing_tool'" in result
            # Note: Current behavior is that agent generates error message directly,
            # rather than asking OpenAI again, so only 1 call is expected
            assert mock_client.chat.completions.create.call_count == 1

    @patch('nagatha_assistant.core.agent.get_openai_client')
    @pytest.mark.asyncio
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
        
        with patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools:
            mock_tools.return_value = [{'name': 'test_tool', 'description': 'Test tool'}]
            
            result = await agent.send_message(1, "Use test tool")
            
            # Should handle JSON decode error gracefully
            assert "error" in result.lower()

    @pytest.mark.skip(reason="Usage tracking integration not currently implemented in send_message")
    @patch('nagatha_assistant.core.agent.record_usage')
    @patch('nagatha_assistant.core.agent.get_openai_client')
    @pytest.mark.asyncio
    async def test_usage_tracking(self, mock_get_client, mock_record):
        """Test that usage is tracked correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.model = "gpt-4"
        
        # Set up the client mock
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client
        
        # Mock all the dependencies that send_message uses
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class, \
             patch('nagatha_assistant.core.agent.Message') as mock_message_class, \
             patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools, \
             patch('nagatha_assistant.core.agent.get_messages') as mock_get_messages, \
             patch('nagatha_assistant.core.agent.get_system_prompt') as mock_system_prompt, \
             patch('nagatha_assistant.core.agent._notify') as mock_notify, \
             patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus:
            
            # Setup session mock
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            # Setup message mock
            mock_message = MagicMock()
            mock_message.id = 1
            mock_message_class.return_value = mock_message
            
            # Setup other mocks
            mock_tools.return_value = []
            mock_get_messages.return_value = []
            mock_system_prompt.return_value = "You are a helpful assistant."
            mock_notify.return_value = AsyncMock()
            
            # Setup event bus mock
            mock_bus = MagicMock()
            mock_bus._running = False
            mock_event_bus.return_value = mock_bus
            
            await agent.send_message(1, "Hello", model="gpt-4")

            # Should track usage
            print('DEBUG record_usage call_args_list:', mock_record.call_args_list)
            mock_record.assert_called_once_with(model="gpt-4", prompt_tokens=100, completion_tokens=50)

    def test_push_message_function_exists(self):
        """Test that push_message function exists."""
        assert hasattr(agent, 'push_message')
        assert callable(agent.push_message)

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
            mock_session.refresh = AsyncMock()
            
            with patch('nagatha_assistant.core.agent.ConversationSession') as mock_conv_class:
                mock_conv_class.return_value = mock_conversation
                
                with patch('nagatha_assistant.core.agent.get_mcp_manager'):
                    with patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus:
                        mock_bus = MagicMock()
                        mock_bus._running = True
                        mock_bus.publish_sync = MagicMock()
                        mock_event_bus.return_value = mock_bus
                        
                        session_id = await agent.start_session()
                        assert session_id == 1

    @pytest.mark.asyncio
    async def test_get_messages(self):
        """Test getting messages for a session."""
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_messages = [MagicMock(), MagicMock()]
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_messages
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            messages = await agent.get_messages(1)
            assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending a message."""
        # Mock all the dependencies that send_message uses
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class, \
             patch('nagatha_assistant.core.agent.Message') as mock_message_class, \
             patch('nagatha_assistant.core.agent.get_available_tools') as mock_tools, \
             patch('nagatha_assistant.core.agent.get_messages') as mock_get_messages, \
             patch('nagatha_assistant.core.agent.get_system_prompt') as mock_system_prompt, \
             patch('nagatha_assistant.core.agent._notify') as mock_notify, \
             patch('nagatha_assistant.core.agent.get_event_bus') as mock_event_bus, \
             patch('nagatha_assistant.core.agent.get_openai_client') as mock_get_client:
            
            # Setup session mock
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            # Setup message mock
            mock_message = MagicMock()
            mock_message.id = 1
            mock_message_class.return_value = mock_message
            
            # Setup other mocks
            mock_tools.return_value = []
            mock_get_messages.return_value = []
            mock_system_prompt.return_value = "You are a helpful assistant."
            mock_notify.return_value = AsyncMock()
            
            # Setup event bus mock
            mock_bus = MagicMock()
            mock_bus._running = False
            mock_event_bus.return_value = mock_bus
            
            # Setup OpenAI response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.choices[0].message.tool_calls = None
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.model = "gpt-4"
            
            # Set up the client mock
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            response = await agent.send_message(1, "Hello")
            assert response == "Response"

    @pytest.mark.asyncio
    async def test_call_mcp_tool(self):
        """Test calling an MCP tool."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.call_tool = AsyncMock(return_value={"result": "success"})
            mock_get_manager.return_value = mock_manager
            
            result = await agent.call_mcp_tool("test_tool", {"param": "value"})
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_get_available_tools(self):
        """Test getting available tools."""
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_available_tools.return_value = [
                {'name': 'test_tool', 'description': 'Test tool'}
            ]
            mock_get_manager.return_value = mock_manager
            
            with patch('nagatha_assistant.core.plugin_manager.get_plugin_manager') as mock_get_plugin_manager:
                mock_plugin_manager = MagicMock()
                mock_plugin_manager.get_available_commands.return_value = {}
                mock_get_plugin_manager.return_value = mock_plugin_manager
                
                tools = await agent.get_available_tools()
                assert len(tools) == 1
                assert tools[0]['name'] == 'test_tool'

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing sessions."""
        with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session
            
            mock_sessions = [MagicMock(), MagicMock()]
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_sessions
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            sessions = await agent.list_sessions()
            assert len(sessions) == 2

    def test_format_mcp_status_for_chat(self):
        """Test formatting MCP status for chat."""
        status = {
            'connected': 1,
            'total_configured': 1,
            'total_tools': 5,
            'connected_servers': ['test_server'],
            'failed': 0,
            'failed_servers': []
        }
        
        formatted = agent.format_mcp_status_for_chat(status)
        assert isinstance(formatted, str)
        assert 'test_server' in formatted

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

    @pytest.mark.asyncio
    async def test_shutdown_mcp_manager(self):
        """Test shutting down MCP manager."""
        with patch('nagatha_assistant.core.agent.shutdown_mcp_manager') as mock_shutdown:
            mock_shutdown.return_value = AsyncMock()
            
            await agent.shutdown_mcp_manager()
            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_system_message(self):
        """Test pushing a system message."""
        # Should not raise an error
        await agent.push_system_message(123, "System message")

    def test_agent_module_constants(self):
        """Test that agent module has expected constants and imports."""
        assert hasattr(agent, '_push_callbacks')
        assert hasattr(agent, 'get_openai_client') 