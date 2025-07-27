"""
Task definitions for Nagatha Assistant.

This module defines common tasks that can be scheduled and executed by the Celery system.
Tasks integrate with the existing event system and can be used by plugins and MCPs.
"""

import os
import subprocess
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from celery import current_task

from ..core.celery_app import celery_app
from ..core.event import Event, StandardEventTypes, create_system_event
from ..core.event_bus import get_event_bus
from ..core.memory import get_memory_manager
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()
event_bus = get_event_bus()


def emit_task_event(event_type: str, task_data: Dict[str, Any]) -> None:
    """Helper function to emit task-related events."""
    event_bus.publish_sync(create_system_event(event_type, task_data))


async def record_task_history(task_id: str, task_name: str, status: str, result: Any = None, error: str = None, duration: float = None, worker: str = None) -> None:
    """Record task execution history."""
    try:
        memory = get_memory_manager()
        
        history_entry = {
            'task_id': task_id,
            'task_name': task_name,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'result': result,
            'error': error,
            'duration': duration,
            'worker': worker
        }
        
        # Get existing history
        history = await memory.get('system', 'task_history', default=[])
        if not isinstance(history, list):
            history = []
        
        # Add new entry
        history.append(history_entry)
        
        # Keep only last 1000 entries to prevent memory bloat
        if len(history) > 1000:
            history = history[-1000:]
        
        # Store updated history
        await memory.set('system', 'task_history', history)
        
    except Exception as e:
        logger.error(f"Failed to record task history: {e}")


def record_task_history_sync(task_id: str, task_name: str, status: str, result: Any = None, error: str = None, duration: float = None, worker: str = None) -> None:
    """Synchronous version of record_task_history for use in Celery tasks."""
    try:
        # Submit the asynchronous function to the thread pool
        thread_pool.submit(asyncio.run, record_task_history(task_id, task_name, status, result, error, duration, worker))
    except Exception as e:
        logger.error(f"Failed to record task history (sync): {e}")


@celery_app.task(bind=True, name='nagatha.system.health_check')
def system_health_check(self):
    """System health check task."""
    import asyncio
    import time
    
    task_id = self.request.id
    task_name = 'nagatha.system.health_check'
    start_time = time.time()
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': task_name
    })
    
    # Record start in history
    record_task_history_sync(
        task_id=task_id,
        task_name=task_name,
        status='started',
        worker=self.request.hostname
    )
    
    try:
        # Check system resources
        import psutil
        
        health_data = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'timestamp': datetime.now().isoformat()
        }
        
        # Store in memory (using sync version to avoid async issues in Celery task)
        try:
            memory = get_memory_manager()
            # Use the sync version to avoid async issues in Celery tasks
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # If we have a running loop, create a task
                asyncio.create_task(memory.set('system', 'health_check', health_data))
            except RuntimeError:
                # No running loop, run in a new event loop
                asyncio.run(memory.set('system', 'health_check', health_data))
        except Exception as e:
            logger.warning(f"Failed to store health check data: {e}")
        
        duration = time.time() - start_time
        
        emit_task_event(StandardEventTypes.TASK_COMPLETED, {
            'task_id': task_id,
            'status': 'completed',
            'result': health_data
        })
        
        # Record completion in history
        record_task_history_sync(
            task_id=task_id,
            task_name=task_name,
            status='completed',
            result=health_data,
            duration=duration,
            worker=self.request.hostname
        )
        
        return health_data
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Health check failed: {e}")
        
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        
        # Record failure in history
        record_task_history_sync(
            task_id=task_id,
            task_name=task_name,
            status='failed',
            error=str(e),
            duration=duration,
            worker=self.request.hostname
        )
        
        raise


