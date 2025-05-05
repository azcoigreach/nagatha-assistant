import json
import pytest
from datetime import datetime

from fastapi.testclient import TestClient

from nagatha_assistant.server import app
import nagatha_assistant.core.agent as chat_module


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_sessions_lifecycle(client):
    # Initially no sessions
    resp = client.get("/sessions")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create a new session
    resp = client.post("/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data and isinstance(data["id"], int)
    sid = data["id"]

    # List sessions now returns the new session
    resp = client.get("/sessions")
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == sid
    # created_at should be ISO format
    dt_str = sessions[0]["created_at"]
    # Validate ISO format
    datetime.fromisoformat(dt_str)


def test_messages_and_send(client, monkeypatch):
    # Mock OpenAI completion to return fixed reply
    async def fake_create(model, messages, **kwargs):  # noqa: ARG001
        class Choice:
            def __init__(self):
                self.message = {"role": "assistant", "content": "hello from fake"}

        class Resp:
            def __init__(self):
                self.choices = [Choice()]
                self.usage = type("U", (), {"prompt_tokens": 0, "completion_tokens": 0})()

        return Resp()

    # Patch the OpenAI client
    monkeypatch.setattr(
        chat_module.client.chat.completions,
        "create",
        fake_create,
    )

    # Start fresh session
    sid = client.post("/sessions").json()["id"]

    # GET messages should be empty
    resp = client.get(f"/sessions/{sid}/messages")
    assert resp.status_code == 200
    assert resp.json() == []

    # Send a message
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "ping"})
    assert resp.status_code == 200
    result = resp.json()
    assert result.get("reply") == "hello from fake"

    # GET messages now returns two messages (user and assistant)
    msgs = client.get(f"/sessions/{sid}/messages").json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user" and msgs[0]["content"] == "ping"
    assert msgs[1]["role"] == "assistant" and msgs[1]["content"] == "hello from fake"


def test_push_message_endpoint(client):
    # Start a session
    sid = client.post("/sessions").json()["id"]
    # Push a message into session
    payload = {"content": "async info", "role": "assistant"}
    resp = client.post(f"/sessions/{sid}/push", json=payload)
    assert resp.status_code == 200
    assert resp.json().get("status") == "pushed"

    # Confirm message appears in history
    msgs = client.get(f"/sessions/{sid}/messages").json()
    # last message matches pushed content
    assert msgs and msgs[-1]["content"] == "async info"
    assert msgs[-1]["role"] == "assistant"


def test_plugins_listing(client):
    # List plugins
    resp = client.get("/plugins")
    assert resp.status_code == 200
    plugins = resp.json()
    assert isinstance(plugins, list)
    # We expect at least the 'echo' plugin
    names = {p['name'] for p in plugins}
    assert 'echo' in names
    # Validate function spec structure
    for p in plugins:
        assert 'version' in p and isinstance(p['version'], str)
        assert 'functions' in p and isinstance(p['functions'], list)