"""
Task Manager Plugin for Nagatha Assistant.

This plugin provides task scheduling and management capabilities through the
existing plugin system, integrating with the Celery scheduler.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..core.plugin import SimplePlugin, PluginConfig
from ..core.scheduler import get_scheduler, schedule_task, cancel_task, list_scheduled_tasks
from ..core.event import Event, StandardEventTypes, create_system_event
from ..plugins.tasks import list_available_tasks, get_task

logger = logging.getLogger(__name__)


class TaskManagerPlugin(SimplePlugin):
    """Plugin for managing scheduled tasks."""
    
    PLUGIN_NAME = "Task Manager"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Manage scheduled tasks and task execution"
    
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.scheduler = get_scheduler()
        self._task_history: List[Dict[str, Any]] = []
    
    async def on_start(self) -> None:
        """Initialize the task manager plugin."""
        logger.info("Task Manager plugin started")
        
        # Register event handlers
        self.register_event_handler(StandardEventTypes.TASK_CREATED, self._on_task_created)
        self.register_event_handler(StandardEventTypes.TASK_COMPLETED, self._on_task_completed)
        self.register_event_handler(StandardEventTypes.TASK_UPDATED, self._on_task_updated)
    
    async def on_stop(self) -> None:
        """Clean up the task manager plugin."""
        logger.info("Task Manager plugin stopped")
    
    def _on_task_created(self, event: Event) -> None:
        """Handle task creation events."""
        task_data = event.data
        self._task_history.append({
            'timestamp': datetime.now().isoformat(),
            'event': 'created',
            'task_id': task_data.get('task_id'),
            'task_name': task_data.get('task_name'),
            'schedule': task_data.get('schedule')
        })
        logger.info(f"Task created: {task_data.get('task_name')} ({task_data.get('task_id')})")
    
    def _on_task_completed(self, event: Event) -> None:
        """Handle task completion events."""
        task_data = event.data
        self._task_history.append({
            'timestamp': datetime.now().isoformat(),
            'event': 'completed',
            'task_id': task_data.get('task_id'),
            'task_name': task_data.get('task_name'),
            'result': task_data.get('result')
        })
        logger.info(f"Task completed: {task_data.get('task_name')} ({task_data.get('task_id')})")
    
    def _on_task_updated(self, event: Event) -> None:
        """Handle task update events."""
        task_data = event.data
        self._task_history.append({
            'timestamp': datetime.now().isoformat(),
            'event': 'updated',
            'task_id': task_data.get('task_id'),
            'status': task_data.get('status')
        })
        logger.info(f"Task updated: {task_data.get('task_id')} - {task_data.get('status')}")
    
    async def schedule_task(self, task_name: str, schedule: str, 
                          args: Optional[tuple] = None, kwargs: Optional[Dict[str, Any]] = None,
                          task_id: Optional[str] = None) -> str:
        """
        Schedule a task.
        
        Args:
            task_name: Name of the task to schedule
            schedule: Schedule specification (natural language or cron)
            args: Task arguments
            kwargs: Task keyword arguments
            task_id: Optional custom task ID
            
        Returns:
            Task ID
        """
        try:
            scheduled_id = schedule_task(task_name, schedule, args, kwargs, task_id)
            logger.info(f"Scheduled task '{task_name}' with ID '{scheduled_id}'")
            return scheduled_id
        except Exception as e:
            logger.error(f"Failed to schedule task '{task_name}': {e}")
            raise
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a scheduled task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        try:
            result = cancel_task(task_id)
            if result:
                logger.info(f"Cancelled task '{task_id}'")
            else:
                logger.warning(f"Task '{task_id}' not found for cancellation")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel task '{task_id}': {e}")
            raise
    
    async def list_scheduled_tasks(self) -> Dict[str, Any]:
        """
        List all scheduled tasks.
        
        Returns:
            Dictionary of scheduled tasks
        """
        try:
            return list_scheduled_tasks()
        except Exception as e:
            logger.error(f"Failed to list scheduled tasks: {e}")
            raise
    
    async def list_available_tasks(self) -> List[str]:
        """
        List all available task names.
        
        Returns:
            List of available task names
        """
        try:
            return list_available_tasks()
        except Exception as e:
            logger.error(f"Failed to list available tasks: {e}")
            raise
    
    async def get_task_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get task execution history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of task history entries
        """
        history = self._task_history.copy()
        if limit:
            history = history[-limit:]
        return history
    
    async def clear_task_history(self) -> None:
        """Clear task execution history."""
        self._task_history.clear()
        logger.info("Task history cleared")
    
    async def execute_task_now(self, task_name: str, args: Optional[tuple] = None, 
                             kwargs: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute a task immediately.
        
        Args:
            task_name: Name of the task to execute
            args: Task arguments
            kwargs: Task keyword arguments
            
        Returns:
            Task ID
        """
        try:
            task_func = get_task(task_name)
            if not task_func:
                raise ValueError(f"Task '{task_name}' not found")
            
            # Execute task immediately
            result = task_func.delay(*(args or ()), **(kwargs or {}))
            logger.info(f"Executed task '{task_name}' with ID '{result.id}'")
            return result.id
        except Exception as e:
            logger.error(f"Failed to execute task '{task_name}': {e}")
            raise
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.
        
        Args:
            task_id: Task ID to check
            
        Returns:
            Task status information or None if not found
        """
        try:
            from ..core.celery_app import celery_app
            result = celery_app.AsyncResult(task_id)
            
            status_info = {
                'task_id': task_id,
                'status': result.status,
                'ready': result.ready(),
                'successful': result.successful(),
                'failed': result.failed()
            }
            
            if result.ready():
                if result.successful():
                    status_info['result'] = result.result
                else:
                    status_info['error'] = str(result.info)
            
            return status_info
        except Exception as e:
            logger.error(f"Failed to get task status for '{task_id}': {e}")
            return None
    
    # Plugin command handlers
    async def handle_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle plugin commands."""
        try:
            if command == "schedule":
                task_name = args.get("task_name")
                schedule = args.get("schedule")
                task_args = args.get("args")
                task_kwargs = args.get("kwargs")
                task_id = args.get("task_id")
                
                if not task_name or not schedule:
                    return {"error": "task_name and schedule are required"}
                
                scheduled_id = await self.schedule_task(task_name, schedule, task_args, task_kwargs, task_id)
                return {"success": True, "task_id": scheduled_id}
            
            elif command == "cancel":
                task_id = args.get("task_id")
                if not task_id:
                    return {"error": "task_id is required"}
                
                result = await self.cancel_task(task_id)
                return {"success": result}
            
            elif command == "list":
                tasks = await self.list_scheduled_tasks()
                return {"tasks": tasks}
            
            elif command == "available":
                tasks = await self.list_available_tasks()
                return {"tasks": tasks}
            
            elif command == "history":
                limit = args.get("limit")
                history = await self.get_task_history(limit)
                return {"history": history}
            
            elif command == "clear_history":
                await self.clear_task_history()
                return {"success": True}
            
            elif command == "execute":
                task_name = args.get("task_name")
                task_args = args.get("args")
                task_kwargs = args.get("kwargs")
                
                if not task_name:
                    return {"error": "task_name is required"}
                
                task_id = await self.execute_task_now(task_name, task_args, task_kwargs)
                return {"success": True, "task_id": task_id}
            
            elif command == "status":
                task_id = args.get("task_id")
                if not task_id:
                    return {"error": "task_id is required"}
                
                status = await self.get_task_status(task_id)
                return {"status": status}
            
            else:
                return {"error": f"Unknown command: {command}"}
        
        except Exception as e:
            logger.error(f"Error handling command '{command}': {e}")
            return {"error": str(e)}
    
    def get_commands(self) -> List[Dict[str, Any]]:
        """Get available plugin commands."""
        return [
            {
                "name": "schedule",
                "description": "Schedule a task",
                "args": {
                    "task_name": {"type": "string", "required": True, "description": "Name of the task to schedule"},
                    "schedule": {"type": "string", "required": True, "description": "Schedule specification"},
                    "args": {"type": "array", "required": False, "description": "Task arguments"},
                    "kwargs": {"type": "object", "required": False, "description": "Task keyword arguments"},
                    "task_id": {"type": "string", "required": False, "description": "Custom task ID"}
                }
            },
            {
                "name": "cancel",
                "description": "Cancel a scheduled task",
                "args": {
                    "task_id": {"type": "string", "required": True, "description": "Task ID to cancel"}
                }
            },
            {
                "name": "list",
                "description": "List all scheduled tasks",
                "args": {}
            },
            {
                "name": "available",
                "description": "List all available tasks",
                "args": {}
            },
            {
                "name": "history",
                "description": "Get task execution history",
                "args": {
                    "limit": {"type": "integer", "required": False, "description": "Maximum number of entries"}
                }
            },
            {
                "name": "clear_history",
                "description": "Clear task execution history",
                "args": {}
            },
            {
                "name": "execute",
                "description": "Execute a task immediately",
                "args": {
                    "task_name": {"type": "string", "required": True, "description": "Name of the task to execute"},
                    "args": {"type": "array", "required": False, "description": "Task arguments"},
                    "kwargs": {"type": "object", "required": False, "description": "Task keyword arguments"}
                }
            },
            {
                "name": "status",
                "description": "Get task status",
                "args": {
                    "task_id": {"type": "string", "required": True, "description": "Task ID to check"}
                }
            }
        ] 