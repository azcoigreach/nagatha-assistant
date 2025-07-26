# Event Bus System Documentation

## Overview

The Nagatha Assistant Event Bus System provides a central communication mechanism for all components using an asynchronous publish/subscribe pattern. It enables loose coupling between system components while providing powerful features like event priorities, filtering, and history tracking.

## Features

- **Asynchronous publish/subscribe pattern** - Non-blocking event processing with async queue
- **Event priorities** - CRITICAL, HIGH, NORMAL, LOW with filtering capabilities
- **Event history tracking** - Configurable history with pattern filtering and automatic cleanup
- **Synchronous and asynchronous handlers** - Support for both handler types with automatic thread pool execution
- **Wildcard subscriptions** - Glob pattern matching (e.g., "agent.*", "mcp.tool.*")
- **Thread safety** - RLock protection and async queue processing
- **Automatic cleanup** - Weak reference tracking for garbage collection
- **Synchronous publishing** - `publish_sync()` for fire-and-forget event publishing

## Architecture

The event bus uses a queue-based architecture:

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Publisher │───►│  Event Queue │───►│  Processor  │
└─────────────┘    └──────────────┘    └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌──────────────┐    ┌─────────────┐
                    │   History    │    │ Subscribers │
                    └──────────────┘    └─────────────┘
```

## Quick Start

```python
import asyncio
from nagatha_assistant.core.event_bus import get_event_bus, ensure_event_bus_started
from nagatha_assistant.core.event import (
    Event, EventPriority, StandardEventTypes,
    create_system_event, create_agent_event
)

async def main():
    # Start the event bus
    event_bus = await ensure_event_bus_started()
    
    # Subscribe to events
    def my_handler(event):
        print(f"Received: {event.event_type}")
    
    sub_id = event_bus.subscribe("system.*", my_handler)
    
    # Publish an event
    event = create_system_event(
        StandardEventTypes.SYSTEM_STARTUP,
        {"component": "my_component"},
        EventPriority.HIGH
    )
    await event_bus.publish(event)
    
    # Cleanup
    event_bus.unsubscribe(sub_id)
    await event_bus.stop()

asyncio.run(main())
```

## Event Types

### Standard Event Types

The system defines comprehensive standard event types in `StandardEventTypes`:

```python
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

# Memory events
MEMORY_SECTION_CREATED = "memory.section.created"
MEMORY_SECTION_UPDATED = "memory.section.updated"
MEMORY_SECTION_DELETED = "memory.section.deleted"
MEMORY_ENTRY_CREATED = "memory.entry.created"
MEMORY_ENTRY_UPDATED = "memory.entry.updated"
MEMORY_ENTRY_DELETED = "memory.entry.deleted"
MEMORY_SEARCH_PERFORMED = "memory.search.performed"
```

### Custom Events

```python
# Create custom events
custom_event = Event(
    event_type="my_module.custom_action",
    data={"user_id": 123, "action": "login"},
    priority=EventPriority.NORMAL,
    source="auth_module"
)
```

### Event Helper Functions

The system provides helper functions for creating common event types:

```python
# System events
system_event = create_system_event(
    StandardEventTypes.SYSTEM_STARTUP,
    {"timestamp": time.time()},
    EventPriority.HIGH
)

# Agent events
agent_event = create_agent_event(
    StandardEventTypes.AGENT_MESSAGE_RECEIVED,
    session_id=123,
    message_data={"content": "Hello", "role": "user"}
)

# MCP events
mcp_event = create_mcp_event(
    StandardEventTypes.MCP_TOOL_CALLED,
    server_name="firecrawl-mcp",
    tool_data={"tool": "search", "args": {"query": "AI news"}}
)

# Memory events
memory_event = create_memory_event(
    StandardEventTypes.MEMORY_ENTRY_CREATED,
    section_name="user_preferences",
    key="theme",
    memory_data={"value": "dark"}
)
```

## Event Priorities

Events have four priority levels:

- `EventPriority.CRITICAL` (0) - Highest priority
- `EventPriority.HIGH` (1) - High priority  
- `EventPriority.NORMAL` (2) - Default priority
- `EventPriority.LOW` (3) - Lowest priority

Priority filtering allows subscribers to only receive events of a certain priority or higher:

```python
# Only receive HIGH and CRITICAL events
event_bus.subscribe("*", handler, priority_filter=EventPriority.HIGH)
```

## Publishing Events

### Asynchronous Publishing

```python
# Publish and wait for processing
await event_bus.publish(event)
```

### Synchronous Publishing

```python
# Fire-and-forget publishing (creates async task)
event_bus.publish_sync(event)
```

**Note**: `publish_sync()` is useful when you need to publish from synchronous code or don't want to wait for the event to be processed. It creates an async task and returns immediately.

## Subscription Patterns

### Wildcard Patterns

Use glob patterns to subscribe to multiple event types:

```python
# All system events
event_bus.subscribe("system.*", handler)

