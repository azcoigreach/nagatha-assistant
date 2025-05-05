import pytest

import nagatha_assistant.core.agent as chat_module
from nagatha_assistant.core.agent import start_session, get_messages, send_message


@pytest.mark.asyncio
async def test_start_session_and_get_messages():
    # New session should have no messages initially
    session_id = await start_session()
    assert isinstance(session_id, int) and session_id > 0
    messages = await get_messages(session_id)
    assert isinstance(messages, list)
    assert len(messages) == 0


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
        class Choice:
            def __init__(self):
                self.message = {'role': 'assistant', 'content': 'fake reply'}
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

    # Verify messages stored in DB
    msgs = await get_messages(sid)
    assert len(msgs) == 2
    assert msgs[0].role == 'user' and msgs[0].content == 'hello world'
    assert msgs[1].role == 'assistant' and msgs[1].content == 'fake reply'

    # Verify correct model and history were passed to OpenAI
    assert calls['model'] == 'test-model'
    # Last message in history should be the user message
    assert calls['messages'][-1]['role'] == 'user'
    assert calls['messages'][-1]['content'] == 'hello world'