"""
Celery application configuration for Nagatha Assistant.

This module provides the main Celery application instance and configuration
for the event system and task processing.
"""

import os
from celery import Celery
from celery.signals import setup_logging

# Configure Celery app
app = Celery('nagatha_assistant')

# Configuration settings
app.conf.update(
    # Redis broker configuration
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'nagatha_assistant.core.celery_tasks.agent.*': {'queue': 'agent'},
        'nagatha_assistant.core.celery_tasks.mcp.*': {'queue': 'mcp'},
        'nagatha_assistant.core.celery_tasks.events.*': {'queue': 'events'},
        'nagatha_assistant.core.celery_tasks.system.*': {'queue': 'system'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Event system settings
    task_send_sent_event=True,
    task_track_started=True,
    
    # Result expiration
    result_expires=3600,  # 1 hour
    
    # Task timeout settings
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes
)

# Import task modules to register them
app.autodiscover_tasks([
    'nagatha_assistant.core.celery_tasks',
])

# Configure Celery Beat
from nagatha_assistant.core.celery_beat import configure_celery_beat
configure_celery_beat(app)


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure logging for Celery."""
    from nagatha_assistant.utils.logger import setup_logger_with_env_control
    # Use existing logger configuration
    setup_logger_with_env_control()


if __name__ == '__main__':
    app.start()