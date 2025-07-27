"""
Celery application configuration for Nagatha Assistant.

This module provides the core Celery application setup with Redis as the broker
and result backend. It's designed to integrate with the existing event system.
"""

import os
from celery import Celery
from celery.schedules import crontab
from typing import Dict, Any, Optional
import logging

# Configure Celery
CELERY_CONFIG = {
    'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 30 * 60,  # 30 minutes
    'task_soft_time_limit': 25 * 60,  # 25 minutes
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 1000,
    'broker_connection_retry_on_startup': True,
    'broker_connection_max_retries': 10,
    'result_expires': 60 * 60 * 24,  # 24 hours
    'beat_schedule': {},
    'beat_schedule_filename': os.getenv('CELERY_BEAT_SCHEDULE_FILE', 'celerybeat-schedule'),
    'beat_max_loop_interval': 5,  # 5 seconds
}

# Create Celery app
celery_app = Celery('nagatha_assistant')

# Configure the app
celery_app.conf.update(CELERY_CONFIG)

# Auto-discover tasks in plugins
celery_app.autodiscover_tasks(['nagatha_assistant.plugins'])

# Configure logging
celery_app.conf.update(
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
)

logger = logging.getLogger(__name__)


def get_celery_app() -> Celery:
    """Get the configured Celery application instance."""
    return celery_app


def configure_celery(broker_url: Optional[str] = None, 
                    result_backend: Optional[str] = None,
                    **kwargs) -> None:
    """
    Configure Celery with custom settings.
    
    Args:
        broker_url: Redis broker URL
        result_backend: Redis result backend URL
        **kwargs: Additional configuration options
    """
    config = CELERY_CONFIG.copy()
    
    if broker_url:
        config['broker_url'] = broker_url
    if result_backend:
        config['result_backend'] = result_backend
    
    config.update(kwargs)
    celery_app.conf.update(config)
    
    logger.info(f"Celery configured with broker: {config['broker_url']}")


def add_periodic_task(name: str, task: str, schedule: Any, 
                     args: Optional[tuple] = None, 
                     kwargs: Optional[Dict[str, Any]] = None) -> None:
    """
    Add a periodic task to the Celery beat schedule.
    
    Args:
        name: Task name
        task: Task function name
        schedule: Schedule (crontab, timedelta, etc.)
        args: Task arguments
        kwargs: Task keyword arguments
    """
    task_config = {
        'task': task,
        'schedule': schedule,
    }
    
    if args:
        task_config['args'] = args
    if kwargs:
        task_config['kwargs'] = kwargs
    
    # Add to in-memory schedule
    celery_app.conf.beat_schedule[name] = task_config
    
    # Persist to beat schedule file
    _persist_beat_schedule()
    
    logger.info(f"Added periodic task '{name}' with schedule: {schedule}")
    logger.info(f"Current beat schedule: {list(celery_app.conf.beat_schedule.keys())}")


def _persist_beat_schedule() -> None:
    """Persist the current beat schedule to the schedule file."""
    try:
        import json
        from celery.schedules import crontab
        
        # Get the schedule file path
        schedule_file = celery_app.conf.beat_schedule_filename
        
        # Convert the beat schedule to a serializable format
        serializable_schedule = {}
        for task_name, task_config in celery_app.conf.beat_schedule.items():
            serializable_config = task_config.copy()
            
            # Convert schedule object to string representation
            schedule = task_config['schedule']
            if isinstance(schedule, crontab):
                # Convert crontab to string format
                schedule_str = f"{schedule.minute} {schedule.hour} {schedule.day_of_month} {schedule.month_of_year} {schedule.day_of_week}"
                serializable_config['schedule'] = schedule_str
                serializable_config['schedule_type'] = 'crontab'
            elif hasattr(schedule, 'total_seconds'):
                # Convert timedelta to seconds
                serializable_config['schedule'] = int(schedule.total_seconds())
                serializable_config['schedule_type'] = 'timedelta'
            else:
                # Keep as string for other types
                serializable_config['schedule'] = str(schedule)
                serializable_config['schedule_type'] = 'string'
            
            serializable_schedule[task_name] = serializable_config
        
        # Write to file
        with open(schedule_file, 'w') as f:
            json.dump(serializable_schedule, f, indent=2, default=str)
        
        logger.info(f"Persisted beat schedule to {schedule_file}")
        
    except Exception as e:
        logger.error(f"Failed to persist beat schedule: {e}")


