import json

import pytest


import nagatha_assistant.modules.chat as chat_module


# ---------------------------------------------------------------------------
# Helper: fake OpenAI completion that triggers echo function
# ---------------------------------------------------------------------------


async def _fake_completion(model, messages, functions=None):  # noqa: D401, ARG001
    """Return a response that requests the `echo` function."""

    class Choice:  # noqa: D401
        def __init__(self):
            self.message = {
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": "echo",
                    "arguments": json.dumps({"text": "from plugin"}),
                },
            }

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
async def test_chat_integration_with_echo(monkeypatch):
    """send_message should execute echo plugin when model asks for it."""

    # Patch the OpenAI client used by the chat module
    monkeypatch.setattr(
        chat_module.client.chat.completions,
        "create",
        _fake_completion,
    )

    # Create session & send message
    sid = await chat_module.start_session()
    reply = await chat_module.send_message(sid, "trigger echo")

    assert reply == "from plugin"
