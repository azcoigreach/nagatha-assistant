"""
Celery Beat configuration for scheduled tasks in Nagatha Assistant.

This module defines periodic tasks that should run on a schedule,
such as health checks, data cleanup, and system maintenance.
"""

from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

# Celery Beat schedule configuration
beat_schedule = {
    # System health check every 5 minutes
    'system-health-check': {
        'task': 'nagatha_assistant.core.celery_tasks.system.health_check',
        'schedule': timedelta(minutes=5),
        'options': {'queue': 'system'}
    },
    
    # Clean up old data daily at 2 AM
    'cleanup-old-data': {
        'task': 'nagatha_assistant.core.celery_tasks.system.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'system'}
    },
    
    # Refresh MCP servers every 30 minutes
    'refresh-mcp-servers': {
        'task': 'nagatha_assistant.core.celery_tasks.mcp.refresh_servers',
        'schedule': timedelta(minutes=30),
        'options': {'queue': 'mcp'}
    },
    
    # Publish system status event every hour
    'publish-system-status': {
        'task': 'nagatha_assistant.core.celery_tasks.events.publish_system_status',
        'schedule': timedelta(hours=1),
        'options': {'queue': 'events'}
    },
    
    # Memory cleanup and optimization every 6 hours
    'memory-optimization': {
        'task': 'nagatha_assistant.core.celery_tasks.system.memory_optimization',
        'schedule': timedelta(hours=6),
        'options': {'queue': 'system'}
    },
    
    # Check for stale sessions every hour
    'check-stale-sessions': {
        'task': 'nagatha_assistant.core.celery_tasks.agent.check_stale_sessions',
        'schedule': timedelta(hours=1),
        'options': {'queue': 'agent'}
    }
}


def configure_celery_beat(app: Celery):
    """
    Configure Celery Beat with the scheduled tasks.
    
    Args:
        app: Celery application instance
    """
    app.conf.beat_schedule = beat_schedule
    app.conf.timezone = 'UTC'
    
    # Configure beat database
    app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'
    
    # Configure beat settings
    app.conf.beat_sync_every = 1  # Sync beat schedule to database every minute
    app.conf.beat_max_loop_interval = 5  # Max interval between beat iterations