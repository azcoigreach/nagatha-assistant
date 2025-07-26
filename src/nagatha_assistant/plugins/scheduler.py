"""
Scheduling Interface for Nagatha Assistant Task Scheduler.

This module provides the main scheduling interface for other components
to schedule one-time and recurring tasks with natural language and cron syntax.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union

from croniter import croniter
from celery import uuid
from celery.beat import ScheduleEntry
from celery.schedules import crontab, schedule

from nagatha_assistant.core.plugin import SimplePlugin, PluginConfig, PluginCommand
from nagatha_assistant.core.event import create_system_event, EventPriority
from nagatha_assistant.db import SessionLocal
from nagatha_assistant.db_models import Task, Reminder

from .celery_app import get_celery_app
from .tasks import AVAILABLE_TASKS

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Main task scheduling interface for Nagatha Assistant.
    
    Provides methods to schedule one-time and recurring tasks using
    cron syntax, natural language, or specific datetime objects.
    """
    
    def __init__(self):
        """Initialize the task scheduler."""
        self.celery_app = get_celery_app()
        self._scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        
    async def schedule_task(self, 
                          task_type: str,
                          task_args: Dict[str, Any],
                          schedule_spec: Union[str, datetime],
                          task_name: Optional[str] = None,
                          description: Optional[str] = None,
                          **kwargs) -> str:
        """
        Schedule a task for execution.
        
        Args:
            task_type: Type of task to schedule (from AVAILABLE_TASKS)
            task_args: Arguments to pass to the task
            schedule_spec: Schedule specification (cron, natural language, or datetime)
            task_name: Optional name for the task
            description: Optional description of the task
            **kwargs: Additional scheduling options
            
        Returns:
            Task ID for tracking
            
        Raises:
            ValueError: If task_type is not available or schedule_spec is invalid
        """
        if task_type not in AVAILABLE_TASKS:
            raise ValueError(f"Unknown task type: {task_type}. Available: {list(AVAILABLE_TASKS.keys())}")
        
        # Generate unique task ID
        task_id = kwargs.get("task_id", uuid())
        
        # Parse the schedule specification
        schedule_obj = self._parse_schedule(schedule_spec)
        
        # Get the Celery task
        celery_task = AVAILABLE_TASKS[task_type]
        
        # Schedule the task
        if isinstance(schedule_obj, datetime):
            # One-time task
            eta = schedule_obj
            result = celery_task.apply_async(
                args=self._prepare_task_args(task_type, task_args),
                eta=eta,
                task_id=task_id
            )
            
            # Store task info
            self._scheduled_tasks[task_id] = {
                "task_id": task_id,
                "task_type": task_type,
                "task_args": task_args,
                "schedule_type": "one_time",
                "eta": eta.isoformat(),
                "name": task_name,
                "description": description,
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
        else:
            # Recurring task - add to beat schedule
            schedule_name = task_name or f"{task_type}_{task_id}"
            
            self.celery_app.conf.beat_schedule[schedule_name] = {
                "task": celery_task.name,
                "schedule": schedule_obj,
                "args": self._prepare_task_args(task_type, task_args),
                "options": {"task_id": task_id}
            }
            
            # Store task info
            self._scheduled_tasks[task_id] = {
                "task_id": task_id,
                "task_type": task_type,
                "task_args": task_args,
                "schedule_type": "recurring",
                "schedule": str(schedule_obj),
                "name": task_name,
                "description": description,
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        
        # Publish event
        await self._publish_task_event("scheduler.task.scheduled", task_id)
        
        logger.info(f"Scheduled {task_type} task with ID {task_id}")
        return task_id
    
    async def schedule_mcp_tool(self, 
                              server_name: str,
                              tool_name: str,
                              arguments: Dict[str, Any],
                              schedule_spec: Union[str, datetime],
                              **kwargs) -> str:
        """
        Schedule an MCP tool call.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            schedule_spec: Schedule specification
            **kwargs: Additional scheduling options
            
        Returns:
            Task ID
        """
        return await self.schedule_task(
            task_type="mcp_tool",
            task_args={
                "server_name": server_name,
                "tool_name": tool_name,
                "arguments": arguments
            },
            schedule_spec=schedule_spec,
            task_name=kwargs.get("task_name", f"MCP_{server_name}_{tool_name}"),
            **kwargs
        )
    
    async def schedule_plugin_command(self,
                                    plugin_name: str,
                                    command_name: str,
                                    arguments: Dict[str, Any],
                                    schedule_spec: Union[str, datetime],
                                    **kwargs) -> str:
        """
        Schedule a plugin command.
        
        Args:
            plugin_name: Name of the plugin
            command_name: Name of the command
            arguments: Arguments to pass to the command
            schedule_spec: Schedule specification
            **kwargs: Additional scheduling options
            
        Returns:
            Task ID
        """
        return await self.schedule_task(
            task_type="plugin_command",
            task_args={
                "plugin_name": plugin_name,
                "command_name": command_name,
                "arguments": arguments
            },
            schedule_spec=schedule_spec,
            task_name=kwargs.get("task_name", f"Plugin_{plugin_name}_{command_name}"),
            **kwargs
        )
    
    async def schedule_notification(self,
                                  message: str,
                                  schedule_spec: Union[str, datetime],
                                  notification_type: str = "info",
                                  **kwargs) -> str:
        """
        Schedule a notification.
        
        Args:
            message: Notification message
            schedule_spec: Schedule specification
            notification_type: Type of notification
            **kwargs: Additional scheduling options
            
        Returns:
            Task ID
        """
        return await self.schedule_task(
            task_type="notification",
            task_args={
                "message": message,
                "notification_type": notification_type,
                **{k: v for k, v in kwargs.items() if k not in ["task_name", "description"]}
            },
            schedule_spec=schedule_spec,
            task_name=kwargs.get("task_name", f"Notification_{notification_type}"),
            **kwargs
        )
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a scheduled task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            True if task was cancelled, False if not found
        """
        if task_id not in self._scheduled_tasks:
            return False
        
        task_info = self._scheduled_tasks[task_id]
        
        # Revoke the task
        self.celery_app.control.revoke(task_id, terminate=True)
        
        # Remove from beat schedule if recurring
        if task_info.get("schedule_type") == "recurring":
            schedule_name = task_info.get("name", f"{task_info['task_type']}_{task_id}")
            if schedule_name in self.celery_app.conf.beat_schedule:
                del self.celery_app.conf.beat_schedule[schedule_name]
        
        # Update task status
        task_info["status"] = "cancelled"
        task_info["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        
        # Publish event
        await self._publish_task_event("scheduler.task.cancelled", task_id)
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    def get_scheduled_tasks(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get information about scheduled tasks.
        
        Args:
            status_filter: Optional status filter (scheduled, running, completed, cancelled)
            
        Returns:
            List of task information dictionaries
        """
        tasks = list(self._scheduled_tasks.values())
        
        if status_filter:
            tasks = [task for task in tasks if task.get("status") == status_filter]
        
        return tasks
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task information dictionary or None if not found
        """
        return self._scheduled_tasks.get(task_id)
    
    def _parse_schedule(self, schedule_spec: Union[str, datetime]) -> Union[datetime, crontab, schedule]:
        """
        Parse a schedule specification into a Celery schedule object.
        
        Args:
            schedule_spec: Schedule specification
            
        Returns:
            Parsed schedule object
            
        Raises:
            ValueError: If schedule_spec is invalid
        """
        if isinstance(schedule_spec, datetime):
            return schedule_spec
        
        if isinstance(schedule_spec, str):
            # Try to parse as natural language first
            natural_datetime = self._parse_natural_language_time(schedule_spec)
            if natural_datetime:
                return natural_datetime
            
            # Try to parse as cron expression
            try:
                # Validate cron expression
                if croniter.is_valid(schedule_spec):
                    # Parse cron components
                    parts = schedule_spec.split()
                    if len(parts) == 5:
                        minute, hour, day, month, day_of_week = parts
                        return crontab(
                            minute=minute,
                            hour=hour,
                            day_of_month=day,
                            month_of_year=month,
                            day_of_week=day_of_week
                        )
            except Exception:
                pass
            
            # Try to parse as ISO datetime
            try:
                return datetime.fromisoformat(schedule_spec.replace('Z', '+00:00'))
            except Exception:
                pass
        
        raise ValueError(f"Invalid schedule specification: {schedule_spec}")
    
    def _parse_natural_language_time(self, text: str) -> Optional[datetime]:
        """
        Parse natural language time expressions.
        
        Args:
            text: Natural language time expression
            
        Returns:
            Parsed datetime or None if not recognized
        """
        text = text.lower().strip()
        now = datetime.now(timezone.utc)
        
        # Simple patterns for demonstration
        patterns = [
            # "in X minutes/hours/days"
            (r'in (\d+) minutes?', lambda m: now + timedelta(minutes=int(m.group(1)))),
            (r'in (\d+) hours?', lambda m: now + timedelta(hours=int(m.group(1)))),
            (r'in (\d+) days?', lambda m: now + timedelta(days=int(m.group(1)))),
            
            # "tomorrow"
            (r'tomorrow', lambda m: now + timedelta(days=1)),
            
            # "next week"
            (r'next week', lambda m: now + timedelta(weeks=1)),
            
            # "at HH:MM"
            (r'at (\d{1,2}):(\d{2})', lambda m: now.replace(
                hour=int(m.group(1)), 
                minute=int(m.group(2)), 
                second=0, 
                microsecond=0
            ) + (timedelta(days=1) if now.hour > int(m.group(1)) else timedelta(0))),
        ]
        
        for pattern, parser in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return parser(match)
                except Exception:
                    continue
        
        return None
    
    def _prepare_task_args(self, task_type: str, task_args: Dict[str, Any]) -> List[Any]:
        """
        Prepare task arguments for Celery task execution.
        
        Args:
            task_type: Type of task
            task_args: Task arguments dictionary
            
        Returns:
            List of arguments for Celery task
        """
        if task_type == "mcp_tool":
            return [
                task_args["server_name"],
                task_args["tool_name"],
                task_args["arguments"]
            ]
        elif task_type == "plugin_command":
            return [
                task_args["plugin_name"],
                task_args["command_name"],
                task_args["arguments"]
            ]
        elif task_type == "notification":
            return [task_args["message"]]
        elif task_type == "shell_command":
            return [task_args["command"]]
        elif task_type == "reminder":
            return [
                task_args["task_id"],
                task_args["message"],
                task_args["remind_at"]
            ]
        elif task_type == "sequence":
            return [task_args["task_definitions"]]
        else:
            return [task_args]
    
    async def _publish_task_event(self, event_type: str, task_id: str) -> None:
        """
        Publish a task-related event.
        
        Args:
            event_type: Type of event
            task_id: Task ID
        """
        try:
            from nagatha_assistant.core.event_bus import get_event_bus
            
            task_info = self._scheduled_tasks.get(task_id, {})
            
            event = create_system_event(
                event_type,
                {
                    "task_id": task_id,
                    "task_type": task_info.get("task_type"),
                    "task_name": task_info.get("name"),
                    "schedule_type": task_info.get("schedule_type"),
                },
                priority=EventPriority.NORMAL,
                source="scheduler"
            )
            
            event_bus = get_event_bus()
            if hasattr(event_bus, '_running') and event_bus._running:
                await event_bus.publish(event)
                
        except Exception as e:
            logger.warning(f"Failed to publish task event: {e}")


class SchedulerPlugin(SimplePlugin):
    """
    Plugin that provides task scheduling capabilities to Nagatha Assistant.
    """
    
    PLUGIN_NAME = "scheduler"
    PLUGIN_VERSION = "1.0.0"
    
    def __init__(self, config: PluginConfig):
        """Initialize the scheduler plugin."""
        super().__init__(config)
        self.scheduler = TaskScheduler()
    
    async def setup(self) -> None:
        """Setup the scheduler plugin."""
        # Register scheduler commands
        commands = [
            PluginCommand(
                name="schedule_task",
                description="Schedule a task for execution",
                handler=self.handle_schedule_task,
                plugin_name=self.name,
                parameters={
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "Type of task to schedule"},
                        "task_args": {"type": "object", "description": "Arguments for the task"},
                        "schedule": {"type": "string", "description": "When to run the task"},
                        "name": {"type": "string", "description": "Optional task name"}
                    },
                    "required": ["task_type", "task_args", "schedule"]
                }
            ),
            PluginCommand(
                name="cancel_task",
                description="Cancel a scheduled task",
                handler=self.handle_cancel_task,
                plugin_name=self.name,
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "ID of task to cancel"}
                    },
                    "required": ["task_id"]
                }
            ),
            PluginCommand(
                name="list_tasks",
                description="List scheduled tasks",
                handler=self.handle_list_tasks,
                plugin_name=self.name,
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Filter by task status"}
                    }
                }
            ),
        ]
        
        # Register commands with plugin manager
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        for command in commands:
            plugin_manager.register_command(command)
        
        logger.info("Scheduler plugin setup complete")
    
    async def handle_schedule_task(self, task_type: str, task_args: Dict[str, Any], 
                                 schedule: str, name: Optional[str] = None, **kwargs) -> str:
        """Handle the schedule_task command."""
        task_id = await self.scheduler.schedule_task(
            task_type=task_type,
            task_args=task_args,
            schedule_spec=schedule,
            task_name=name,
            **kwargs
        )
        return f"Task scheduled with ID: {task_id}"
    
    async def handle_cancel_task(self, task_id: str, **kwargs) -> str:
        """Handle the cancel_task command."""
        cancelled = await self.scheduler.cancel_task(task_id)
        if cancelled:
            return f"Task {task_id} cancelled successfully"
        else:
            return f"Task {task_id} not found"
    
    async def handle_list_tasks(self, status: Optional[str] = None, **kwargs) -> str:
        """Handle the list_tasks command."""
        tasks = self.scheduler.get_scheduled_tasks(status_filter=status)
        if not tasks:
            return "No scheduled tasks found"
        
        result = f"Found {len(tasks)} scheduled tasks:\n"
        for task in tasks:
            result += f"- {task['task_id']}: {task.get('name', task['task_type'])} ({task['status']})\n"
        
        return result


# Global scheduler instance
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get the global task scheduler instance."""
    global _scheduler
    
    if _scheduler is None:
        _scheduler = TaskScheduler()
    
    return _scheduler


# Plugin configuration for discovery
PLUGIN_CONFIG = {
    "name": "scheduler",
    "version": "1.0.0",
    "description": "Task scheduling plugin for Nagatha Assistant",
    "author": "Nagatha Assistant",
    "dependencies": [],
    "config": {},
    "enabled": True,
    "priority": 50
}