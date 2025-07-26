import pytest

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
async def test_send_message_stores_history(monkeypatch):
    # Mock OpenAI API
    calls = {}

    # Mock OpenAI API create call
    async def fake_create(model, messages, **kwargs):
        # Record call parameters
        calls['model'] = model
        calls['messages'] = list(messages)
        # Fake response structure
        class Message:
            def __init__(self):
                self.role = 'assistant'
                self.content = 'fake reply'
        class Choice:
            def __init__(self):
                self.message = Message()
        class Response:
            def __init__(self):
                self.choices = [Choice()]
        return Response()

    # Patch AsyncOpenAI client method
    monkeypatch.setattr(
        chat_module.client.chat.completions,
        'create',
        fake_create
    )

    # Start session and send a user message
    sid = await start_session()
    reply = await send_message(sid, 'hello world', model='test-model')
    # Verify reply from fake API
    assert reply == 'fake reply'

    # Verify messages stored in DB (welcome + user + assistant)
    msgs = await get_messages(sid)
    assert len(msgs) >= 3  # At least welcome message + user message + assistant reply
    
    # Find the welcome message (should be first)
    welcome_msg = msgs[0]
    assert welcome_msg.role == 'assistant' and 'Hello' in welcome_msg.content
    
    # Find the user message
    user_msg = None
    for msg in msgs:
        if msg.role == 'user' and msg.content == 'hello world':
            user_msg = msg
            break
    assert user_msg is not None, "User message should be found"
    
    # Find the assistant reply
    assistant_msg = None
    for msg in msgs:
        if msg.role == 'assistant' and msg.content == 'fake reply':
            assistant_msg = msg
            break
    assert assistant_msg is not None, "Assistant reply should be found"

    # Verify correct model and history were passed to OpenAI
    assert calls['model'] == 'test-model'
    # Last message in history should be the user message
    assert calls['messages'][-1]['role'] == 'user'
    assert calls['messages'][-1]['content'] == 'hello world'