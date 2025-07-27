# Celery Task Scheduling Integration

This document describes the Celery task scheduling system integrated into Nagatha Assistant.

## Overview

The Celery integration provides distributed task execution and scheduling capabilities, allowing you to:

- Schedule one-time and recurring tasks
- Use natural language time specifications
- Execute tasks in the background
- Monitor task execution through events
- Manage tasks through CLI commands

## Architecture

### Core Components

1. **Celery Application** (`src/nagatha_assistant/core/celery_app.py`)
   - Main Celery configuration
   - Redis broker setup
   - Task discovery and registration

2. **Task Scheduler** (`src/nagatha_assistant/core/scheduler.py`)
   - High-level scheduling interface
   - Natural language time parsing
   - Integration with event system

3. **Task Definitions** (`src/nagatha_assistant/plugins/tasks.py`)
   - Built-in system tasks
   - Task registry
   - Event emission for task lifecycle

4. **Task Manager Plugin** (`src/nagatha_assistant/plugins/task_manager.py`)
   - Plugin-based task management
   - Command interface
   - Task history tracking

## Installation

### Dependencies

The following packages are required:

```bash
pip install celery redis celery-beat flower parsedatetime
```

### Redis Setup

Redis is required as the message broker. Install and start Redis:

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
redis-server
```

## Usage

### CLI Commands

#### Service Management

Start all Celery services:
```bash
nagatha celery service start --all
```

Start specific services:
```bash
nagatha celery service start --redis --worker --beat
```

Check service status:
```bash
nagatha celery service status
```

Stop services:
```bash
nagatha celery service stop --all
```

#### Task Management

List available tasks:
```bash
nagatha celery task available
```

Schedule a task:
```bash
nagatha celery task schedule "nagatha.system.health_check" "every 5 minutes"
```

Schedule with arguments:
```bash
nagatha celery task schedule "nagatha.system.backup_database" "every day at 2am" --args '["backup_$(date +%Y%m%d).db"]'
```

List scheduled tasks:
```bash
nagatha celery task list
```

Cancel a task:
```bash
nagatha celery task cancel "task_id_here"
```

Clear all tasks:
```bash
nagatha celery task clear
```

#### Task History

View task execution history:
```bash
nagatha celery task history
```

View with filters:
```bash
# Show last 50 entries
nagatha celery task history --limit 50

# Filter by task name
nagatha celery task history --task-name nagatha.system.health_check

# Show only failed tasks
nagatha celery task history --status failed

# Get detailed output
nagatha celery task history --format detailed

# Get JSON output
nagatha celery task history --format json
```

Clear task history:
```bash
nagatha celery task clear-history --confirm
```

#### Testing

Test Celery functionality:
```bash
nagatha celery test
```

Check system health:
```bash
nagatha celery health
```

### Natural Language Scheduling

The scheduler supports natural language time specifications:

#### One-time Tasks
- `"in 5 minutes"`
- `"tomorrow at 9am"`
- `"next monday at 8am"`
- `"2024-01-15 14:30"`

#### Recurring Tasks
- `"every 5 minutes"`
- `"every hour"`
- `"every day at 2pm"`
- `"every monday at 8am"`
- `"every week"`

#### Cron-like Syntax
- `"0 2 * * *"` (daily at 2am)
- `"*/15 * * * *"` (every 15 minutes)
- `"0 9 * * 1"` (every monday at 9am)

### Available Tasks

#### System Tasks
- `nagatha.system.health_check` - System health monitoring
- `nagatha.system.backup_database` - Database backup
- `nagatha.system.cleanup_logs` - Log file cleanup
- `nagatha.system.execute_command` - Execute system commands

#### Memory Tasks
- `nagatha.memory.backup` - Memory data backup
- `nagatha.memory.cleanup` - Memory cleanup

#### Notification Tasks
- `nagatha.notification.send` - Send notifications

### Programmatic Usage

#### Basic Scheduling

```python
from nagatha_assistant.core.scheduler import schedule_task, schedule_one_time, schedule_recurring

# Schedule a task
task_id = schedule_task("nagatha.system.health_check", "every 5 minutes")

# Schedule one-time task
task_id = schedule_one_time("nagatha.system.backup_database", "tomorrow at 2am")

# Schedule recurring task
task_id = schedule_recurring("nagatha.memory.cleanup", "every day at 3am")
```

#### Using the Scheduler

```python
from nagatha_assistant.core.scheduler import get_scheduler

scheduler = get_scheduler()

