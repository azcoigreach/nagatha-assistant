# Event Bus System Documentation

## Overview

The Nagatha Assistant Event Bus System provides a central communication mechanism for all components using an asynchronous publish/subscribe pattern.

## Features

- **Asynchronous publish/subscribe pattern** - Non-blocking event processing
- **Event priorities** - CRITICAL, HIGH, NORMAL, LOW with filtering
- **Event history tracking** - Configurable history with pattern filtering  
- **Synchronous and asynchronous handlers** - Support for both handler types
- **Wildcard subscriptions** - Glob pattern matching (e.g., "agent.*", "mcp.tool.*")
- **Thread safety** - RLock protection and async queue processing

## Quick Start

```python
import asyncio
from nagatha_assistant.core import (
    get_event_bus, ensure_event_bus_started,
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

The system defines standard event types in `StandardEventTypes`:

```python
# System events
SYSTEM_STARTUP = "system.startup"
SYSTEM_SHUTDOWN = "system.shutdown"

# Agent events  
AGENT_MESSAGE_RECEIVED = "agent.message.received"
AGENT_MESSAGE_SENT = "agent.message.sent"
AGENT_CONVERSATION_STARTED = "agent.conversation.started"

# MCP events
MCP_SERVER_CONNECTED = "mcp.server.connected"
MCP_TOOL_CALLED = "mcp.tool.called"

# Database events
DB_ENTITY_CREATED = "db.entity.created"
DB_ENTITY_UPDATED = "db.entity.updated"

# And more...
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
    # Sync processing (runs in thread pool)
    process_event_data(event.data)
    print(f"Processed: {event.event_type}")

event_bus.subscribe("sync.*", sync_handler)
```

## Event History

The event bus maintains a history of all published events:

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

## Integration with Nagatha

The event bus is automatically integrated into the Nagatha application lifecycle:

- **Startup**: Event bus starts with `agent.startup()`
- **Shutdown**: Event bus stops with `agent.shutdown()`
- **Message handling**: Events published for user/agent messages
- **Conversation management**: Events for session start/end

Events are automatically published for:
- System startup/shutdown
- New conversation sessions
- Message received/sent
- MCP server connections
- Database entity changes

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

### Error Handling

Event handlers should handle their own errors:

```python
async def safe_handler(event: Event):
    try:
        await process_event(event)
    except Exception as e:
        logger.exception(f"Error processing {event.event_type}: {e}")
```

### Unsubscription

Always unsubscribe when done to prevent memory leaks:

```python
sub_id = event_bus.subscribe("pattern", handler)
# ... later
event_bus.unsubscribe(sub_id)

# Or unsubscribe all for a handler
event_bus.unsubscribe_handler(handler)
```

## Examples

See `demo_event_system.py` for a complete working example demonstrating all features.

## Testing

Run the event system tests:

```bash
pytest tests/test_event_system.py -v
```

The test suite includes 22 comprehensive tests covering all functionality.