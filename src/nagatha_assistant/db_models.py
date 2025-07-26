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

# ---------------------------------------------------------------------------
# Memory System models
# ---------------------------------------------------------------------------

class MemorySection(Base):
    """Represents different memory sections with different persistence levels."""
    __tablename__ = "memory_sections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    persistence_level = Column(String(50), nullable=False, server_default="permanent")  # temporary, session, permanent
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    memory_entries = relationship("MemoryEntry", back_populates="section", cascade="all, delete-orphan")


class MemoryEntry(Base):
    """Represents individual memory entries in the system."""
    __tablename__ = "memory_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("memory_sections.id"), nullable=False)
    key = Column(String(255), nullable=False, index=True)
    value_type = Column(String(50), nullable=False, server_default="string")  # string, json, binary
    value = Column(Text, nullable=True)  # JSON serialized or string value
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"), nullable=True)  # For session-scoped memory
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For temporary memory
    
    # Relationships
    section = relationship("MemorySection", back_populates="memory_entries")
    session = relationship("ConversationSession", foreign_keys=[session_id])
    
    # Unique constraint for key within a section and session (if applicable)
    __table_args__ = (
        # For session-scoped memory, key must be unique within section and session
        # For global memory, key must be unique within section
    )


# ---------------------------------------------------------------------------
# Discord Auto-Chat Configuration models
# ---------------------------------------------------------------------------

class DiscordAutoChat(Base):
    """Represents auto-chat configuration for Discord channels/DMs."""
    __tablename__ = "discord_auto_chat"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(255), unique=True, nullable=False, index=True)  # Discord channel/DM ID
    guild_id = Column(String(255), nullable=True, index=True)  # Discord guild ID (null for DMs)
    enabled = Column(Boolean, nullable=False, server_default="0")  # Auto-chat enabled/disabled
    enabled_by_user_id = Column(String(255), nullable=False)  # Discord user ID who enabled it
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_message_at = Column(DateTime(timezone=True), nullable=True)  # For rate limiting
    message_count = Column(Integer, nullable=False, server_default="0")  # Daily message count for rate limiting


# ---------------------------------------------------------------------------
# Scheduled Task models
# ---------------------------------------------------------------------------

class ScheduledTask(Base):
    """Represents a scheduled task in the task scheduler."""
    __tablename__ = "scheduled_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, nullable=False, index=True)  # Celery task ID
    task_type = Column(String(100), nullable=False, index=True)  # Type of task (mcp_tool, plugin_command, etc.)
    task_name = Column(String(255), nullable=True, index=True)  # Human-readable task name
    description = Column(Text, nullable=True)  # Task description
    
    # Task configuration
    task_args = Column(Text, nullable=False)  # JSON-encoded task arguments
    schedule_type = Column(String(50), nullable=False)  # one_time, recurring
    schedule_spec = Column(String(255), nullable=False)  # Cron expression or datetime
    
    # Status tracking
    status = Column(String(50), nullable=False, server_default="scheduled")  # scheduled, running, completed, failed, cancelled
    
    # Execution tracking
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, nullable=False, server_default="0")
    max_runs = Column(Integer, nullable=True)  # For one-time tasks or limited runs
    
    # Error handling
    retry_count = Column(Integer, nullable=False, server_default="0")
    max_retries = Column(Integer, nullable=False, server_default="3")
    last_error = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(String(255), nullable=True)  # User or system that created the task
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    executions = relationship("TaskExecution", back_populates="scheduled_task", cascade="all, delete-orphan")


class TaskExecution(Base):
    """Represents an execution of a scheduled task."""
    __tablename__ = "task_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    scheduled_task_id = Column(Integer, ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(String(255), nullable=True, index=True)  # Celery execution ID
    
    # Execution details
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False)  # running, completed, failed, cancelled
    
    # Results
    result = Column(Text, nullable=True)  # JSON-encoded execution result
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    
    # Performance metrics
    duration_seconds = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)
    cpu_usage_percent = Column(Integer, nullable=True)
    
    # Relationships
    scheduled_task = relationship("ScheduledTask", back_populates="executions")