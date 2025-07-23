"""
Nagatha Core Features Integration with Celery Platform.

This module implements the integration plan from issue #43, providing
Celery tasks that interface with Nagatha's core features including:
- Chat/message processing with async handling
- MCP server management and health checks
- Memory management and cleanup
- Metrics and usage tracking
- Task and reminder scheduling
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from celery import shared_task
from django.utils import timezone as django_timezone
from django.conf import settings

# Add Nagatha source to path for imports
nagatha_src_path = Path(settings.BASE_DIR).parent / "src"
if nagatha_src_path.exists():
    sys.path.insert(0, str(nagatha_src_path))

logger = logging.getLogger(__name__)


class NagathaCeleryBridge:
    """
    Bridge class to handle async/sync conversion between Celery and Nagatha's async core.
    
    This provides a clean interface for Celery tasks to interact with Nagatha's
    async-first architecture while handling the event loop properly.
    """
    
    def __init__(self):
        self._initialized = False
        self._agent = None
        self._mcp_manager = None
        self._memory_manager = None
        self._event_bus = None
        self._plugin_manager = None
    
    async def _ensure_initialized(self):
        """Ensure Nagatha core components are initialized."""
        if self._initialized:
            return
            
        try:
            # Import Nagatha core modules
            from nagatha_assistant.core.agent import startup as agent_startup
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            from nagatha_assistant.core.memory import get_memory_manager
            from nagatha_assistant.core.event_bus import get_event_bus
            from nagatha_assistant.core.plugin_manager import get_plugin_manager
            
            # Initialize agent and get components
            init_summary = await agent_startup()
            self._agent = agent_startup  # Store reference to startup function
            
            # Get core managers
            self._mcp_manager = await get_mcp_manager()
            self._memory_manager = get_memory_manager()
            self._event_bus = get_event_bus()
            self._plugin_manager = get_plugin_manager()
            
            self._initialized = True
            logger.info("Nagatha Celery bridge initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Nagatha Celery bridge: {e}")
            raise
    
    def _run_async(self, coro):
        """Run an async coroutine in a new event loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    async def process_message_async(self, session_id: int, message: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Process a user message using Nagatha's core agent."""
        await self._ensure_initialized()
        
        try:
            from nagatha_assistant.core.agent import send_message, start_session
            
            # Create session if needed
            if session_id is None:
                session_id = await start_session()
            
            # Send message and get response
            response = await send_message(session_id, message)
            
            return {
                'success': True,
                'session_id': session_id,
                'response': response,
                'user_id': user_id
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                'success': False,
                'error': str(e),
                'session_id': session_id,
                'user_id': user_id
            }
    
    async def check_mcp_servers_async(self) -> Dict[str, Any]:
        """Check MCP server health and status."""
        await self._ensure_initialized()
        
        try:
            # Get MCP status
            mcp_status = self._mcp_manager.get_initialization_summary()
            server_info = self._mcp_manager.get_server_info()
            
            # Check each server's connection
            health_checks = {}
            for server_name, info in server_info.items():
                try:
                    # Test connection to each server
                    config = self._mcp_manager.servers.get(server_name)
                    if config:
                        is_connected = await self._mcp_manager._test_and_discover_server(config)
                        health_checks[server_name] = {
                            'connected': is_connected,
                            'tools_count': len([t for t in self._mcp_manager.tools.values() if t.server_name == server_name]),
                            'last_check': datetime.now(timezone.utc).isoformat()
                        }
                except Exception as e:
                    health_checks[server_name] = {
                        'connected': False,
                        'error': str(e),
                        'last_check': datetime.now(timezone.utc).isoformat()
                    }
            
            return {
                'success': True,
                'mcp_status': mcp_status,
                'server_info': server_info,
                'health_checks': health_checks,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking MCP servers: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_memory_async(self) -> Dict[str, Any]:
        """Clean up memory and perform maintenance tasks."""
        await self._ensure_initialized()
        
        try:
            # Clean up expired temporary entries
            if self._memory_manager:
                # The memory manager has an internal cleanup loop, so we just get stats
                stats = await self._memory_manager.get_storage_stats()
                cleanup_result = {
                    'cleaned_entries': 0,  # Cleanup is automatic
                    'cleanup_running': stats.get('cleanup_running', False)
                }
            else:
                cleanup_result = {'cleaned_entries': 0}
            
            # Get memory statistics
            if self._memory_manager:
                stats = await self._memory_manager.get_storage_stats()
            else:
                stats = {'total_entries': 0, 'sections': {}}
            
            return {
                'success': True,
                'cleanup_result': cleanup_result,
                'memory_stats': stats,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up memory: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def track_usage_metrics_async(self) -> Dict[str, Any]:
        """Track usage metrics and costs."""
        await self._ensure_initialized()
        
        try:
            from nagatha_assistant.utils.usage_tracker import load_usage, get_reset_info
            
            # Get current usage data
            usage_data = load_usage()
            reset_info = get_reset_info()
            
            # Calculate daily totals
            daily_totals = {}
            total_cost = 0.0
            total_requests = 0
            
            for model, data in usage_data.items():
                if 'daily_usage' in data:
                    daily_data = data['daily_usage']
                    today = datetime.now().strftime('%Y-%m-%d')
                    
                    if today in daily_data:
                        daily_totals[model] = daily_data[today]
                        total_cost += daily_data[today].get('cost', 0)
                        total_requests += daily_data[today].get('requests', 0)
            
            return {
                'success': True,
                'usage_data': usage_data,
                'daily_totals': daily_totals,
                'total_cost': total_cost,
                'total_requests': total_requests,
                'reset_info': reset_info,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error tracking usage metrics: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def process_scheduled_tasks_async(self) -> Dict[str, Any]:
        """Process scheduled tasks and reminders."""
        await self._ensure_initialized()
        
        try:
            # Note: Task and reminder modules are not yet implemented
            # This is a placeholder for future implementation
            processed_tasks = []
            processed_reminders = []
            
            # For now, return a success response indicating no tasks to process
            return {
                'success': True,
                'due_tasks': 0,
                'due_reminders': 0,
                'processed_tasks': processed_tasks,
                'processed_reminders': processed_reminders,
                'note': 'Task and reminder modules not yet implemented',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing scheduled tasks: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }


# Global bridge instance
_nagatha_bridge = None

def get_nagatha_bridge() -> NagathaCeleryBridge:
    """Get the global Nagatha Celery bridge instance."""
    global _nagatha_bridge
    if _nagatha_bridge is None:
        _nagatha_bridge = NagathaCeleryBridge()
    return _nagatha_bridge


# Celery Tasks

@shared_task(bind=True)
def process_message_with_nagatha(self, session_id: Optional[int], message: str, user_id: Optional[str] = None):
    """Process a user message using Nagatha's core agent via Celery."""
    task_record = None
    try:
        from .models import Task, Session, Message as DjangoMessage
        
        # Create task record
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='process_message_with_nagatha',
            description=f'Process message: {message[:50]}...',
            status='running',
            started_at=django_timezone.now()
        )
        
        # Get Nagatha bridge
        bridge = get_nagatha_bridge()
        
        # Process message
        result = bridge._run_async(
            bridge.process_message_async(session_id, message, user_id)
        )
        
        # Update task record
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = result
        task_record.completed_at = django_timezone.now()
        task_record.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in process_message_with_nagatha: {e}")
        
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = django_timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def check_mcp_servers_health(self):
    """Check MCP server health and status via Celery."""
    task_record = None
    try:
        from .models import Task
        
        # Create task record
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='check_mcp_servers_health',
            description='Check MCP server health and status',
            status='running',
            started_at=django_timezone.now()
        )
        
        # Get Nagatha bridge
        bridge = get_nagatha_bridge()
        
        # Check MCP servers
        result = bridge._run_async(bridge.check_mcp_servers_async())
        
        # Update task record
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = result
        task_record.completed_at = django_timezone.now()
        task_record.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in check_mcp_servers_health: {e}")
        
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = django_timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def cleanup_memory_and_maintenance(self):
    """Clean up memory and perform maintenance tasks via Celery."""
    task_record = None
    try:
        from .models import Task
        
        # Create task record
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='cleanup_memory_and_maintenance',
            description='Clean up memory and perform maintenance',
            status='running',
            started_at=django_timezone.now()
        )
        
        # Get Nagatha bridge
        bridge = get_nagatha_bridge()
        
        # Clean up memory
        result = bridge._run_async(bridge.cleanup_memory_async())
        
        # Update task record
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = result
        task_record.completed_at = django_timezone.now()
        task_record.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in cleanup_memory_and_maintenance: {e}")
        
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = django_timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def track_usage_metrics(self):
    """Track usage metrics and costs via Celery."""
    task_record = None
    try:
        from .models import Task
        
        # Create task record
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='track_usage_metrics',
            description='Track usage metrics and costs',
            status='running',
            started_at=django_timezone.now()
        )
        
        # Get Nagatha bridge
        bridge = get_nagatha_bridge()
        
        # Track usage
        result = bridge._run_async(bridge.track_usage_metrics_async())
        
        # Update task record
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = result
        task_record.completed_at = django_timezone.now()
        task_record.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in track_usage_metrics: {e}")
        
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = django_timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def process_scheduled_tasks(self):
    """Process scheduled tasks and reminders via Celery."""
    task_record = None
    try:
        from .models import Task
        
        # Create task record
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='process_scheduled_tasks',
            description='Process scheduled tasks and reminders',
            status='running',
            started_at=django_timezone.now()
        )
        
        # Get Nagatha bridge
        bridge = get_nagatha_bridge()
        
        # Process scheduled tasks
        result = bridge._run_async(bridge.process_scheduled_tasks_async())
        
        # Update task record
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = result
        task_record.completed_at = django_timezone.now()
        task_record.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in process_scheduled_tasks: {e}")
        
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = django_timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def reload_mcp_configuration(self):
    """Reload MCP configuration via Celery."""
    task_record = None
    try:
        from .models import Task
        
        # Create task record
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='reload_mcp_configuration',
            description='Reload MCP server configuration',
            status='running',
            started_at=django_timezone.now()
        )
        
        # Get Nagatha bridge
        bridge = get_nagatha_bridge()
        bridge._run_async(bridge._ensure_initialized())
        
        # Reload MCP configuration
        result = bridge._run_async(bridge._mcp_manager.reload_configuration())
        
        # Update task record
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = {'success': True, 'message': 'MCP configuration reloaded'}
        task_record.completed_at = django_timezone.now()
        task_record.save()
        
        return {'success': True, 'message': 'MCP configuration reloaded'}
        
    except Exception as e:
        logger.error(f"Error in reload_mcp_configuration: {e}")
        
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = django_timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)} 