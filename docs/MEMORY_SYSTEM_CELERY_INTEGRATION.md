# Nagatha Memory System Integration with Celery

## Overview

Nagatha's memory system is designed to provide intelligent, persistent storage that works seamlessly with Celery for background operations. This document explains how the memory system works, its integration with Celery, and how to use it effectively.

## Memory System Architecture

### Hybrid Storage Strategy

Nagatha uses a **hybrid storage approach** that combines the best of both worlds:

#### **Redis (Short-term/Fast Access)**
- **Session state** - Current conversation context
- **Temporary data** - Cache, intermediate results
- **User preferences** - Frequently accessed settings
- **Real-time data** - Active session information

#### **SQLite (Long-term/Persistent)**
- **Facts** - Long-term knowledge and information
- **Command history** - Historical interactions
- **Permanent preferences** - Core user settings
- **Cross-session data** - Information that persists across sessions

### Memory Sections

The memory system is organized into logical sections:

```python
SECTIONS = {
    "user_preferences": MemorySection("user_preferences", PersistenceLevel.PERMANENT),
    "session_state": MemorySection("session_state", PersistenceLevel.SESSION),
    "command_history": MemorySection("command_history", PersistenceLevel.PERMANENT),
    "facts": MemorySection("facts", PersistenceLevel.PERMANENT),
    "temporary": MemorySection("temporary", PersistenceLevel.TEMPORARY),
}
```

## Celery Integration

### Background Memory Operations

Celery tasks handle memory operations that would otherwise block the main application:

#### **1. Memory Cleanup and Maintenance**
```python
@shared_task(bind=True)
def cleanup_memory_and_maintenance(self):
    """Clean up expired entries and perform maintenance."""
```

**Operations:**
- Remove expired temporary data
- Clean up old session state
- Optimize storage efficiency
- Update memory statistics

#### **2. Memory Optimization**
```python
@shared_task(bind=True)
def optimize_memory_storage(self):
    """Optimize memory storage and perform advanced maintenance."""
```

**Operations:**
- Consolidate duplicate facts
- Remove redundant entries
- Compress memory data
- Analyze memory usage patterns

#### **3. Database Synchronization**
```python
@shared_task(bind=True)
def sync_memory_to_database(self):
    """Sync Redis memory to SQLite database for long-term persistence."""
```

**Operations:**
- Sync Redis data to SQLite
- Ensure data consistency
- Backup critical information
- Maintain data integrity

#### **4. Memory Analytics**
```python
@shared_task(bind=True)
def get_memory_analytics(self):
    """Get comprehensive memory analytics and insights."""
```

**Operations:**
- Generate usage statistics
- Analyze memory growth patterns
- Identify optimization opportunities
- Monitor storage efficiency

### Scheduled Memory Tasks

The system includes scheduled tasks for regular maintenance:

```python
CELERY_BEAT_SCHEDULE = {
    # Memory cleanup - Every hour
    'cleanup-memory-and-maintenance': {
        'task': 'dashboard.nagatha_celery_integration.cleanup_memory_and_maintenance',
        'schedule': 3600.0,
    },
    
    # Memory optimization - Every 6 hours
    'optimize-memory-storage': {
        'task': 'dashboard.nagatha_celery_integration.optimize_memory_storage',
        'schedule': 21600.0,
    },
    
    # Database sync - Every 30 minutes
    'sync-memory-to-database': {
        'task': 'dashboard.nagatha_celery_integration.sync_memory_to_database',
        'schedule': 1800.0,
    },
}
```

## How Memory Works with Celery

### **1. Fast Access Pattern**
```
User Request → Redis (Fast) → Response
                ↓
            Background Sync → SQLite (Persistent)
```

### **2. Long-term Storage Pattern**
```
User Request → SQLite (Persistent) → Response
                ↓
            Background Cache → Redis (Fast)
```

### **3. Hybrid Access Pattern**
```
User Request → Check Redis → If not found → Check SQLite → Cache in Redis → Response
```

## Memory Operations in Practice

### **Storing Information**

```python
# Store user preference (Redis + SQLite)
await memory_manager.set_user_preference("theme", "dark")

# Store session state (Redis only)
await memory_manager.set_session_state(session_id, "current_topic", "AI discussion")

# Store fact (SQLite only)
await memory_manager.store_fact("python_version", "Python 3.11 is the latest stable version")

# Store temporary data (Redis with TTL)
await memory_manager.set_temporary("search_results", results, ttl_seconds=3600)
```

### **Retrieving Information**

