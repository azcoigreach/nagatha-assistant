# Nagatha Core Features Integration with Celery Platform

This document describes the implementation of issue #43: "Plan: Integrate Nagatha Core Features with Celery Platform". This integration provides a robust bridge between Nagatha's async-first core architecture and Django's Celery task queue system.

## Overview

The integration consists of several key components:

1. **NagathaCeleryBridge** - Async/sync bridge for Celery tasks
2. **Enhanced Celery Tasks** - Core Nagatha functionality as Celery tasks
3. **Scheduled Tasks** - Periodic operations via Celery Beat
4. **API Endpoints** - Web interface for the integrated functionality
5. **Management Commands** - Testing and administration tools

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django Web    │    │   Celery        │    │   Nagatha       │
│   Dashboard     │    │   Tasks         │    │   Core          │
│                 │    │                 │    │                 │
│  API Endpoints  │◄──►│  Task Queue     │◄──►│  Agent         │
│  Views          │    │  Beat Scheduler │    │  MCP Manager   │
│  Templates      │    │  Workers        │    │  Memory        │
│                 │    │                 │    │  Plugins       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Redis         │
                       │   Broker        │
                       │   Backend       │
                       └─────────────────┘
```

## Key Components

### 1. NagathaCeleryBridge

The `NagathaCeleryBridge` class in `web_dashboard/dashboard/nagatha_celery_integration.py` provides:

- **Async/Sync Conversion**: Handles the conversion between Celery's sync environment and Nagatha's async core
- **Component Management**: Manages initialization of Nagatha's core components (agent, MCP manager, memory, etc.)
- **Error Handling**: Provides robust error handling and fallback mechanisms
- **Resource Management**: Ensures proper cleanup and resource management

```python
# Example usage
bridge = get_nagatha_bridge()
result = bridge._run_async(bridge.process_message_async(session_id, message))
```

### 2. Core Celery Tasks

The integration provides the following Celery tasks:

#### Message Processing
- **`process_message_with_nagatha`**: Process user messages using Nagatha's core agent
- **Features**: Full conversation context, MCP tool integration, memory persistence

#### MCP Server Management
- **`check_mcp_servers_health`**: Periodic health checks of MCP servers
- **`reload_mcp_configuration`**: Reload MCP server configurations
- **Features**: Connection testing, tool discovery, status reporting

#### Memory Management
- **`cleanup_memory_and_maintenance`**: Memory cleanup and maintenance tasks
- **Features**: Expired entry cleanup, statistics collection, optimization

#### Usage Tracking
- **`track_usage_metrics`**: Track API usage and costs
- **Features**: Token counting, cost calculation, usage analytics

#### Scheduled Tasks
- **`process_scheduled_tasks`**: Process due tasks and reminders
- **Features**: Task notifications, reminder delivery, scheduling

### 3. Scheduled Tasks (Celery Beat)

The integration includes comprehensive scheduled tasks:

```python
CELERY_BEAT_SCHEDULE = {
    # MCP Server Health Checks - Every 5 minutes
    'check-mcp-servers-health': {
        'task': 'dashboard.nagatha_celery_integration.check_mcp_servers_health',
        'schedule': 300.0,
    },
    
    # Memory Cleanup and Maintenance - Every hour
    'cleanup-memory-and-maintenance': {
        'task': 'dashboard.nagatha_celery_integration.cleanup_memory_and_maintenance',
        'schedule': 3600.0,
    },
    
    # Usage Metrics Tracking - Every 15 minutes
    'track-usage-metrics': {
        'task': 'dashboard.nagatha_celery_integration.track_usage_metrics',
        'schedule': 900.0,
    },
    
    # Scheduled Tasks and Reminders - Every minute
    'process-scheduled-tasks': {
        'task': 'dashboard.nagatha_celery_integration.process_scheduled_tasks',
        'schedule': 60.0,
    },
}
```

## API Endpoints

### Message Processing

#### Standard Message Processing (Redis-based)
```
POST /api/send-message/
{
    "message": "Hello Nagatha",
    "session_id": "optional-session-id"
}
```

#### Nagatha Core Message Processing
```
POST /api/send-message-nagatha-core/
{
    "message": "Hello Nagatha",
    "session_id": "optional-session-id"
}
```

**Response:**
```json
{
    "success": true,
    "task_id": "celery-task-id",
    "session_id": "session-id",
    "user_message_id": "message-id",
    "message": "Message processing started with Nagatha core",
    "integration_type": "nagatha_core"
}
```

### Task Status
```
GET /api/task-status/{task_id}/
```

### System Status
```
GET /api/system-status/
```

## Management Commands

### Test Integration
```bash
# Test all integration components
python manage.py test_nagatha_integration

# Test specific components
python manage.py test_nagatha_integration --task message
python manage.py test_nagatha_integration --task mcp
python manage.py test_nagatha_integration --task memory
python manage.py test_nagatha_integration --task usage
python manage.py test_nagatha_integration --task scheduled
python manage.py test_nagatha_integration --task reload

# Test with custom message
python manage.py test_nagatha_integration --task message --message "Custom test message"
```

## Configuration

### Environment Variables

The integration uses the following environment variables:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key
DJANGO_SECRET_KEY=your-django-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost/nagatha_dashboard
NAGATHA_DATABASE_URL=sqlite:///nagatha.db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO
```

