# Celery Integration Guide

This document explains how to use the new Celery-based event system in Nagatha Assistant.

## Overview

Nagatha Assistant now uses Celery for distributed task processing and event management. This provides several benefits:

- **Scalability**: Tasks can be distributed across multiple workers
- **Reliability**: Task retry mechanisms and failure handling
- **Monitoring**: Built-in monitoring and management tools
- **Scheduling**: Periodic tasks with Celery Beat
- **Persistence**: Redis-based storage for events and session data

## Architecture

### Components

1. **Celery App** (`src/nagatha_assistant/celery_app.py`)
   - Main Celery application configuration
   - Task routing and worker settings
   - Beat schedule configuration

2. **Task Definitions** (`src/nagatha_assistant/core/celery_tasks.py`)
   - Agent message processing
   - MCP tool calls
   - System maintenance
   - Event processing

3. **Event System** (`src/nagatha_assistant/core/celery_event_bus.py`)
   - Celery-based event bus
   - Compatible with original event bus API
   - Distributed event processing

4. **Storage Layer** (`src/nagatha_assistant/core/celery_event_storage.py`)
   - Redis-based event and session storage
   - High-performance data operations
   - Event history and subscription management

5. **Compatibility Layer** (`src/nagatha_assistant/core/celery_storage.py`)
   - Gradual migration support
   - Fallback to SQLAlchemy when needed
   - Dual backend operations

## Setup and Installation

### Prerequisites

1. **Redis Server**
   ```bash
   # Install Redis (Ubuntu/Debian)
   sudo apt-get install redis-server
   
   # Start Redis
   sudo systemctl start redis-server
   ```

2. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables

Set these environment variables for Celery configuration:

```bash
# Redis connection (default: redis://localhost:6379/0)
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"

# Optional Redis URL (legacy compatibility)
export REDIS_URL="redis://localhost:6379/0"
```

## Running the System

### Quick Start

1. **Start all Celery processes:**
   ```bash
   ./start_celery.sh
   ```
   This starts the worker, beat scheduler, and flower monitoring.

2. **Start individual components:**
   ```bash
   # Worker only
   ./start_celery.sh worker
   
   # Beat scheduler only
   ./start_celery.sh beat
   
   # Monitoring only
   ./start_celery.sh flower
   ```

3. **Test the integration:**
   ```bash
   ./start_celery.sh test
   ```

### Manual Commands

```bash
# Start Celery worker
celery -A nagatha_assistant.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A nagatha_assistant.celery_app beat --loglevel=info

# Start Celery flower (monitoring)
celery -A nagatha_assistant.celery_app flower --port=5555
```

## Usage

### Event System

The new event system maintains API compatibility:

```python
from nagatha_assistant.core.celery_storage import get_event_bus, ensure_event_bus_started
from nagatha_assistant.core.event import Event, EventPriority

# Get event bus (automatically uses Celery if available)
event_bus = get_event_bus()

# Start the event bus
await ensure_event_bus_started()

# Publish events
event = Event(
    event_type="my.custom.event",
    data={"message": "Hello from Celery!"},
    priority=EventPriority.NORMAL,
    source="my_app"
)
await event_bus.publish(event)

# Subscribe to events
def my_handler(event):
    print(f"Received event: {event.event_type}")

subscription_id = event_bus.subscribe("my.custom.*", my_handler)
```

### Task Processing

Direct task calls:

```python
from nagatha_assistant.core.celery_tasks import process_message_task, publish_event_task

# Process a message asynchronously
task = process_message_task.delay(session_id=1, message_content="Hello!", message_type="user")

# Get result (blocking)
result = task.get(timeout=60)

# Publish event as task
publish_event_task.delay("my.event", {"data": "value"})
```

### Agent Integration

Using the new Celery-based agent functions:

```python
from nagatha_assistant.core.agent import send_message_via_celery, start_session

# Create session
session_id = await start_session()

# Send message (uses Celery processing)
response = await send_message_via_celery(session_id, "Hello, Nagatha!")
```

### Storage Operations

The compatibility layer provides seamless access:

```python
from nagatha_assistant.core.celery_storage import (
    create_session_async, store_message_async, get_session_messages_async
)

# Create session
session_id = await create_session_async("user123")

# Store message
message_id = await store_message_async(session_id, "Hello!", "user")

# Get messages
messages = await get_session_messages_async(session_id)
```

