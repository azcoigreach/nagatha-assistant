import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


import nagatha_assistant.core.agent as chat_module
from nagatha_assistant.core import get_event_bus, initialize_plugin_system


# ---------------------------------------------------------------------------
# Helper: fake OpenAI completion that triggers echo function
# ---------------------------------------------------------------------------


async def _fake_completion(model, messages, tools=None, **kwargs):  # noqa: D401, ARG001
    """Return a response that requests the `echo` function using tool calls."""

    # First call: return tool calls
    if tools and any(tool['function']['name'] == 'echo' for tool in tools):
        class ToolCall:  # noqa: D401
            def __init__(self):
                self.id = "call_echo_123"
                self.type = "function"
                self.function = type("Function", (), {
                    "name": "echo",
                    "arguments": json.dumps({"text": "from plugin"})
                })()

        class Message:  # noqa: D401
            def __init__(self):
                self.role = "assistant"
                self.content = None
                self.tool_calls = [ToolCall()]

        class Choice:  # noqa: D401
            def __init__(self):
                self.message = Message()

        class Resp:  # noqa: D401
            def __init__(self):
                self.choices = [Choice()]
                # dummy usage
                self.usage = type("U", (), {"prompt_tokens": 0, "completion_tokens": 0})()

        return Resp()
    
    # Follow-up call: return final response
    else:
        class Message:  # noqa: D401
            def __init__(self):
                self.role = "assistant"
                self.content = "from plugin"

        class Choice:  # noqa: D401
            def __init__(self):
                self.message = Message()

        class Resp:  # noqa: D401
            def __init__(self):
                self.choices = [Choice()]
                # dummy usage
                self.usage = type("U", (), {"prompt_tokens": 0, "completion_tokens": 0})()

        return Resp()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_integration_with_echo():
    """send_message should execute echo plugin when model asks for it."""

    # Start event bus and initialize plugin system
    event_bus = get_event_bus()
    await event_bus.start()

    try:
        await initialize_plugin_system()

        # Mock OpenAI response that includes tool call
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_123"
        mock_response.choices[0].message.tool_calls[0].function.name = "echo"
        mock_response.choices[0].message.tool_calls[0].function.arguments = '{"message": "Test echo"}'
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "gpt-4"

        # Mock the OpenAI client
        with patch('nagatha_assistant.core.agent.get_openai_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Create session & send message
            sid = await chat_module.start_session()
            reply = await chat_module.send_message(sid, "trigger echo")

            # The reply should contain the echo result
            assert "from plugin" in reply
        
    finally:
        await event_bus.stop()
