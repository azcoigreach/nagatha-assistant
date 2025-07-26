"""
Celery Application Configuration for Nagatha Assistant Task Scheduler.

This module configures Celery for distributed task execution with Redis as the broker.
It integrates with the Nagatha plugin system and event bus for seamless task management.
"""

import os
import logging
from typing import Any, Dict, Optional

from celery import Celery
from celery.signals import task_success, task_failure, task_retry
from kombu import Queue

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
DEFAULT_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
DEFAULT_TASK_SERIALIZER = "json"
DEFAULT_RESULT_SERIALIZER = "json"
DEFAULT_ACCEPT_CONTENT = ["json"]
DEFAULT_TIMEZONE = "UTC"


def create_celery_app(
    broker_url: Optional[str] = None,
    result_backend: Optional[str] = None,
    **kwargs
) -> Celery:
    """
    Create and configure a Celery application for Nagatha Assistant.
    
    Args:
        broker_url: Redis broker URL (default from env or localhost)
        result_backend: Redis result backend URL (default from env or localhost)
        **kwargs: Additional Celery configuration options
        
    Returns:
        Configured Celery application instance
    """
    
    app = Celery("nagatha_scheduler")
    
    # Configure Celery
    app.conf.update(
        broker_url=broker_url or DEFAULT_BROKER_URL,
        result_backend=result_backend or DEFAULT_RESULT_BACKEND,
        task_serializer=DEFAULT_TASK_SERIALIZER,
        result_serializer=DEFAULT_RESULT_SERIALIZER,
        accept_content=DEFAULT_ACCEPT_CONTENT,
        timezone=DEFAULT_TIMEZONE,
        enable_utc=True,
        
        # Task routing
        task_routes={
            "nagatha_scheduler.tasks.*": {"queue": "nagatha_tasks"},
            "nagatha_scheduler.plugins.*": {"queue": "nagatha_plugins"},
        },
        
        # Queue configuration
        task_default_queue="nagatha_tasks",
        task_queues=(
            Queue("nagatha_tasks", routing_key="nagatha_tasks"),
            Queue("nagatha_plugins", routing_key="nagatha_plugins"),
        ),
        
        # Worker configuration
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
        
        # Task execution settings
        task_soft_time_limit=300,  # 5 minutes
        task_time_limit=600,       # 10 minutes
        task_max_retries=3,
        task_default_retry_delay=60,  # 1 minute
        
        # Beat scheduler settings
        beat_schedule={},
        beat_scheduler="celery.beat:PersistentScheduler",
        
        # Additional settings
        task_send_sent_event=True,
        task_track_started=True,
        result_expires=3600,  # 1 hour
        
        **kwargs
    )
    
    # Setup signal handlers for integration with Nagatha event system
    setup_signal_handlers(app)
    
    # Autodiscover tasks
    app.autodiscover_tasks(["nagatha_assistant.plugins"])
    
    logger.info("Celery application configured for Nagatha Assistant")
    return app


def setup_signal_handlers(app: Celery) -> None:
    """
    Setup Celery signal handlers for integration with Nagatha event system.
    
    Args:
        app: Celery application instance
    """
    
    @task_success.connect
    def task_success_handler(sender=None, task_id=None, result=None, retval=None, **kwargs):
        """Handle task success events."""
        try:
            from nagatha_assistant.core.event_bus import get_event_bus
            from nagatha_assistant.core.event import create_system_event, EventPriority
            
            event = create_system_event(
                "scheduler.task.success",
                {
                    "task_id": task_id,
                    "task_name": sender,
                    "result": str(result)[:1000] if result else None,  # Limit result size
                },
                priority=EventPriority.NORMAL,
                source="scheduler"
            )
            
            # Try to publish event (non-blocking)
            event_bus = get_event_bus()
            if hasattr(event_bus, '_running') and event_bus._running:
                event_bus.publish_sync(event)
                
        except Exception as e:
            logger.warning(f"Failed to publish task success event: {e}")
    
    @task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs):
        """Handle task failure events."""
        try:
            from nagatha_assistant.core.event_bus import get_event_bus
            from nagatha_assistant.core.event import create_system_event, EventPriority
            
            event = create_system_event(
                "scheduler.task.failure",
                {
                    "task_id": task_id,
                    "task_name": sender,
                    "exception": str(exception)[:1000] if exception else None,
                    "traceback": str(traceback)[:2000] if traceback else None,
                },
                priority=EventPriority.HIGH,
                source="scheduler"
            )
            
            # Try to publish event (non-blocking)
            event_bus = get_event_bus()
            if hasattr(event_bus, '_running') and event_bus._running:
                event_bus.publish_sync(event)
                
        except Exception as e:
            logger.warning(f"Failed to publish task failure event: {e}")
    
    @task_retry.connect
    def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
        """Handle task retry events."""
        try:
            from nagatha_assistant.core.event_bus import get_event_bus
            from nagatha_assistant.core.event import create_system_event, EventPriority
            
            event = create_system_event(
                "scheduler.task.retry",
                {
                    "task_id": task_id,
                    "task_name": sender,
                    "reason": str(reason)[:1000] if reason else None,
                },
                priority=EventPriority.NORMAL,
                source="scheduler"
            )
            
            # Try to publish event (non-blocking)
            event_bus = get_event_bus()
            if hasattr(event_bus, '_running') and event_bus._running:
                event_bus.publish_sync(event)
                
        except Exception as e:
            logger.warning(f"Failed to publish task retry event: {e}")


# Global Celery app instance
celery_app: Optional[Celery] = None


def get_celery_app() -> Celery:
    """
    Get the global Celery application instance.
    
    Returns:
        Celery application instance
    """
    global celery_app
    
    if celery_app is None:
        celery_app = create_celery_app()
    
    return celery_app


def configure_celery_app(**kwargs) -> Celery:
    """
    Configure or reconfigure the global Celery application.
    
    Args:
        **kwargs: Celery configuration options
        
    Returns:
        Configured Celery application instance
    """
    global celery_app
    celery_app = create_celery_app(**kwargs)
    return celery_app