# Nagatha Assistant Task Scheduler

The Task Scheduler is a powerful component of Nagatha Assistant that allows you to schedule and execute tasks at specified times or intervals. It uses Celery and Redis for distributed task execution and supports both one-time and recurring tasks.

## Features

### 🔧 Task Types
- **MCP Tool Calls**: Schedule calls to Model Context Protocol servers
- **Plugin Commands**: Schedule execution of plugin commands
- **Notifications**: Schedule system notifications
- **Shell Commands**: Schedule execution of shell commands
- **Task Sequences**: Execute multiple tasks with dependencies

### ⏰ Scheduling Options
- **Natural Language**: "in 30 minutes", "tomorrow", "next week"
- **Cron Expressions**: "0 9 * * *" (daily at 9 AM), "*/5 * * * *" (every 5 minutes)
- **ISO Datetime**: "2025-07-27T14:30:00Z"

### 📊 Management Features
- Task persistence across restarts
- Task status tracking and monitoring
- Event-based notifications
- Task cancellation and rescheduling
- Execution history and audit trail

## Quick Start

### 1. Start Redis and Celery Services

Using Docker Compose (recommended):
```bash
docker-compose -f docker-compose.scheduler.yml up -d
```

Or manually:
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start Celery Worker
celery -A nagatha_assistant.plugins.celery_app worker --loglevel=info

# Start Celery Beat (for recurring tasks)
celery -A nagatha_assistant.plugins.celery_app beat --loglevel=info
```

### 2. Schedule Your First Task

Using the CLI:
```bash
# Schedule a notification
python -m nagatha_assistant.cli scheduler schedule notification "in 5 minutes" --message "Hello from scheduler!"

# Schedule a recurring daily reminder
python -m nagatha_assistant.cli scheduler schedule notification "0 9 * * *" --message "Daily standup time!"

# Schedule an MCP tool call
python -m nagatha_assistant.cli scheduler schedule mcp_tool "tomorrow at 2pm" --server-name time --tool-name get_current_time
```

### 3. Manage Your Tasks

```bash
# List all scheduled tasks
python -m nagatha_assistant.cli scheduler list

# Show detailed task information
python -m nagatha_assistant.cli scheduler info <task_id>

# Cancel a task
python -m nagatha_assistant.cli scheduler cancel <task_id>
```

## Programming Interface

### Basic Usage

```python
from nagatha_assistant.plugins.scheduler import get_scheduler

# Get the scheduler instance
scheduler = get_scheduler()

# Schedule a notification
task_id = await scheduler.schedule_notification(
    message="Meeting reminder",
    schedule_spec="in 30 minutes",
    notification_type="info"
)

# Schedule an MCP tool call
task_id = await scheduler.schedule_mcp_tool(
    server_name="time",
    tool_name="get_current_time",
    arguments={},
    schedule_spec="0 9 * * *"  # Daily at 9 AM
)

# Cancel a task
await scheduler.cancel_task(task_id)
```

### Plugin Integration

```python
from nagatha_assistant.core.plugin import SimplePlugin
from nagatha_assistant.plugins.scheduler import get_scheduler

class MyPlugin(SimplePlugin):
    async def setup(self):
        scheduler = get_scheduler()
        
        # Schedule a recurring task
        await scheduler.schedule_plugin_command(
            plugin_name=self.name,
            command_name="daily_cleanup",
            arguments={},
            schedule_spec="0 2 * * *",  # Daily at 2 AM
            task_name="Daily Cleanup"
        )
```

## Natural Language Examples

The scheduler supports intuitive natural language time expressions:

- `"in 30 minutes"` - 30 minutes from now
- `"in 2 hours"` - 2 hours from now
- `"tomorrow"` - Next day at the same time
- `"next week"` - Next week at the same time
- `"at 14:30"` - Today at 2:30 PM (or tomorrow if time has passed)

## Cron Expression Examples

Standard cron expressions are supported:

- `"0 9 * * *"` - Daily at 9:00 AM
- `"*/5 * * * *"` - Every 5 minutes
- `"0 0 * * 0"` - Weekly on Sunday at midnight
- `"0 12 1 * *"` - Monthly on the 1st at noon
- `"0 9 * * 1-5"` - Weekdays at 9:00 AM

## Event Integration

The scheduler integrates with Nagatha's event system:

### Event Types
- `scheduler.task.scheduled` - When a task is scheduled
- `scheduler.task.success` - When a task completes successfully
- `scheduler.task.failure` - When a task fails
- `scheduler.task.retry` - When a task is retried
- `scheduler.task.cancelled` - When a task is cancelled

### Event Handling

```python
from nagatha_assistant.core.event_bus import get_event_bus