### Docker Configuration

The integration is fully compatible with the existing Docker setup:

```yaml
# docker-compose.yml
services:
  web:
    # Django web application
    command: gunicorn --bind 0.0.0.0:8000 web_dashboard.wsgi:application
  
  celery:
    # Celery worker for background tasks
    command: celery -A web_dashboard worker --loglevel=info --concurrency=2
  
  celery-beat:
    # Celery Beat for scheduled tasks
    command: celery -A web_dashboard beat --loglevel=info
```

## Usage Examples

### 1. Process a Message with Nagatha Core

```python
from dashboard.nagatha_celery_integration import process_message_with_nagatha

# Start message processing
result = process_message_with_nagatha.delay(
    session_id=123,
    message="What's the weather like today?",
    user_id="user123"
)

# Get result
response = result.get(timeout=60)
print(f"Response: {response}")
```

### 2. Check MCP Server Health

```python
from dashboard.nagatha_celery_integration import check_mcp_servers_health

# Check MCP servers
result = check_mcp_servers_health.delay()
health_status = result.get(timeout=30)

if health_status['success']:
    print(f"MCP servers: {health_status['mcp_status']}")
else:
    print(f"Health check failed: {health_status['error']}")
```

### 3. Track Usage Metrics

```python
from dashboard.nagatha_celery_integration import track_usage_metrics

# Track usage
result = track_usage_metrics.delay()
usage_data = result.get(timeout=30)

if usage_data['success']:
    print(f"Total cost: ${usage_data['total_cost']}")
    print(f"Total requests: {usage_data['total_requests']}")
```

## Error Handling

The integration includes comprehensive error handling:

### 1. Initialization Errors
- Graceful fallback when Nagatha core components fail to initialize
- Detailed error logging for debugging
- Fallback to Redis-based adapter when core integration fails

### 2. Task Execution Errors
- Task state tracking in Django models
- Error messages stored for debugging
- Automatic retry mechanisms for transient failures

### 3. Async/Sync Conversion Errors
- Proper event loop management
- Resource cleanup on errors
- Fallback responses when async operations fail

## Monitoring and Debugging

### 1. Task Monitoring
- All tasks are tracked in the Django `Task` model
- Task status, progress, and results are stored
- Error messages and stack traces are preserved

### 2. Logging
- Comprehensive logging at all levels
- Structured logging for easy parsing
- Separate log levels for different components

### 3. Health Checks
- System status endpoint for monitoring
- MCP server health monitoring
- Memory and resource usage tracking

## Performance Considerations

### 1. Async/Sync Overhead
- Each Celery task creates a new event loop
- Consider batching operations where possible
- Monitor memory usage with frequent task execution

### 2. Database Connections
- Proper connection pooling for database operations
- Connection cleanup in task completion
- Monitor connection limits in production

### 3. Redis Usage
- Monitor Redis memory usage
- Configure appropriate TTL for task results
- Consider Redis persistence for critical data

## Security Considerations

### 1. API Security
- CSRF protection on API endpoints
- User authentication and authorization
- Input validation and sanitization

### 2. Task Security
- Task result isolation between users
- Secure handling of sensitive data
- Proper cleanup of temporary data

### 3. Environment Security
- Secure storage of API keys
- Environment variable protection
- Network security for Redis and database connections

## Troubleshooting

### Common Issues

#### 1. Import Errors
```
ModuleNotFoundError: No module named 'nagatha_assistant'
```
**Solution**: Ensure the Nagatha source directory is in the Python path and the module is properly installed.

#### 2. Async/Sync Issues
```
RuntimeError: There is no current event loop in thread
```
**Solution**: The integration handles this automatically, but ensure you're using the bridge methods correctly.

#### 3. MCP Connection Issues
```
ConnectionError: Failed to connect to MCP server
```
**Solution**: Check MCP server configuration and network connectivity.

#### 4. Memory Issues
```
MemoryError: Out of memory
```
**Solution**: Monitor memory usage and adjust Celery worker concurrency.

### Debug Commands

```bash
# Check Celery worker status
celery -A web_dashboard inspect active

# Check scheduled tasks
celery -A web_dashboard inspect scheduled

# Monitor task queue
celery -A web_dashboard monitor

# Check Redis connection
redis-cli ping

# Test Nagatha integration
python manage.py test_nagatha_integration --task all
```

## Future Enhancements

### 1. Advanced Scheduling
- Dynamic task scheduling based on usage patterns
- Intelligent retry mechanisms
- Priority-based task processing

### 2. Enhanced Monitoring
- Real-time dashboard for task monitoring
- Performance metrics and alerts
- Automated health checks and recovery

### 3. Scalability Improvements
- Horizontal scaling of Celery workers
- Load balancing across multiple instances
- Distributed task processing

### 4. Integration Extensions
- Webhook support for external integrations
- Plugin system for custom task types
- Advanced event-driven architecture

## Conclusion

The Nagatha Core Features Integration with Celery Platform provides a robust, scalable solution for integrating Nagatha's async-first architecture with Django's task queue system. The implementation addresses all the requirements outlined in issue #43 and provides a solid foundation for future enhancements.

The integration maintains backward compatibility with existing Redis-based functionality while providing access to the full power of Nagatha's core features through a clean, well-documented API. 