# All agent message events
event_bus.subscribe("agent.message.*", handler)

# All events (monitoring)
event_bus.subscribe("*", handler)
```

### Filtering

Filter events by priority and source:

```python
# Only high priority events from agent
event_bus.subscribe(
    "agent.*", 
    handler,
    priority_filter=EventPriority.HIGH,
    source_filter="agent"
)
```

### Subscription Management

```python
# Subscribe and get subscription ID
sub_id = event_bus.subscribe("pattern", handler)

# Unsubscribe by ID
event_bus.unsubscribe(sub_id)

# Unsubscribe all subscriptions for a handler
removed_count = event_bus.unsubscribe_handler(handler)

# Get all subscriptions
subscriptions = event_bus.get_subscriptions()
```

## Handler Types

### Async Handlers

```python
async def async_handler(event: Event):
    # Async processing
    await some_async_operation(event.data)
    print(f"Processed: {event.event_type}")

event_bus.subscribe("async.*", async_handler)
```

### Sync Handlers

```python
def sync_handler(event: Event):
    # Sync processing (automatically runs in thread pool)
    process_event_data(event.data)
    print(f"Processed: {event.event_type}")

event_bus.subscribe("sync.*", sync_handler)
```

**Note**: Synchronous handlers are automatically executed in a thread pool to avoid blocking the event processing loop.

## Event History

The event bus maintains a configurable history of all published events:

```python
# Get all history (most recent first)
history = event_bus.get_event_history()

# Get last 10 events
recent = event_bus.get_event_history(limit=10)

# Get only system events
system_events = event_bus.get_event_history(event_type_pattern="system.*")

# Clear history
event_bus.clear_history()
```

### History Configuration

```python
# Create event bus with custom history size
event_bus = EventBus(max_history=5000)  # Default is 1000
```

## Event Bus Lifecycle

### Starting and Stopping

```python
# Start the event bus
await event_bus.start()

# Check if running
if event_bus._running:
    print("Event bus is active")

# Stop the event bus
await event_bus.stop()
```

### Global Event Bus

The system provides a global singleton event bus:

```python
# Get the global event bus
event_bus = get_event_bus()

# Ensure it's started
event_bus = await ensure_event_bus_started()

# Shutdown the global event bus
await shutdown_event_bus()
```

## Integration with Nagatha

The event bus is automatically integrated into the Nagatha application lifecycle:

### Automatic Integration

- **Startup**: Event bus starts with `agent.startup()`
- **Shutdown**: Event bus stops with `agent.shutdown()`
- **Message handling**: Events published for user/agent messages
- **Conversation management**: Events for session start/end

### Automatic Event Publishing

Events are automatically published for:
- System startup/shutdown
- New conversation sessions
- Message received/sent
- MCP server connections
- Database entity changes
- Memory operations
- UI interactions

### Plugin Integration

Plugins can easily integrate with the event bus:

```python
class MyPlugin(BasePlugin):
    async def start(self):
        # Subscribe to events
        self.subscribe_to_events("agent.*", self.handle_agent_event)
        
        # Publish events
        await self.publish_event(create_system_event("plugin.started"))
    
    def handle_agent_event(self, event):
        # Handle agent events
        pass
```

## Advanced Features

### Weak Reference Cleanup

The event bus automatically tracks weak references to handler objects and cleans up subscriptions when objects are garbage collected:

```python
class MyHandler:
    def __init__(self, event_bus):
        # This subscription will be automatically cleaned up when MyHandler is GC'd
        event_bus.subscribe("system.*", self.handle_event)
    
    def handle_event(self, event):
        pass
```

### Error Handling

Event handlers should handle their own errors:

```python
async def safe_handler(event: Event):
    try:
        await process_event(event)
    except Exception as e:
        logger.exception(f"Error processing {event.event_type}: {e}")