event_bus = get_event_bus()

async def handle_task_success(event):
    task_id = event.data["task_id"]
    print(f"Task {task_id} completed successfully!")

event_bus.subscribe("scheduler.task.success", handle_task_success)
```

## Database Models

The scheduler uses two main database models:

### ScheduledTask
- Stores task configuration and scheduling information
- Tracks status, execution counts, and error handling
- Supports metadata like creation time and user attribution

### TaskExecution
- Records individual task executions
- Stores results, errors, and performance metrics
- Provides full audit trail for debugging and monitoring

## Monitoring

### CLI Commands
```bash
# List tasks by status
python -m nagatha_assistant.cli scheduler list --status scheduled
python -m nagatha_assistant.cli scheduler list --status failed

# View detailed task information
python -m nagatha_assistant.cli scheduler info <task_id>
```

### Flower Web Interface
When using Docker Compose, Flower provides a web interface at http://localhost:5555 for monitoring Celery tasks.

### Event Monitoring
Subscribe to scheduler events to implement custom monitoring:

```python
event_bus.subscribe("scheduler.task.*", your_monitoring_handler)
```

## Configuration

### Environment Variables

- `CELERY_BROKER_URL` - Redis broker URL (default: redis://localhost:6379/0)
- `CELERY_RESULT_BACKEND` - Redis result backend URL (default: redis://localhost:6379/0)

### Celery Configuration

The scheduler is configured with sensible defaults:
- JSON serialization for cross-platform compatibility
- Task acknowledgment after completion for reliability
- 5-minute soft timeout, 10-minute hard timeout
- 3 retry attempts with exponential backoff

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```
   Solution: Ensure Redis is running on localhost:6379 or update CELERY_BROKER_URL
   ```

2. **Tasks Not Executing**
   ```
   Solution: Check that Celery worker is running and connected to Redis
   ```

3. **Beat Schedule Not Working**
   ```
   Solution: Ensure Celery Beat is running for recurring tasks
   ```

### Debug Mode

Set log level to DEBUG for detailed information:
```bash
export LOG_LEVEL=DEBUG
python -m nagatha_assistant.cli scheduler list
```

### Testing

Run the demonstration script to test functionality:
```bash
# Basic tests (no external dependencies)
python demo_scheduler.py --basic

# Full demonstration (requires Redis)
python demo_scheduler.py
```

## Advanced Usage

### Task Dependencies

```python
# Schedule a sequence of tasks
task_definitions = [
    {"type": "notification", "args": {"message": "Starting backup"}},
    {"type": "shell_command", "args": {"command": "backup.sh"}},
    {"type": "notification", "args": {"message": "Backup complete"}}
]

await scheduler.schedule_task(
    task_type="sequence",
    task_args={"task_definitions": task_definitions},
    schedule_spec="0 2 * * *"  # Daily at 2 AM
)
```

### Custom Task Types

Extend the scheduler by adding new task types to `tasks.py`:

```python
@app.task(base=NagathaTask, bind=True)
def my_custom_task(self, custom_arg: str) -> Dict[str, Any]:
    # Your custom task logic here
    pass

# Register in AVAILABLE_TASKS
AVAILABLE_TASKS["my_custom"] = my_custom_task
```

## API Reference

See the docstrings in `src/nagatha_assistant/plugins/scheduler.py` for detailed API documentation.

## Contributing

When adding new features to the scheduler:

1. Add tests to `tests/test_scheduler_basic.py`
2. Update this documentation
3. Consider event integration for monitoring
4. Test with both one-time and recurring schedules