"""
Task scheduler interface for Nagatha Assistant.

This module provides a high-level interface for scheduling tasks using Celery,
integrating with the existing event system and providing natural language
time specification capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List, Callable
from celery.schedules import crontab, timedelta as celery_timedelta
import parsedatetime
import re

from .celery_app import celery_app, add_periodic_task, remove_periodic_task, get_beat_schedule
from .event import Event, StandardEventTypes, create_system_event
from .event_bus import get_event_bus

logger = logging.getLogger(__name__)

# Initialize parsedatetime calendar
cal = parsedatetime.Calendar()


class TaskScheduler:
    """High-level task scheduler interface."""
    
    def __init__(self):
        self.event_bus = get_event_bus()
        self._task_registry: Dict[str, Callable] = {}
        
    def register_task(self, name: str, task_func: Callable) -> None:
        """
        Register a task function for scheduling.
        
        Args:
            name: Task name
            task_func: Task function to register
        """
        self._task_registry[name] = task_func
        logger.info(f"Registered task: {name}")
        
    def parse_natural_time(self, time_spec: str) -> Union[datetime, timedelta, crontab]:
        """
        Parse natural language time specification.
        
        Args:
            time_spec: Natural language time specification
            
        Returns:
            Parsed time (datetime, timedelta, or crontab)
            
        Examples:
            "in 5 minutes" -> timedelta(minutes=5)
            "tomorrow at 9am" -> datetime
            "every day at 2pm" -> crontab
            "every monday at 8am" -> crontab
        """
        time_spec = time_spec.lower().strip()
        
        # Handle "in X seconds/minutes/hours/days"
        if time_spec.startswith('in '):
            match = re.match(r'in (\d+) (second|minute|hour|day|week)s?', time_spec)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)
                if unit == 'second':
                    return timedelta(seconds=amount)
                elif unit == 'minute':
                    return timedelta(minutes=amount)
                elif unit == 'hour':
                    return timedelta(hours=amount)
                elif unit == 'day':
                    return timedelta(days=amount)
                elif unit == 'week':
                    return timedelta(weeks=amount)
        
        # Handle "every X seconds/minutes/hours/days"
        if time_spec.startswith('every '):
            return self._parse_every_format(time_spec)
        
        if time_spec.startswith('every day at '):
            return self._parse_every_day_at_format(time_spec)
        
        day_pattern = r'every (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at (.+)'
        if re.match(day_pattern, time_spec):
            return self._parse_every_day_at_specific_time_format(time_spec)
        
        if re.match(r'^\*/\d+ \* \* \* \*$', time_spec):
            return self._parse_cron_like_syntax(time_spec)
        
        cron_pattern = r'^(\*|\d+)(/\d+)? (\*|\d+)(/\d+)? (\*|\d+)(/\d+)? (\*|\d+)(/\d+)? (\*|\d+)(/\d+)?$'
        if re.match(cron_pattern, time_spec):
            return self._parse_standard_cron_expression(time_spec)
        
        # Handle specific date/time
        parsed_time, _ = cal.parseDT(time_spec)
        if parsed_time:
            return parsed_time
        
        raise ValueError(f"Could not parse time specification: {time_spec}")
    
    def schedule_task(self, task_name: str, schedule: Union[str, datetime, timedelta, crontab],
                     args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                     task_id: Optional[str] = None) -> str:
        """
        Schedule a task with the given schedule.
        
        Args:
            task_name: Name of the task to schedule
            schedule: Schedule specification (natural language or object)
            args: Task arguments
            kwargs: Task keyword arguments
            task_id: Optional task ID for tracking
            
        Returns:
            Task ID
        """
        # Parse natural language schedule if string
        if isinstance(schedule, str):
            schedule = self.parse_natural_time(schedule)
        
        # Generate task ID if not provided
        if task_id is None:
            task_id = f"{task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Add to beat schedule
        add_periodic_task(task_id, task_name, schedule, args, kwargs)
        
        # Emit event
        self.event_bus.publish_sync(create_system_event(
            StandardEventTypes.TASK_CREATED,
            {
                'task_id': task_id,
                'task_name': task_name,
                'schedule': str(schedule),
                'args': args,
                'kwargs': kwargs
            }
        ))
        
        logger.info(f"Scheduled task '{task_name}' with ID '{task_id}' for {schedule}")
        return task_id
    
    def schedule_one_time(self, task_name: str, when: Union[str, datetime],
                         args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                         task_id: Optional[str] = None) -> str:
        """
        Schedule a one-time task.
        
        Args:
            task_name: Name of the task to schedule
            when: When to execute the task
            args: Task arguments
            kwargs: Task keyword arguments
            task_id: Optional task ID for tracking
            
        Returns:
            Task ID
        """
        # Parse natural language time if string
        if isinstance(when, str):
            when = self.parse_natural_time(when)
        
        # If it's a datetime, calculate delay
        if isinstance(when, datetime):
            delay = when - datetime.now()
            if delay.total_seconds() <= 0:
                raise ValueError("Scheduled time must be in the future")
            schedule = celery_timedelta(seconds=delay.total_seconds())
        else:
            schedule = when
        
        return self.schedule_task(task_name, schedule, args, kwargs, task_id)
    
    def schedule_recurring(self, task_name: str, interval: Union[str, timedelta, crontab],
                          args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                          task_id: Optional[str] = None) -> str:
        """
        Schedule a recurring task.
        
        Args:
            task_name: Name of the task to schedule
            interval: Recurring interval
            args: Task arguments
            kwargs: Task keyword arguments
            task_id: Optional task ID for tracking
            
        Returns:
            Task ID
        """
        # Parse natural language interval if string
        if isinstance(interval, str):
            interval = self.parse_natural_time(interval)
        
        return self.schedule_task(task_name, interval, args, kwargs, task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a scheduled task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled, False if not found
        """
        # Check if task exists
        from .celery_app import get_beat_schedule
        schedule = get_beat_schedule()
        if task_id not in schedule:
            logger.warning(f"Task '{task_id}' not found for cancellation")
            return False
        
        remove_periodic_task(task_id)
        
        # Emit event
        self.event_bus.publish_sync(create_system_event(
            StandardEventTypes.TASK_UPDATED,
            {
                'task_id': task_id,
                'status': 'cancelled'
            }
        ))
        
        logger.info(f"Cancelled task '{task_id}'")
        return True
    
    def list_scheduled_tasks(self) -> Dict[str, Any]:
        """
        List all scheduled tasks.
        
        Returns:
            Dictionary of scheduled tasks
        """
        return get_beat_schedule()
    
    def clear_all_tasks(self) -> None:
        """Clear all scheduled tasks."""
        from .celery_app import clear_beat_schedule
        clear_beat_schedule()
        
        # Emit event
        self.event_bus.publish_sync(create_system_event(
            "task.schedule.cleared",
            {'cleared_at': datetime.now().isoformat()}
        ))
        
        logger.info("Cleared all scheduled tasks")


# Global scheduler instance
_scheduler_instance: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler()
    return _scheduler_instance


def schedule_task(task_name: str, schedule: Union[str, datetime, timedelta, crontab],
                 args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                 task_id: Optional[str] = None) -> str:
    """Convenience function to schedule a task."""
    return get_scheduler().schedule_task(task_name, schedule, args, kwargs, task_id)


def schedule_one_time(task_name: str, when: Union[str, datetime],
                     args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                     task_id: Optional[str] = None) -> str:
    """Convenience function to schedule a one-time task."""
    return get_scheduler().schedule_one_time(task_name, when, args, kwargs, task_id)


def schedule_recurring(task_name: str, interval: Union[str, timedelta, crontab],
                      args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                      task_id: Optional[str] = None) -> str:
    """Convenience function to schedule a recurring task."""
    return get_scheduler().schedule_recurring(task_name, interval, args, kwargs, task_id)


def cancel_task(task_id: str) -> bool:
    """Convenience function to cancel a task."""
    return get_scheduler().cancel_task(task_id)


def list_scheduled_tasks() -> Dict[str, Any]:
    """Convenience function to list scheduled tasks."""
    return get_scheduler().list_scheduled_tasks() 