# Schedule with custom ID
task_id = scheduler.schedule_task(
    "nagatha.system.execute_command",
    "in 10 minutes",
    args=("ls -la",),
    task_id="my_custom_task"
)

# Cancel task
scheduler.cancel_task(task_id)

# List tasks
tasks = scheduler.list_scheduled_tasks()
```

#### Plugin Integration

```python
from nagatha_assistant.plugins.task_manager import TaskManagerPlugin

# Get plugin instance
plugin = TaskManagerPlugin(config)

# Schedule task through plugin
task_id = await plugin.schedule_task("nagatha.system.health_check", "every hour")

# Execute task immediately
task_id = await plugin.execute_task_now("nagatha.system.backup_database")

# Get task status
status = await plugin.get_task_status(task_id)
```

### Event Integration

Tasks emit events that integrate with the existing event system:

- `task.created` - Task scheduled
- `task.updated` - Task status changed
- `task.completed` - Task completed successfully
- `task.failed` - Task failed

```python
from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import StandardEventTypes

event_bus = get_event_bus()

# Listen for task events
@event_bus.on(StandardEventTypes.TASK_COMPLETED)
def on_task_completed(event):
    print(f"Task {event.data['task_id']} completed")
```

## Configuration

### Environment Variables

- `CELERY_BROKER_URL` - Redis broker URL (default: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND` - Result backend URL (default: `redis://localhost:6379/0`)
- `CELERY_BEAT_SCHEDULE_FILE` - Beat schedule file (default: `celerybeat-schedule`)

### Celery Configuration

The Celery app is configured in `src/nagatha_assistant/core/celery_app.py` with:

- JSON serialization
- UTC timezone
- 30-minute task timeout
- 25-minute soft timeout
- 24-hour result expiration
- Auto-discovery of tasks in plugins

## Monitoring

### Flower Web Interface

Flower provides a web-based monitoring interface:

```bash
nagatha celery service start --flower
```

Access at: http://localhost:5555

### Task History

The system automatically tracks task execution history with detailed information:

- **Task Start** - Records when task begins execution
- **Task Completion** - Records successful completion with results
- **Task Failure** - Records failures with error details
- **Timing** - Tracks execution duration
- **Worker Info** - Records which worker executed the task

#### CLI History Commands

```bash
# View recent task history
nagatha celery task history

# Filter by specific criteria
nagatha celery task history --task-name nagatha.system.health_check --status completed

# Get detailed information
nagatha celery task history --format detailed
```

#### Programmatic Access

```python
from nagatha_assistant.core.memory import get_memory_manager

memory = get_memory_manager()
history = await memory.get('system', 'task_history', default=[])
```

The TaskManagerPlugin also provides task history access:

```python
plugin = TaskManagerPlugin(config)
history = await plugin.get_task_history(limit=10)
```

### Logging

Celery uses the standard Python logging system. Configure log levels:

```bash
nagatha --log-level INFO celery service start --worker
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Ensure Redis is running: `redis-cli ping`
   - Check Redis URL in environment variables

2. **Task Not Executing**
   - Verify worker is running: `nagatha celery service status`
   - Check task is properly scheduled: `nagatha celery task list`

3. **Import Errors**
   - Ensure all dependencies are installed
   - Check Python path includes the project root

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
nagatha celery service start --worker
```

### Manual Testing

Test individual components:

```bash
# Test Redis
redis-cli ping

# Test Celery
nagatha celery test

# Test scheduling
nagatha celery task schedule "nagatha.system.health_check" "in 1 minute"
```

## Development

### Adding Custom Tasks

1. Create task function in `src/nagatha_assistant/plugins/tasks.py`:

```python
@celery_app.task(bind=True, name='nagatha.custom.my_task')
def my_custom_task(self, arg1, arg2):
    # Task implementation
    return {"result": "success"}
```

2. Register in task registry:

```python
TASK_REGISTRY = {
    # ... existing tasks
    'custom.my_task': my_custom_task,
}
```

### Plugin Integration

Plugins can register custom tasks:

```python
class MyPlugin(BasePlugin):
    async def on_start(self):
        # Register custom task
        from nagatha_assistant.core.celery_app import celery_app
        
        @celery_app.task(bind=True, name='nagatha.plugin.my_task')
        def plugin_task(self):
            return {"plugin": "task"}
```

## Security Considerations

- Tasks run with the same permissions as the Nagatha process
- Validate task arguments before execution
- Use task timeouts to prevent hanging tasks
- Monitor task execution for resource usage
- Consider using separate Redis databases for different environments 