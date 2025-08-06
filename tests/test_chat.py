import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import nagatha_assistant.core.agent as chat_module
from nagatha_assistant.core.agent import start_session, get_messages, send_message


@pytest.mark.asyncio
async def test_start_session_and_get_messages():
    # New session should have a welcome message initially
    session_id = await start_session()
    assert isinstance(session_id, int) and session_id > 0
    messages = await get_messages(session_id)
    assert isinstance(messages, list)
    assert len(messages) >= 1  # At least one message (welcome message)
    
    # Check that the first message is a welcome message from assistant
    welcome_message = messages[0]
    assert welcome_message.role == 'assistant'
    assert 'Hello' in welcome_message.content  # Welcome message should contain greeting
    assert 'Nagatha' in welcome_message.content  # Should mention Nagatha


@pytest.mark.asyncio
async def test_send_message_stores_history():
    """Test that send_message stores messages properly in history."""
    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "fake reply"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.model = "test-model"
    
    # Mock the OpenAI client
    with patch('nagatha_assistant.core.agent.get_openai_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        
        # Start session and send a user message
        sid = await start_session()
        reply = await send_message(sid, 'hello world', model='test-model')
        
        # Verify reply from fake API
        assert reply == 'fake reply'
        
        # Verify messages stored in DB (welcome + user + assistant)
        msgs = await get_messages(sid)
        assert len(msgs) >= 3  # Should have at least welcome, user, and assistant messages
        
        # Check that user message was stored
        user_messages = [m for m in msgs if m.role == 'user' and m.content == 'hello world']
        assert len(user_messages) == 1
        
        # Check that assistant message was stored
        assistant_messages = [m for m in msgs if m.role == 'assistant' and m.content == 'fake reply']
        assert len(assistant_messages) == 1