## Monitoring

### Celery Flower

Access the web-based monitoring at: http://localhost:5555

Features:
- Real-time task monitoring
- Worker status and statistics
- Task history and results
- Queue management

### Logs

Monitor logs for debugging:

```bash
# Worker logs
celery -A nagatha_assistant.celery_app worker --loglevel=debug

# Beat logs
celery -A nagatha_assistant.celery_app beat --loglevel=debug
```

### Redis CLI

Monitor Redis directly:

```bash
redis-cli monitor
redis-cli info
redis-cli keys "*"
```

## Periodic Tasks

The system includes several scheduled tasks:

- **System Health Check** (every 5 minutes)
- **Data Cleanup** (daily at 2 AM)
- **MCP Server Refresh** (every 30 minutes)
- **System Status Publishing** (hourly)
- **Memory Optimization** (every 6 hours)
- **Stale Session Check** (hourly)

Configure additional tasks in `src/nagatha_assistant/core/celery_beat.py`.

## Migration Guide

### Gradual Migration

The system supports gradual migration from the old event system:

1. **Start with compatibility layer**: Existing code continues to work
2. **Update critical paths**: Convert high-traffic operations first
3. **Test thoroughly**: Use the test script to validate functionality
4. **Monitor performance**: Watch for improvements in scalability

### Code Changes

Minimal changes required for existing code:

```python
# Old import
from nagatha_assistant.core.event_bus import get_event_bus

# New import (automatic fallback)
from nagatha_assistant.core.celery_storage import get_event_bus
```

Agent functions now have Celery variants:

```python
# Old
response = await send_message(session_id, message)

# New (with fallback)
response = await send_message_via_celery(session_id, message)
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```
   Error: Redis connection failed
   ```
   - Check if Redis is running: `redis-cli ping`
   - Verify connection URL: `CELERY_BROKER_URL`

2. **No Workers Available**
   ```
   Error: No workers available
   ```
   - Start Celery worker: `./start_celery.sh worker`
   - Check worker status in Flower: http://localhost:5555

3. **Task Timeout**
   ```
   Error: Task timeout
   ```
   - Increase timeout in `celery_app.py`
   - Check worker logs for performance issues

4. **Import Errors**
   ```
   ModuleNotFoundError: No module named 'nagatha_assistant'
   ```
   - Set PYTHONPATH: `export PYTHONPATH="$PWD/src:$PYTHONPATH"`
   - Use absolute imports in code

### Performance Tuning

1. **Worker Concurrency**
   ```bash
   celery -A nagatha_assistant.celery_app worker --concurrency=8
   ```

2. **Queue Priorities**
   ```python
   # High priority queue for critical tasks
   task.apply_async(queue='agent', priority=9)
   ```

3. **Redis Configuration**
   ```
   # /etc/redis/redis.conf
   maxmemory 2gb
   maxmemory-policy allkeys-lru
   ```

## Best Practices

1. **Task Design**
   - Keep tasks small and focused
   - Use idempotent operations
   - Handle exceptions gracefully

2. **Event Patterns**
   - Use descriptive event types
   - Include relevant context in event data
   - Consider event ordering requirements

3. **Error Handling**
   - Implement retry logic for transient failures
   - Log errors with sufficient context
   - Use dead letter queues for failed tasks

4. **Monitoring**
   - Monitor queue lengths
   - Track task execution times
   - Set up alerts for failures

## Integration with Django Dashboard

The Django web dashboard automatically uses the Celery system:

```python
# In Django views
from nagatha_assistant.core.celery_tasks import process_message_task

def chat_view(request):
    task = process_message_task.delay(
        session_id=request.session['session_id'],
        message_content=request.POST['message'],
        message_type='user'
    )
    return JsonResponse({'task_id': task.id})
```

Monitor task progress:

```python
from celery.result import AsyncResult

def task_status(request, task_id):
    result = AsyncResult(task_id)
    return JsonResponse({
        'status': result.status,
        'result': result.result
    })
```

## Support

For issues or questions:

1. Check the logs for error details
2. Run the integration test: `./start_celery.sh test`
3. Verify Redis connectivity
4. Check worker status in Flower
5. Review this documentation for configuration options