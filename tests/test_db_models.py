import pytest
from datetime import datetime
from sqlalchemy import Table
from nagatha_assistant.db import Base
from nagatha_assistant.db_models import (
    ConversationSession, Message, Tag, Note, Task, Reminder, 
    MemorySection, MemoryEntry, DiscordAutoChat
)


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


def test_notes_tables_registered():
    """Test that notes and tags tables are registered."""
    tables = set(Base.metadata.tables.keys())
    assert "notes" in tables, "notes table missing"
    assert "tags" in tables, "tags table missing"
    assert "note_tags" in tables, "note_tags association table missing"


def test_notes_columns():
    """Test notes table structure."""
    table: Table = Base.metadata.tables.get("notes")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "title", "content", "created_at", "updated_at"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_tags_columns():
    """Test tags table structure."""
    table: Table = Base.metadata.tables.get("tags")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "name"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_tasks_tables_registered():
    """Test that tasks and reminders tables are registered."""
    tables = set(Base.metadata.tables.keys())
    assert "tasks" in tables, "tasks table missing"
    assert "reminders" in tables, "reminders table missing"
    assert "task_tags" in tables, "task_tags association table missing"


def test_tasks_columns():
    """Test tasks table structure."""
    table: Table = Base.metadata.tables.get("tasks")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "title", "description", "status", "priority", "due_at", "created_at", "updated_at"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_reminders_columns():
    """Test reminders table structure."""
    table: Table = Base.metadata.tables.get("reminders")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "task_id", "remind_at", "delivered", "recurrence", "last_sent_at"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_memory_tables_registered():
    """Test that memory tables are registered."""
    tables = set(Base.metadata.tables.keys())
    assert "memory_sections" in tables, "memory_sections table missing"
    assert "memory_entries" in tables, "memory_entries table missing"


def test_memory_sections_columns():
    """Test memory_sections table structure."""
    table: Table = Base.metadata.tables.get("memory_sections")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "name", "description", "persistence_level", "created_at"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_memory_entries_columns():
    """Test memory_entries table structure."""
    table: Table = Base.metadata.tables.get("memory_entries")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "section_id", "key", "value_type", "value", "session_id", "created_at", "updated_at", "expires_at"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_discord_auto_chat_columns():
    """Test discord_auto_chat table structure."""
    table: Table = Base.metadata.tables.get("discord_auto_chat")
    assert table is not None
    cols = set(table.columns.keys())
    expected = {"id", "channel_id", "guild_id", "enabled", "enabled_by_user_id", "created_at", "updated_at", "last_message_at", "message_count"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_foreign_key_constraints():
    """Test that foreign key constraints are properly defined."""
    tables = Base.metadata.tables
    
    # Test messages -> conversation_sessions
    messages_table = tables.get("messages")
    assert messages_table is not None
    session_fk = next((fk for fk in messages_table.foreign_keys if fk.column.table.name == "conversation_sessions"), None)
    assert session_fk is not None, "Missing foreign key from messages to conversation_sessions"
    
    # Test reminders -> tasks
    reminders_table = tables.get("reminders")
    assert reminders_table is not None
    task_fk = next((fk for fk in reminders_table.foreign_keys if fk.column.table.name == "tasks"), None)
    assert task_fk is not None, "Missing foreign key from reminders to tasks"
    
    # Test memory_entries -> memory_sections
    memory_entries_table = tables.get("memory_entries")
    assert memory_entries_table is not None
    section_fk = next((fk for fk in memory_entries_table.foreign_keys if fk.column.table.name == "memory_sections"), None)
    assert section_fk is not None, "Missing foreign key from memory_entries to memory_sections"


def test_association_tables():
    """Test that association tables are properly defined."""
    tables = Base.metadata.tables
    
    # Test note_tags
    note_tags_table = tables.get("note_tags")
    assert note_tags_table is not None
    note_tags_cols = set(note_tags_table.columns.keys())
    assert "note_id" in note_tags_cols
    assert "tag_id" in note_tags_cols
    
    # Test task_tags
    task_tags_table = tables.get("task_tags")
    assert task_tags_table is not None
    task_tags_cols = set(task_tags_table.columns.keys())
    assert "task_id" in task_tags_cols
    assert "tag_id" in task_tags_cols


def test_boolean_defaults():
    """Test that boolean columns have proper PostgreSQL defaults."""
    tables = Base.metadata.tables
    
    # Test reminders.delivered
    reminders_table = tables.get("reminders")
    assert reminders_table is not None
    delivered_col = reminders_table.columns.get("delivered")
    assert delivered_col is not None
    assert delivered_col.server_default.arg == "false", "delivered column should default to false"
    
    # Test discord_auto_chat.enabled
    discord_table = tables.get("discord_auto_chat")
    assert discord_table is not None
    enabled_col = discord_table.columns.get("enabled")
    assert enabled_col is not None
    assert enabled_col.server_default.arg == "false", "enabled column should default to false"


def test_indexes():
    """Test that important indexes are defined."""
    tables = Base.metadata.tables
    
    # Test conversation_sessions indexes
    sessions_table = tables.get("conversation_sessions")
    assert sessions_table is not None
    assert any(idx.name == "ix_conversation_sessions_id" for idx in sessions_table.indexes)
    
    # Test messages indexes
    messages_table = tables.get("messages")
    assert messages_table is not None
    assert any(idx.name == "ix_messages_id" for idx in messages_table.indexes)
    
    # Test tags unique index
    tags_table = tables.get("tags")
    assert tags_table is not None
    assert any(idx.name == "ix_tags_name" for idx in tags_table.indexes)
    name_idx = next(idx for idx in tags_table.indexes if idx.name == "ix_tags_name")
    assert name_idx.unique, "tags.name should have a unique index"


def test_all_tables_present():
    """Test that all expected tables are present in the schema."""
    expected_tables = {
        "conversation_sessions",
        "messages",
        "notes",
        "tags",
        "note_tags",
        "tasks",
        "reminders",
        "task_tags",
        "memory_sections",
        "memory_entries",
        "discord_auto_chat"
    }
    
    actual_tables = set(Base.metadata.tables.keys())
    missing_tables = expected_tables - actual_tables
    extra_tables = actual_tables - expected_tables
    
    assert not missing_tables, f"Missing tables: {missing_tables}"
    if extra_tables:
        print(f"Note: Extra tables found: {extra_tables}")