@celery_app.task(bind=True, name='nagatha.system.backup_database')
def backup_database(self, backup_name: Optional[str] = None):
    """Backup the database."""
    task_id = self.request.id
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': 'system.backup_database'
    })
    
    try:
        # Get database path
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///nagatha.db")
        if not db_url.startswith("sqlite"):
            raise ValueError("Backup is only supported for SQLite databases")
        
        db_path = db_url.split("///", 1)[1]
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        # Generate backup name
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"nagatha_backup_{timestamp}.db"
        
        # Create backup directory if it doesn't exist
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, backup_name)
        
        # Copy database file
        import shutil
        shutil.copy2(db_path, backup_path)
        
        result = {
            'backup_path': backup_path,
            'original_size': os.path.getsize(db_path),
            'backup_size': os.path.getsize(backup_path),
            'timestamp': datetime.now().isoformat()
        }
        
        emit_task_event(StandardEventTypes.TASK_COMPLETED, {
            'task_id': task_id,
            'status': 'completed',
            'result': result
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='nagatha.system.cleanup_logs')
def cleanup_logs(self, days_to_keep: int = 7):
    """Clean up old log files."""
    task_id = self.request.id
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': 'system.cleanup_logs'
    })
    
    try:
        import glob
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        log_patterns = ['*.log', '*.log.*']
        deleted_files = []
        
        for pattern in log_patterns:
            for log_file in glob.glob(pattern):
                if os.path.isfile(log_file):
                    file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                    if file_time < cutoff_date:
                        os.remove(log_file)
                        deleted_files.append(log_file)
        
        result = {
            'deleted_files': deleted_files,
            'files_deleted': len(deleted_files),
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': datetime.now().isoformat()
        }
        
        emit_task_event(StandardEventTypes.TASK_COMPLETED, {
            'task_id': task_id,
            'status': 'completed',
            'result': result
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Log cleanup failed: {e}")
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='nagatha.memory.backup')
def backup_memory(self, section: Optional[str] = None):
    """Backup memory data to file."""
    task_id = self.request.id
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': 'memory.backup'
    })
    
    try:
        memory = get_memory_manager()
        
        if section:
            # Backup specific section
            data = await memory.get_all(section)
            backup_data = {section: data}
        else:
            # Backup all sections
            sections = await memory.list_sections()
            backup_data = {}
            for sect in sections:
                backup_data[sect] = await memory.get_all(sect)
        
        # Create backup directory
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        section_suffix = f"_{section}" if section else ""
        backup_file = os.path.join(backup_dir, f"memory_backup{section_suffix}_{timestamp}.json")
        
        # Write backup
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        result = {
            'backup_file': backup_file,
            'sections_backed_up': list(backup_data.keys()),
            'total_entries': sum(len(data) for data in backup_data.values()),
            'timestamp': datetime.now().isoformat()
        }
        
        emit_task_event(StandardEventTypes.TASK_COMPLETED, {
            'task_id': task_id,
            'status': 'completed',
            'result': result
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Memory backup failed: {e}")
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='nagatha.system.execute_command')
def execute_command(self, command: str, timeout: int = 300):
    """Execute a system command."""
    task_id = self.request.id
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': 'system.execute_command',
        'command': command
    })
    
    try:
        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = {
            'command': command,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'execution_time': datetime.now().isoformat()
        }
        
        if result.returncode == 0:
            emit_task_event(StandardEventTypes.TASK_COMPLETED, {
                'task_id': task_id,
                'status': 'completed',
                'result': output
            })
        else:
            emit_task_event('task.failed', {
                'task_id': task_id,
                'error': f"Command failed with return code {result.returncode}",
                'result': output
            })
        
        return output
        
    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds"
        logger.error(error_msg)
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': error_msg
        })
        raise
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='nagatha.notification.send')
def send_notification(self, message: str, notification_type: str = "info", 
                     title: Optional[str] = None):
    """Send a notification."""
    task_id = self.request.id
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': 'notification.send',
        'message': message,
        'type': notification_type
    })
    
    try:
        # Emit notification event
        event_bus.publish_sync(create_system_event(
            StandardEventTypes.UI_NOTIFICATION,
            {
                'message': message,
                'type': notification_type,
                'title': title,
                'timestamp': datetime.now().isoformat()
            }
        ))
        
        result = {
            'message': message,
            'type': notification_type,
            'title': title,
            'sent_at': datetime.now().isoformat()
        }
        
        emit_task_event(StandardEventTypes.TASK_COMPLETED, {
            'task_id': task_id,
            'status': 'completed',
            'result': result
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Notification failed: {e}")
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='nagatha.memory.cleanup')
def cleanup_memory(self, section: Optional[str] = None, days_old: int = 30):
    """Clean up old memory entries."""
    task_id = self.request.id
    
    emit_task_event(StandardEventTypes.TASK_UPDATED, {
        'task_id': task_id,
        'status': 'started',
        'task_name': 'memory.cleanup'
    })
    
    try:
        memory = get_memory_manager()
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cleaned_entries = 0
        
        if section:
            sections = [section]
        else:
            sections = await memory.list_sections()
        
        for sect in sections:
            try:
                data = await memory.get_all(sect)
                for key, value in data.items():
                    # Check if entry has timestamp and is old
                    if isinstance(value, dict) and 'timestamp' in value:
                        try:
                            entry_time = datetime.fromisoformat(value['timestamp'])
                            if entry_time < cutoff_date:
                                await memory.delete(sect, key)
                                cleaned_entries += 1
                        except (ValueError, TypeError):
                            continue
            except Exception as e:
                logger.warning(f"Error cleaning section {sect}: {e}")
        
        result = {
            'sections_processed': len(sections),
            'entries_cleaned': cleaned_entries,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': datetime.now().isoformat()
        }
        
        emit_task_event(StandardEventTypes.TASK_COMPLETED, {
            'task_id': task_id,
            'status': 'completed',
            'result': result
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Memory cleanup failed: {e}")
        emit_task_event('task.failed', {
            'task_id': task_id,
            'error': str(e)
        })
        raise


# Task registry for easy access
TASK_REGISTRY = {
    'system.health_check': system_health_check,
    'system.backup_database': backup_database,
    'system.cleanup_logs': cleanup_logs,
    'system.execute_command': execute_command,
    'memory.backup': backup_memory,
    'memory.cleanup': cleanup_memory,
    'notification.send': send_notification,
}


def get_task(task_name: str):
    """Get a task by name."""
    return TASK_REGISTRY.get(task_name)


def list_available_tasks() -> List[str]:
    """List all available task names."""
    return list(TASK_REGISTRY.keys()) 