def _load_beat_schedule() -> None:
    """Load the beat schedule from the schedule file."""
    try:
        import json
        from celery.schedules import crontab
        
        schedule_file = celery_app.conf.beat_schedule_filename
        
        if not os.path.exists(schedule_file):
            logger.info(f"Beat schedule file {schedule_file} does not exist, starting with empty schedule")
            return
        
        with open(schedule_file, 'r') as f:
            serializable_schedule = json.load(f)
        
        # Convert back to Celery schedule objects
        for task_name, task_config in serializable_schedule.items():
            schedule_type = task_config.get('schedule_type', 'string')
            schedule_value = task_config['schedule']
            
            if schedule_type == 'crontab':
                # Parse crontab string
                parts = schedule_value.split()
                if len(parts) == 5:
                    minute, hour, day_of_month, month_of_year, day_of_week = parts
                    schedule = crontab(
                        minute=minute if minute != '*' else None,
                        hour=hour if hour != '*' else None,
                        day_of_month=day_of_month if day_of_month != '*' else None,
                        month_of_year=month_of_year if month_of_year != '*' else None,
                        day_of_week=day_of_week if day_of_week != '*' else None
                    )
                else:
                    logger.warning(f"Invalid crontab format for task {task_name}: {schedule_value}")
                    continue
            elif schedule_type == 'timedelta':
                # Convert seconds back to timedelta
                from celery.schedules import timedelta as celery_timedelta
                schedule = celery_timedelta(seconds=schedule_value)
            else:
                # Keep as string for other types
                schedule = schedule_value
            
            # Reconstruct task config
            task_config_copy = {
                'task': task_config['task'],
                'schedule': schedule,
            }
            
            if 'args' in task_config:
                task_config_copy['args'] = task_config['args']
            if 'kwargs' in task_config:
                task_config_copy['kwargs'] = task_config['kwargs']
            
            celery_app.conf.beat_schedule[task_name] = task_config_copy
        
        logger.info(f"Loaded {len(celery_app.conf.beat_schedule)} tasks from {schedule_file}")
        
    except Exception as e:
        logger.error(f"Failed to load beat schedule: {e}")
        # Start with empty schedule if loading fails
        celery_app.conf.beat_schedule.clear()


def remove_periodic_task(name: str) -> None:
    """
    Remove a periodic task from the Celery beat schedule.
    
    Args:
        name: Task name to remove
    """
    if name in celery_app.conf.beat_schedule:
        del celery_app.conf.beat_schedule[name]
        # Persist the updated schedule
        _persist_beat_schedule()
        logger.info(f"Removed periodic task '{name}'")


def get_beat_schedule() -> Dict[str, Any]:
    """Get the current beat schedule configuration."""
    return celery_app.conf.beat_schedule.copy()


def reload_beat_schedule() -> None:
    """Reload the beat schedule from the schedule file."""
    _load_beat_schedule()
    logger.info("Reloaded beat schedule from file")


def initialize_celery() -> None:
    """Initialize the Celery application and load the beat schedule."""
    _load_beat_schedule()
    logger.info("Celery application initialized with beat schedule loaded")


def clear_beat_schedule() -> None:
    """Clear all periodic tasks from the beat schedule."""
    celery_app.conf.beat_schedule.clear()
    # Persist the cleared schedule
    _persist_beat_schedule()
    logger.info("Cleared all periodic tasks from beat schedule")


# Health check task
@celery_app.task(bind=True, name='nagatha.health_check')
def health_check(self):
    """Health check task for monitoring Celery workers."""
    from datetime import datetime, timezone
    
    return {
        'status': 'healthy',
        'task_id': self.request.id,
        'worker': self.request.hostname,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


# Test task
@celery_app.task(bind=True, name='nagatha.test_task')
def test_task(self, message: str = "Hello from Celery!"):
    """Test task for verifying Celery functionality."""
    logger.info(f"Test task executed: {message}")
    return {
        'message': message,
        'task_id': self.request.id,
        'status': 'completed'
    }


if __name__ == '__main__':
    celery_app.start() 