#!/usr/bin/env python3
"""
Integration tests for database operations.
Tests actual database operations with all models.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from nagatha_assistant.db import SessionLocal, engine
from nagatha_assistant.db_models import (
    ConversationSession, Message, Tag, Note, Task, Reminder,
    MemorySection, MemoryEntry, DiscordAutoChat
)


@pytest.fixture(autouse=True)
async def setup_database():
    """Set up database for testing."""
    # Ensure schema is up to date
    from nagatha_assistant.db import ensure_schema
    await ensure_schema()
    
    # Create tables if they don't exist
    from nagatha_assistant.db_models import Base
    from sqlalchemy import create_engine
    from nagatha_assistant.db import DATABASE_URL
    
    # Create sync engine for table creation
    sync_url = DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")
    sync_engine = create_engine(sync_url)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    
    yield


@pytest.mark.asyncio
async def test_conversation_session_creation():
    """Test creating and retrieving conversation sessions."""
    async with SessionLocal() as session:
        # Create a new session
        new_session = ConversationSession()
        session.add(new_session)
        await session.flush()
        
        # Verify session was created
        assert new_session.id is not None
        assert new_session.created_at is not None
        
        # Retrieve the session
        retrieved_session = await session.get(ConversationSession, new_session.id)
        assert retrieved_session is not None
        assert retrieved_session.id == new_session.id


@pytest.mark.asyncio
async def test_message_creation():
    """Test creating and retrieving messages."""
    async with SessionLocal() as session:
        # Create a session first
        session_obj = ConversationSession()
        session.add(session_obj)
        await session.flush()
        
        # Create a message
        message = Message(
            session_id=session_obj.id,
            role="user",
            content="Test message",
            timestamp=datetime.now()
        )
        session.add(message)
        await session.commit()
        
        # Verify message was created
        assert message.id is not None
        assert message.session_id == session_obj.id
        assert message.role == "user"
        assert message.content == "Test message"
        
        # Test relationship
        assert len(session_obj.messages) == 1
        assert session_obj.messages[0].id == message.id


@pytest.mark.asyncio
async def test_notes_and_tags():
    """Test creating notes with tags."""
    async with SessionLocal() as session:
        # Create tags
        tag1 = Tag(name="important")
        tag2 = Tag(name="work")
        session.add_all([tag1, tag2])
        await session.flush()
        
        # Create a note with tags
        note = Note(
            title="Test Note",
            content="This is a test note",
            tags=[tag1, tag2]
        )
        session.add(note)
        await session.commit()
        
        # Verify note and tags
        assert note.id is not None
        assert len(note.tags) == 2
        assert any(tag.name == "important" for tag in note.tags)
        assert any(tag.name == "work" for tag in note.tags)
        
        # Test tag relationship
        assert len(tag1.notes) == 1
        assert tag1.notes[0].id == note.id


@pytest.mark.asyncio
async def test_tasks_and_reminders():
    """Test creating tasks with reminders."""
    async with SessionLocal() as session:
        # Create a task
        task = Task(
            title="Test Task",
            description="This is a test task",
            status="pending",
            priority="high",
            due_at=datetime.now() + timedelta(days=1)
        )
        session.add(task)
        await session.flush()
        
        # Create a reminder for the task
        reminder = Reminder(
            task_id=task.id,
            remind_at=datetime.now() + timedelta(hours=1),
            delivered=False,
            recurrence="daily"
        )
        session.add(reminder)
        await session.commit()
        
        # Verify task and reminder
        assert task.id is not None
        assert reminder.id is not None
        assert reminder.task_id == task.id
        assert reminder.delivered is False
        
        # Test relationship
        assert len(task.reminders) == 1
        assert task.reminders[0].id == reminder.id


@pytest.mark.asyncio
async def test_memory_system():
    """Test memory sections and entries."""
    async with SessionLocal() as session:
        # Create a memory section
        section = MemorySection(
            name="user_preferences",
            description="User preferences and settings",
            persistence_level="permanent"
        )
        session.add(section)
        await session.flush()
        
        # Create memory entries
        entry1 = MemoryEntry(
            section_id=section.id,
            key="theme",
            value_type="string",
            value="dark"
        )
        entry2 = MemoryEntry(
            section_id=section.id,
            key="language",
            value_type="string",
            value="en"
        )
        session.add_all([entry1, entry2])
        await session.commit()
        
        # Verify memory entries
        assert entry1.id is not None
        assert entry2.id is not None
        assert entry1.section_id == section.id
        assert entry2.section_id == section.id
        
        # Test relationships
        assert len(section.memory_entries) == 2
        assert any(entry.key == "theme" for entry in section.memory_entries)
        assert any(entry.key == "language" for entry in section.memory_entries)


@pytest.mark.asyncio
async def test_discord_auto_chat():
    """Test Discord auto-chat configuration."""
    async with SessionLocal() as session:
        # Create Discord auto-chat config
        discord_config = DiscordAutoChat(
            channel_id="123456789",
            guild_id="987654321",
            enabled=True,
            enabled_by_user_id="111222333"
        )
        session.add(discord_config)
        await session.commit()
        
        # Verify configuration
        assert discord_config.id is not None
        assert discord_config.channel_id == "123456789"
        assert discord_config.guild_id == "987654321"
        assert discord_config.enabled is True
        assert discord_config.enabled_by_user_id == "111222333"
        assert discord_config.message_count == 0


@pytest.mark.asyncio
async def test_cascade_deletions():
    """Test that cascade deletions work properly."""
    async with SessionLocal() as session:
        # Create a session with messages
        session_obj = ConversationSession()
        session.add(session_obj)
        await session.flush()
        
        message1 = Message(
            session_id=session_obj.id,
            role="user",
            content="Message 1",
            timestamp=datetime.now()
        )
        message2 = Message(
            session_id=session_obj.id,
            role="assistant",
            content="Response 1",
            timestamp=datetime.now()
        )
        session.add_all([message1, message2])
        await session.flush()
        
        # Verify messages exist
        assert message1.id is not None
        assert message2.id is not None
        
        # Delete the session (should cascade to messages)
        await session.delete(session_obj)
        await session.commit()
        
        # Verify messages were deleted
        result = await session.execute(text("SELECT COUNT(*) FROM messages WHERE session_id = :session_id"))
        count = result.scalar()
        assert count == 0


@pytest.mark.asyncio
async def test_unique_constraints():
    """Test that unique constraints are enforced."""
    async with SessionLocal() as session:
        # Create a tag
        tag1 = Tag(name="unique_tag")
        session.add(tag1)
        await session.commit()
        
        # Try to create another tag with the same name
        tag2 = Tag(name="unique_tag")
        session.add(tag2)
        
        # This should raise an integrity error
        with pytest.raises(Exception):  # SQLAlchemy will raise an integrity error
            await session.commit()
        
        # Rollback to clean state
        await session.rollback()


@pytest.mark.asyncio
async def test_boolean_defaults():
    """Test that boolean defaults are applied correctly."""
    async with SessionLocal() as session:
        # Create a task
        task = Task(
            title="Test Task",
            description="Test description"
        )
        session.add(task)
        await session.flush()
        
        # Create a reminder without specifying delivered
        reminder = Reminder(
            task_id=task.id,
            remind_at=datetime.now() + timedelta(hours=1)
        )
        session.add(reminder)
        await session.commit()
        
        # Verify default values
        assert reminder.delivered is False
        
        # Create Discord config without specifying enabled
        discord_config = DiscordAutoChat(
            channel_id="test_channel",
            enabled_by_user_id="test_user"
        )
        session.add(discord_config)
        await session.commit()
        
        # Verify default values
        assert discord_config.enabled is False


@pytest.mark.asyncio
async def test_complex_queries():
    """Test complex database queries."""
    async with SessionLocal() as session:
        # Create test data
        session_obj = ConversationSession()
        session.add(session_obj)
        await session.flush()
        
        # Add messages
        messages = [
            Message(session_id=session_obj.id, role="user", content=f"Message {i}", timestamp=datetime.now())
            for i in range(5)
        ]
        session.add_all(messages)
        await session.commit()
        
        # Test complex query - count messages by role
        result = await session.execute(
            text("SELECT role, COUNT(*) as count FROM messages GROUP BY role")
        )
        role_counts = {row.role: row.count for row in result.fetchall()}
        
        assert role_counts["user"] == 5
        
        # Test query with joins
        result = await session.execute(
            text("""
                SELECT cs.id, COUNT(m.id) as message_count 
                FROM conversation_sessions cs 
                LEFT JOIN messages m ON cs.id = m.session_id 
                GROUP BY cs.id
            """)
        )
        session_data = result.fetchall()
        assert len(session_data) == 1
        assert session_data[0].message_count == 5


@pytest.mark.asyncio
async def test_transaction_rollback():
    """Test that transactions can be rolled back properly."""
    async with SessionLocal() as session:
        # Start a transaction
        async with session.begin():
            # Create a session
            session_obj = ConversationSession()
            session.add(session_obj)
            await session.flush()
            
            # Create a message
            message = Message(
                session_id=session_obj.id,
                role="user",
                content="Test message",
                timestamp=datetime.now()
            )
            session.add(message)
            
            # The transaction should commit automatically due to context manager
            pass
        
        # Verify data was committed
        assert session_obj.id is not None
        assert message.id is not None
        
        # Test rollback scenario
        async with SessionLocal() as session2:
            try:
                async with session2.begin():
                    # Create invalid data that should cause rollback
                    invalid_message = Message(
                        session_id=999999,  # Non-existent session
                        role="user",
                        content="Invalid message",
                        timestamp=datetime.now()
                    )
                    session2.add(invalid_message)
                    # This should fail and rollback
                    await session2.flush()
            except Exception:
                # Expected to fail
                pass
            
            # Verify no data was committed
            result = await session2.execute(text("SELECT COUNT(*) FROM messages WHERE content = 'Invalid message'"))
            count = result.scalar()
            assert count == 0 