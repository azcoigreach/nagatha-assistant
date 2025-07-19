"""
Event system definitions and types for Nagatha Assistant.

This module provides the base classes and types for the event bus system,
including event definitions, priorities, and standard event types.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, Optional, Union, Callable, Awaitable


class EventPriority(IntEnum):
    """Event priority levels, with lower numbers being higher priority."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Event:
    """Base event class for all events in the system."""
    
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    
    # Auto-populated fields
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """Ensure timestamp is timezone-aware."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


# Type aliases for event handlers
SyncEventHandler = Callable[[Event], Any]
AsyncEventHandler = Callable[[Event], Awaitable[Any]]
EventHandler = Union[SyncEventHandler, AsyncEventHandler]


class StandardEventTypes:
    """Standard event types used throughout the Nagatha system."""
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    
    # Agent events
    AGENT_MESSAGE_RECEIVED = "agent.message.received"
    AGENT_MESSAGE_SENT = "agent.message.sent"
    AGENT_CONVERSATION_STARTED = "agent.conversation.started"
    AGENT_CONVERSATION_ENDED = "agent.conversation.ended"
    
    # MCP events
    MCP_SERVER_CONNECTED = "mcp.server.connected"
    MCP_SERVER_DISCONNECTED = "mcp.server.disconnected"
    MCP_TOOL_CALLED = "mcp.tool.called"
    MCP_TOOL_RESULT = "mcp.tool.result"
    
    # Database events
    DB_ENTITY_CREATED = "db.entity.created"
    DB_ENTITY_UPDATED = "db.entity.updated"
    DB_ENTITY_DELETED = "db.entity.deleted"
    
    # UI events
    UI_USER_ACTION = "ui.user.action"
    UI_NOTIFICATION = "ui.notification"
    
    # Task/Reminder events
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    REMINDER_TRIGGERED = "reminder.triggered"
    
    # Note events
    NOTE_CREATED = "note.created"
    NOTE_UPDATED = "note.updated"
    NOTE_DELETED = "note.deleted"


def create_system_event(event_type: str, data: Optional[Dict[str, Any]] = None, 
                       priority: EventPriority = EventPriority.NORMAL,
                       source: Optional[str] = None) -> Event:
    """Helper function to create system events with consistent formatting."""
    return Event(
        event_type=event_type,
        data=data or {},
        priority=priority,
        source=source or "system"
    )


def create_agent_event(event_type: str, session_id: int, message_data: Optional[Dict[str, Any]] = None,
                      priority: EventPriority = EventPriority.NORMAL) -> Event:
    """Helper function to create agent-related events."""
    data = {"session_id": session_id}
    if message_data:
        data.update(message_data)
    
    return Event(
        event_type=event_type,
        data=data,
        priority=priority,
        source="agent"
    )


def create_mcp_event(event_type: str, server_name: str, tool_data: Optional[Dict[str, Any]] = None,
                    priority: EventPriority = EventPriority.NORMAL) -> Event:
    """Helper function to create MCP-related events."""
    data = {"server_name": server_name}
    if tool_data:
        data.update(tool_data)
    
    return Event(
        event_type=event_type,
        data=data,
        priority=priority,
        source="mcp"
    )