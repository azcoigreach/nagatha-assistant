"""
Database models for Nagatha Assistant chat sessions.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Table, Boolean
from sqlalchemy.orm import relationship

from nagatha_assistant.db import Base

# Association table for many-to-many relationship between notes and tags
from sqlalchemy import Table

note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class ConversationSession(Base):
    """
    Represents a chat session with the AI model.
    """
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """
    Represents a single message in a conversation session.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ConversationSession", back_populates="messages")
    
# ---------------------------------------------------------------------------
# Notes and Tags models
# ---------------------------------------------------------------------------
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    notes = relationship(
        "Note",
        secondary=note_tags,
        back_populates="tags",
        cascade="all",
    )

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    tags = relationship(
        "Tag",
        secondary=note_tags,
        back_populates="notes",
    )
    
# ---------------------------------------------------------------------------
# Task and Reminder models
# ---------------------------------------------------------------------------
# Association table for tasks and tags
task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, server_default="pending")  # pending, completed, closed
    priority = Column(String(10), nullable=False, server_default="med")  # low, med, high
    due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    tags = relationship(
        "Tag",
        secondary=task_tags,
        back_populates="tasks",
    )
    reminders = relationship(
        "Reminder",
        back_populates="task",
        cascade="all, delete-orphan",
    )

class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False)
    delivered = Column(Boolean, nullable=False, server_default="0")
    recurrence = Column(String(20), nullable=True)  # daily, weekly, monthly, yearly
    last_sent_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task", back_populates="reminders")
    
# ---------------------------------------------------------------------------
# Establish Task-Tag back-population on Tag
# ---------------------------------------------------------------------------
Tag.tasks = relationship(
    "Task",
    secondary=task_tags,
    back_populates="tags",
    cascade="all",
)