```

The event bus will log handler errors but continue processing other handlers.

### Thread Safety

All event bus operations are thread-safe:

```python
# Safe to call from any thread
event_bus.publish_sync(event)
event_bus.subscribe("pattern", handler)
```

## Best Practices

### Event Naming

Use hierarchical naming with dots:
- `system.startup`
- `agent.message.received`
- `mcp.server.connected`
- `ui.notification.error`

### Event Data

Keep event data lightweight and JSON-serializable:

```python
# Good
event_data = {
    "user_id": 123,
    "action": "login",
    "timestamp": datetime.now().isoformat()
}

# Avoid large objects
# event_data = {"large_object": some_big_object}
```

### Performance Considerations

- Use `publish_sync()` for fire-and-forget events
- Keep event data small
- Use appropriate priority levels
- Unsubscribe when done to prevent memory leaks

### Memory Management

```python
# Always unsubscribe when done
sub_id = event_bus.subscribe("pattern", handler)
try:
    # Use the subscription
    pass
finally:
    event_bus.unsubscribe(sub_id)

# Or unsubscribe all for a handler
event_bus.unsubscribe_handler(handler)
```

## Examples

### Complete Working Example

```python
#!/usr/bin/env python3
"""
Complete event bus example demonstrating all features.
"""

import asyncio
import logging
from nagatha_assistant.core.event_bus import get_event_bus, ensure_event_bus_started
from nagatha_assistant.core.event import (
    Event, EventPriority, StandardEventTypes,
    create_system_event, create_agent_event, create_mcp_event
)

async def main():
    # Start the event bus
    event_bus = await ensure_event_bus_started()
    
    # Track received events
    received_events = []
    
    # Define handlers
    async def system_handler(event):
        print(f"🏛️  System: {event.event_type}")
        received_events.append(event)
    
    def agent_handler(event):
        print(f"🤖 Agent: {event.event_type} - Session {event.data.get('session_id')}")
        received_events.append(event)
    
    # Subscribe to events
    system_sub = event_bus.subscribe("system.*", system_handler)
    agent_sub = event_bus.subscribe("agent.*", agent_handler)
    
    # Publish events
    await event_bus.publish(create_system_event(
        StandardEventTypes.SYSTEM_STARTUP,
        {"demo": True}
    ))
    
    event_bus.publish_sync(create_agent_event(
        StandardEventTypes.AGENT_CONVERSATION_STARTED,
        123
    ))
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Show results
    print(f"Received {len(received_events)} events")
    print(f"History: {len(event_bus.get_event_history())} events")
    
    # Cleanup
    event_bus.unsubscribe(system_sub)
    event_bus.unsubscribe(agent_sub)
    await event_bus.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Plugin Integration Example

```python
from nagatha_assistant.core.plugin import BasePlugin
from nagatha_assistant.core.event import create_system_event

class EventAwarePlugin(BasePlugin):
    async def start(self):
        # Subscribe to events
        self.subscribe_to_events("agent.message.*", self.handle_message)
        
        # Publish startup event
        await self.publish_event(create_system_event(
            "plugin.event_aware.started",
            {"plugin_name": self.name}
        ))
    
    def handle_message(self, event):
        session_id = event.data.get("session_id")
        content = event.data.get("content", "")
        print(f"Plugin received message in session {session_id}: {content[:50]}...")
```

## Testing

Run the event system tests:

```bash
pytest tests/test_event_system.py -v
pytest tests/test_event_integration.py -v
```

The test suite includes comprehensive tests covering:
- Event publishing and subscription
- Pattern matching and filtering
- Handler execution (sync and async)
- Event history and cleanup
- Thread safety
- Integration with other components

## Troubleshooting

### Common Issues

**Event not received:**
- Check if event bus is running (`event_bus._running`)
- Verify subscription pattern matches event type
- Check priority and source filters
- Ensure handler is not raising exceptions

**Memory leaks:**
- Always unsubscribe when done
- Use weak references for object-bound handlers
- Monitor subscription count with `event_bus.get_subscriptions()`

**Performance issues:**
- Use appropriate event priorities
- Keep event data small
- Consider using `publish_sync()` for non-critical events
- Monitor event history size

### Debug Mode

Enable debug logging to see event processing:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show detailed information about event publishing, subscription matching, and handler execution.