```python
# Get user preference (fast from Redis)
theme = await memory_manager.get_user_preference("theme", default="light")

# Get session state (fast from Redis)
topic = await memory_manager.get_session_state(session_id, "current_topic")

# Get fact (from SQLite, cached in Redis)
fact = await memory_manager.get_fact("python_version")

# Search facts (searches both Redis and SQLite)
results = await memory_manager.search_facts("Python")
```

### **Background Operations**

```python
# Trigger memory optimization
from dashboard.nagatha_celery_integration import optimize_memory_storage
task = optimize_memory_storage.delay()

# Get memory analytics
from dashboard.nagatha_celery_integration import get_memory_analytics
analytics_task = get_memory_analytics.delay()

# Manual database sync
from dashboard.nagatha_celery_integration import sync_memory_to_database
sync_task = sync_memory_to_database.delay()
```

## Memory Lifecycle Management

### **Automatic Cleanup**

The system automatically manages memory lifecycle:

1. **Temporary Data**: Automatically expires based on TTL
2. **Session Data**: Cleaned up when sessions end
3. **Duplicate Facts**: Consolidated during optimization
4. **Expired Entries**: Removed during cleanup tasks

### **Data Persistence Strategy**

- **Critical Data**: Stored in both Redis and SQLite
- **Frequently Accessed**: Cached in Redis, persisted in SQLite
- **Temporary Data**: Stored only in Redis with TTL
- **Historical Data**: Stored only in SQLite

## Performance Considerations

### **Redis Benefits**
- **Fast Access**: Sub-millisecond response times
- **Async Compatible**: Works perfectly with Celery
- **TTL Support**: Automatic expiration
- **Memory Efficient**: Optimized for speed

### **SQLite Benefits**
- **Reliable Persistence**: ACID compliance
- **Data Integrity**: Transaction support
- **Long-term Storage**: No size limitations
- **Complex Queries**: Full SQL support

### **Hybrid Benefits**
- **Best Performance**: Fast access + reliable storage
- **Scalability**: Can handle large datasets
- **Flexibility**: Choose storage based on data type
- **Reliability**: Redundant storage for critical data

## Troubleshooting Memory Issues

### **Common Problems**

1. **Memory Not Accessible**
   - Check if memory tables exist in database
   - Verify Redis connection
   - Check Celery worker status

2. **Slow Memory Access**
   - Check Redis performance
   - Monitor database queries
   - Review memory optimization tasks

3. **Data Loss**
   - Check sync task status
   - Verify backup procedures
   - Review error logs

### **Debugging Commands**

```python
# Check memory statistics
from nagatha_assistant.core.memory import get_memory_manager
manager = get_memory_manager()
stats = await manager.get_storage_stats()
print(stats)

# Test memory operations
await manager.set("test", "key", "value")
value = await manager.get("test", "key")
print(f"Retrieved: {value}")

# Check Celery task status
from dashboard.models import Task
tasks = Task.objects.filter(task_name__contains='memory').order_by('-created_at')[:5]
for task in tasks:
    print(f"{task.task_name}: {task.status}")
```

## Best Practices

### **1. Choose Appropriate Storage**
- Use Redis for frequently accessed data
- Use SQLite for long-term storage
- Use hybrid approach for critical data

### **2. Set Appropriate TTL**
- Temporary data: 1 hour to 1 day
- Session data: Session duration
- Cache data: Based on update frequency

### **3. Monitor Memory Usage**
- Track memory growth patterns
- Monitor cleanup task performance
- Review optimization results

### **4. Regular Maintenance**
- Run optimization tasks regularly
- Monitor sync task success rates
- Review memory analytics

## Future Enhancements

### **Planned Features**
1. **Memory Compression**: Reduce storage footprint
2. **Intelligent Caching**: Predictive data loading
3. **Memory Analytics**: Advanced usage insights
4. **Distributed Memory**: Multi-node support

### **Integration Opportunities**
1. **MCP Memory Tools**: External memory servers
2. **Plugin Memory**: Plugin-specific storage
3. **User Memory**: Per-user memory isolation
4. **Memory Sharing**: Cross-session memory sharing

## Conclusion

Nagatha's memory system provides a robust, scalable solution for persistent storage that works seamlessly with Celery. The hybrid approach ensures both performance and reliability, while the background tasks handle maintenance and optimization automatically.

The system is designed to be:
- **Fast**: Redis provides sub-millisecond access
- **Reliable**: SQLite ensures data persistence
- **Scalable**: Can handle growing datasets
- **Maintainable**: Automated cleanup and optimization
- **Flexible**: Choose storage based on data requirements

This architecture allows Nagatha to maintain rich, persistent memory while providing fast access to frequently used information, all managed efficiently through Celery background tasks. 