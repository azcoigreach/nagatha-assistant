"""
Task Definitions and Registration for Nagatha Assistant Scheduler.

This module defines Celery tasks that can be scheduled and executed,
including MCP tool calls, plugin commands, and system utilities.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from celery import Task
from celery.exceptions import Retry

from .celery_app import get_celery_app

logger = logging.getLogger(__name__)

# Get the Celery app instance
app = get_celery_app()


class NagathaTask(Task):
    """
    Base task class for Nagatha Assistant tasks with enhanced error handling
    and integration with the Nagatha event system.
    """
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_jitter = False
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {self.name} [{task_id}] completed successfully")
        
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {self.name} [{task_id}] failed: {exc}")
        
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Task {self.name} [{task_id}] retrying: {exc}")


@app.task(base=NagathaTask, bind=True)
def execute_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an MCP tool call through the scheduler.
    
    Args:
        server_name: Name of the MCP server
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        
    Returns:
        Tool execution result
    """
    try:
        # Import here to avoid circular imports
        from nagatha_assistant.core.mcp_manager import get_mcp_manager
        
        async def _execute():
            mcp_manager = await get_mcp_manager()
            return await mcp_manager.call_tool(tool_name, arguments, server_name)
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_execute())
            return {
                "success": True,
                "result": result,
                "server_name": server_name,
                "tool_name": tool_name,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            loop.close()
            
    except Exception as e:
        logger.exception(f"Failed to execute MCP tool {tool_name} on server {server_name}")
        return {
            "success": False,
            "error": str(e),
            "server_name": server_name,
            "tool_name": tool_name,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }


@app.task(base=NagathaTask, bind=True)
def execute_plugin_command(self, plugin_name: str, command_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a plugin command through the scheduler.
    
    Args:
        plugin_name: Name of the plugin
        command_name: Name of the command to execute
        arguments: Arguments to pass to the command
        
    Returns:
        Command execution result
    """
    try:
        # Import here to avoid circular imports
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
        
        async def _execute():
            plugin_manager = get_plugin_manager()
            return await plugin_manager.execute_command(command_name, **arguments)
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_execute())
            return {
                "success": True,
                "result": result,
                "plugin_name": plugin_name,
                "command_name": command_name,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            loop.close()
            
    except Exception as e:
        logger.exception(f"Failed to execute plugin command {command_name} on plugin {plugin_name}")
        return {
            "success": False,
            "error": str(e),
            "plugin_name": plugin_name,
            "command_name": command_name,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }


@app.task(base=NagathaTask, bind=True)
def send_notification(self, message: str, notification_type: str = "info", 
                     target: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Send a notification through the event system.
    
    Args:
        message: Notification message
        notification_type: Type of notification (info, warning, error, success)
        target: Optional target for the notification
        **kwargs: Additional notification data
        
    Returns:
        Notification result
    """
    try:
        # Import here to avoid circular imports
        from nagatha_assistant.core.event_bus import get_event_bus
        from nagatha_assistant.core.event import create_system_event, EventPriority
        
        priority_map = {
            "error": EventPriority.HIGH,
            "warning": EventPriority.NORMAL,
            "info": EventPriority.NORMAL,
            "success": EventPriority.LOW
        }
        
        event = create_system_event(
            "scheduler.notification",
            {
                "message": message,
                "notification_type": notification_type,
                "target": target,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                **kwargs
            },
            priority=priority_map.get(notification_type, EventPriority.NORMAL),
            source="scheduler"
        )
        
        # Try to publish event
        event_bus = get_event_bus()
        if hasattr(event_bus, '_running') and event_bus._running:
            event_bus.publish_sync(event)
            
        return {
            "success": True,
            "message": message,
            "notification_type": notification_type,
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.exception(f"Failed to send notification: {message}")
        return {
            "success": False,
            "error": str(e),
            "message": message,
            "sent_at": datetime.now(timezone.utc).isoformat()
        }


@app.task(base=NagathaTask, bind=True)
def execute_shell_command(self, command: str, working_dir: Optional[str] = None,
                         timeout: int = 300, capture_output: bool = True) -> Dict[str, Any]:
    """
    Execute a shell command through the scheduler.
    
    Args:
        command: Shell command to execute
        working_dir: Working directory for the command
        timeout: Command timeout in seconds
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        Command execution result
    """
    import subprocess
    import os
    
    try:
        env = os.environ.copy()
        
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            env=env
        )
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout if capture_output else None,
            "stderr": result.stderr if capture_output else None,
            "command": command,
            "working_dir": working_dir,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"Shell command timed out: {command}")
        return {
            "success": False,
            "error": "Command timed out",
            "timeout": timeout,
            "command": command,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.exception(f"Failed to execute shell command: {command}")
        return {
            "success": False,
            "error": str(e),
            "command": command,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }


@app.task(base=NagathaTask, bind=True)
def create_reminder(self, task_id: int, message: str, remind_at: str) -> Dict[str, Any]:
    """
    Create a reminder for a task.
    
    Args:
        task_id: ID of the task to remind about
        message: Reminder message
        remind_at: ISO formatted datetime string for when to remind
        
    Returns:
        Reminder creation result
    """
    try:
        # Import here to avoid circular imports
        from nagatha_assistant.db import SessionLocal
        from nagatha_assistant.db_models import Task, Reminder
        from datetime import datetime
        
        async def _create_reminder():
            async with SessionLocal() as session:
                # Parse the remind_at datetime
                remind_datetime = datetime.fromisoformat(remind_at.replace('Z', '+00:00'))
                
                # Create the reminder
                reminder = Reminder(
                    task_id=task_id,
                    remind_at=remind_datetime,
                    delivered=False
                )
                
                session.add(reminder)
                await session.commit()
                
                return {
                    "success": True,
                    "reminder_id": reminder.id,
                    "task_id": task_id,
                    "remind_at": remind_at,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_create_reminder())
        finally:
            loop.close()
            
    except Exception as e:
        logger.exception(f"Failed to create reminder for task {task_id}")
        return {
            "success": False,
            "error": str(e),
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }


@app.task(base=NagathaTask, bind=True)
def process_task_sequence(self, task_definitions: List[Dict[str, Any]], 
                         stop_on_failure: bool = True) -> Dict[str, Any]:
    """
    Process a sequence of tasks with optional dependency handling.
    
    Args:
        task_definitions: List of task definitions to execute in order
        stop_on_failure: Whether to stop the sequence if a task fails
        
    Returns:
        Sequence execution result
    """
    results = []
    failed_task = None
    
    try:
        for i, task_def in enumerate(task_definitions):
            task_type = task_def.get("type")
            task_args = task_def.get("args", {})
            
            logger.info(f"Executing task {i+1}/{len(task_definitions)}: {task_type}")
            
            # Execute the appropriate task based on type
            if task_type == "mcp_tool":
                result = execute_mcp_tool.apply(
                    args=[task_args.get("server_name"), task_args.get("tool_name"), 
                          task_args.get("arguments", {})]
                ).get()
            elif task_type == "plugin_command":
                result = execute_plugin_command.apply(
                    args=[task_args.get("plugin_name"), task_args.get("command_name"),
                          task_args.get("arguments", {})]
                ).get()
            elif task_type == "shell_command":
                result = execute_shell_command.apply(
                    args=[task_args.get("command")],
                    kwargs={k: v for k, v in task_args.items() if k != "command"}
                ).get()
            elif task_type == "notification":
                result = send_notification.apply(
                    args=[task_args.get("message", "")],
                    kwargs={k: v for k, v in task_args.items() if k != "message"}
                ).get()
            else:
                result = {
                    "success": False,
                    "error": f"Unknown task type: {task_type}",
                    "task_index": i
                }
            
            results.append({
                "task_index": i,
                "task_type": task_type,
                "result": result
            })
            
            # Check if task failed
            if not result.get("success", False):
                failed_task = i
                if stop_on_failure:
                    logger.warning(f"Task sequence stopped at task {i+1} due to failure")
                    break
        
        return {
            "success": failed_task is None,
            "completed_tasks": len(results),
            "total_tasks": len(task_definitions),
            "failed_task_index": failed_task,
            "results": results,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.exception("Failed to process task sequence")
        return {
            "success": False,
            "error": str(e),
            "completed_tasks": len(results),
            "total_tasks": len(task_definitions),
            "results": results,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }


# Task registry for easy access
AVAILABLE_TASKS = {
    "mcp_tool": execute_mcp_tool,
    "plugin_command": execute_plugin_command,
    "notification": send_notification,
    "shell_command": execute_shell_command,
    "reminder": create_reminder,
    "sequence": process_task_sequence,
}


def get_available_tasks() -> Dict[str, Any]:
    """Get information about all available tasks."""
    return {
        name: {
            "name": task.name,
            "description": task.__doc__,
            "queue": getattr(task, "queue", "default")
        }
        for name, task in AVAILABLE_TASKS.items()
    }