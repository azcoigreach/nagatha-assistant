import pytest

from sqlalchemy import Table
from nagatha_assistant.db import Base


def test_chat_tables_registered():
    # Ensure chat session tables are in metadata
    tables = set(Base.metadata.tables.keys())
    assert "conversation_sessions" in tables, "conversation_sessions table missing"
    assert "messages" in tables, "messages table missing"


def test_conversation_sessions_columns():
    table: Table = Base.metadata.tables.get("conversation_sessions")
    assert table is not None
    cols = set(table.columns.keys())
    assert "id" in cols
    assert "created_at" in cols


def test_messages_columns():
    table: Table = Base.metadata.tables.get("messages")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "session_id", "role", "content", "timestamp"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"