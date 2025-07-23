"""
Celery tasks for Nagatha Assistant core functionality.

This module defines Celery tasks that replace the event bus system
for agent operations, MCP server management, and event processing.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from celery import shared_task, current_task
from celery.exceptions import Retry

from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


# Event System Tasks

@shared_task(bind=True, name='nagatha_assistant.core.celery_tasks.events.publish_event')
def publish_event_task(self, event_type: str, data: Dict[str, Any], 
                      priority: int = 2, source: Optional[str] = None,
                      correlation_id: Optional[str] = None):
    """
    Publish an event through the Celery event system.
    
    Args:
        event_type: Type of the event (e.g., "agent.message.sent")
        data: Event data dictionary
        priority: Event priority (0=CRITICAL, 1=HIGH, 2=NORMAL, 3=LOW)
        source: Source of the event
        correlation_id: Correlation ID for tracking related events
    """
    try:
        # Create event metadata
        event_metadata = {
            'event_id': self.request.id,
            'event_type': event_type,
            'data': data,
            'priority': priority,
            'source': source or 'system',
            'correlation_id': correlation_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'task_id': self.request.id
        }
        
        logger.info(f"Publishing event: {event_type} (ID: {self.request.id})")
        
        # Store event in Redis for history/debugging
        from nagatha_assistant.core.celery_event_storage import store_event
        store_event(event_metadata)
        
        # Dispatch to subscribers based on event pattern
        dispatch_to_subscribers.delay(event_metadata)
        
        return {'success': True, 'event_id': self.request.id}
        
    except Exception as e:
        logger.error(f"Error publishing event {event_type}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.events.dispatch_to_subscribers')
def dispatch_to_subscribers(event_metadata: Dict[str, Any]):
    """
    Dispatch an event to all matching subscribers.
    
    Args:
        event_metadata: Complete event metadata including type, data, etc.
    """
    try:
        event_type = event_metadata['event_type']
        
        # Get subscribers for this event type
        from nagatha_assistant.core.celery_event_storage import get_subscribers
        subscribers = get_subscribers(event_type)
        
        # Dispatch to each subscriber
        for subscriber in subscribers:
            try:
                # Call subscriber task
                handle_event_subscription.delay(subscriber['handler_task'], event_metadata)
            except Exception as e:
                logger.error(f"Error dispatching to subscriber {subscriber['handler_task']}: {e}")
        
        logger.debug(f"Dispatched event {event_type} to {len(subscribers)} subscribers")
        return {'success': True, 'dispatched_count': len(subscribers)}
        
    except Exception as e:
        logger.error(f"Error dispatching event: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.events.handle_event_subscription')
def handle_event_subscription(handler_task: str, event_metadata: Dict[str, Any]):
    """
    Handle an event subscription by calling the appropriate handler task.
    
    Args:
        handler_task: Name of the Celery task to handle this event
        event_metadata: Event metadata
    """
    try:
        from celery import current_app
        
        # Call the handler task
        current_app.send_task(handler_task, args=[event_metadata])
        
        return {'success': True, 'handler': handler_task}
        
    except Exception as e:
        logger.error(f"Error handling event subscription for {handler_task}: {e}")
        return {'success': False, 'error': str(e)}


# Agent Tasks

@shared_task(bind=True, name='nagatha_assistant.core.celery_tasks.agent.process_message')
def process_message_task(self, session_id: int, message_content: str, 
                        message_type: str = 'user'):
    """
    Process a message through the agent system.
    
    Args:
        session_id: Session ID for the conversation
        message_content: Content of the message
        message_type: Type of message ('user' or 'assistant')
    """
    try:
        logger.info(f"Processing message for session {session_id}")
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'step': 'starting', 'progress': 10})
        
        # Store incoming message
        from nagatha_assistant.core.celery_storage import store_message
        message_id = store_message(session_id, message_content, message_type)
        
        self.update_state(state='PROGRESS', meta={'step': 'message_stored', 'progress': 20})
        
        # Publish message received event
        publish_event_task.delay(
            'agent.message.received',
            {
                'session_id': session_id,
                'message_id': message_id,
                'content': message_content,
                'message_type': message_type
            },
            source='agent'
        )
        
        if message_type == 'user':
            # Process with AI agent
            response = asyncio.run(process_with_ai_agent(session_id, message_content))
            
            self.update_state(state='PROGRESS', meta={'step': 'ai_processed', 'progress': 80})
            
            # Store response message
            response_id = store_message(session_id, response, 'assistant')
            
            # Publish response event
            publish_event_task.delay(
                'agent.message.sent',
                {
                    'session_id': session_id,
                    'message_id': response_id,
                    'content': response,
                    'message_type': 'assistant'
                },
                source='agent'
            )
            
            self.update_state(state='SUCCESS', meta={'response': response, 'message_id': response_id})
            return {'success': True, 'response': response, 'message_id': response_id}
        
        self.update_state(state='SUCCESS', meta={'message_id': message_id})
        return {'success': True, 'message_id': message_id}
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.agent.start_session')
def start_session_task(user_id: Optional[str] = None):
    """
    Start a new conversation session.
    
    Args:
        user_id: Optional user ID for the session
    """
    try:
        from nagatha_assistant.core.celery_storage import create_session
        
        session_id = create_session(user_id)
        
        # Publish session started event
        publish_event_task.delay(
            'agent.conversation.started',
            {
                'session_id': session_id,
                'user_id': user_id
            },
            source='agent'
        )
        
        logger.info(f"Started new session: {session_id}")
        return {'success': True, 'session_id': session_id}
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return {'success': False, 'error': str(e)}


# MCP Tasks

@shared_task(bind=True, name='nagatha_assistant.core.celery_tasks.mcp.call_tool')
def call_mcp_tool_task(self, tool_name: str, arguments: Dict[str, Any], 
                      server_name: Optional[str] = None):
    """
    Call an MCP tool through Celery.
    
    Args:
        tool_name: Name of the tool to call
        arguments: Arguments for the tool
        server_name: Optional specific server name
    """
    try:
        logger.info(f"Calling MCP tool: {tool_name}")
        
        self.update_state(state='PROGRESS', meta={'step': 'calling_tool', 'progress': 50})
        
        # Call the tool asynchronously
        result = asyncio.run(call_mcp_tool_async(tool_name, arguments, server_name))
        
        # Publish tool result event
        publish_event_task.delay(
            'mcp.tool.result',
            {
                'tool_name': tool_name,
                'arguments': arguments,
                'result': result,
                'server_name': server_name
            },
            source='mcp'
        )
        
        self.update_state(state='SUCCESS', meta={'result': result})
        return {'success': True, 'result': result}
        
    except Exception as e:
        logger.error(f"Error calling MCP tool {tool_name}: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.mcp.refresh_servers')
def refresh_mcp_servers_task():
    """
    Refresh MCP server connections and available tools.
    """
    try:
        # Refresh server connections
        status = asyncio.run(refresh_mcp_servers_async())
        
        # Publish server status update event
        publish_event_task.delay(
            'mcp.servers.refreshed',
            status,
            source='mcp'
        )
        
        return {'success': True, 'status': status}
        
    except Exception as e:
        logger.error(f"Error refreshing MCP servers: {e}")
        return {'success': False, 'error': str(e)}


# System Tasks

@shared_task(name='nagatha_assistant.core.celery_tasks.system.health_check')
def system_health_check_task():
    """
    Perform system health check.
    """
    try:
        from nagatha_assistant.core.celery_event_storage import get_system_status
        
        status = get_system_status()
        
        # Publish health status event
        publish_event_task.delay(
            'system.health.checked',
            status,
            source='system'
        )
        
        return {'success': True, 'status': status}
        
    except Exception as e:
        logger.error(f"Error in system health check: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.system.cleanup_old_data')
def cleanup_old_data_task():
    """
    Clean up old data from the system.
    """
    try:
        from nagatha_assistant.core.celery_event_storage import cleanup_old_data
        
        result = cleanup_old_data()
        
        publish_event_task.delay(
            'system.cleanup.completed',
            result,
            source='system'
        )
        
        return {'success': True, 'result': result}
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.system.memory_optimization')
def memory_optimization_task():
    """
    Perform memory optimization and garbage collection.
    """
    try:
        import gc
        import psutil
        import os
        
        # Get memory usage before optimization
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Force garbage collection
        collected = gc.collect()
        
        # Get memory usage after optimization
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_freed = memory_before - memory_after
        
        result = {
            'memory_before_mb': memory_before,
            'memory_after_mb': memory_after,
            'memory_freed_mb': memory_freed,
            'objects_collected': collected
        }
        
        publish_event_task.delay(
            'system.memory.optimized',
            result,
            source='system'
        )
        
        logger.info(f"Memory optimization completed: freed {memory_freed:.2f} MB")
        return {'success': True, 'result': result}
        
    except Exception as e:
        logger.error(f"Error in memory optimization: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.events.publish_system_status')
def publish_system_status_task():
    """
    Publish current system status as an event.
    """
    try:
        from nagatha_assistant.core.celery_event_storage import get_system_status
        
        status = get_system_status()
        
        publish_event_task.delay(
            'system.status.updated',
            status,
            priority=1,  # HIGH priority
            source='system'
        )
        
        return {'success': True, 'status': status}
        
    except Exception as e:
        logger.error(f"Error publishing system status: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='nagatha_assistant.core.celery_tasks.agent.check_stale_sessions')
def check_stale_sessions_task():
    """
    Check for and clean up stale sessions.
    """
    try:
        from nagatha_assistant.core.celery_event_storage import get_redis_client
        from datetime import datetime, timezone, timedelta
        
        redis_client = get_redis_client()
        
        # Get all active sessions
        session_ids = redis_client.smembers("active_sessions")
        stale_sessions = []
        current_time = datetime.now(timezone.utc)
        
        for session_id in session_ids:
            session_data = redis_client.hgetall(f"session:{session_id}")
            if session_data:
                last_activity_str = session_data.get('last_activity', '')
                if last_activity_str:
                    try:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        # Consider sessions stale after 24 hours of inactivity
                        if current_time - last_activity > timedelta(hours=24):
                            stale_sessions.append(session_id)
                    except Exception as e:
                        logger.warning(f"Error parsing last activity for session {session_id}: {e}")
        
        # Clean up stale sessions
        for session_id in stale_sessions:
            redis_client.srem("active_sessions", session_id)
            # Optionally, you could also delete session data here
            # redis_client.delete(f"session:{session_id}")
            # redis_client.delete(f"session_messages:{session_id}")
        
        result = {
            'total_sessions': len(session_ids),
            'stale_sessions': len(stale_sessions),
            'stale_session_ids': stale_sessions
        }
        
        if stale_sessions:
            publish_event_task.delay(
                'agent.sessions.cleaned',
                result,
                source='agent'
            )
        
        logger.info(f"Stale session check: {len(stale_sessions)} stale sessions cleaned")
        return {'success': True, 'result': result}
        
    except Exception as e:
        logger.error(f"Error checking stale sessions: {e}")
        return {'success': False, 'error': str(e)}


# Helper functions for async operations

async def process_with_ai_agent(session_id: int, message_content: str) -> str:
    """
    Process message with AI agent (async helper).
    """
    try:
        # Import here to avoid circular imports
        from nagatha_assistant.core.agent import _process_message_with_openai
        from nagatha_assistant.core.celery_storage import get_session_messages
        
        # Get conversation history
        messages = get_session_messages(session_id)
        
        # Convert to OpenAI format
        openai_messages = []
        for msg in messages:
            openai_messages.append({
                'role': 'user' if msg['type'] == 'user' else 'assistant',
                'content': msg['content']
            })
        
        # Add current message
        openai_messages.append({'role': 'user', 'content': message_content})
        
        # Process with OpenAI
        response = await _process_message_with_openai(openai_messages)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in AI agent processing: {e}")
        return f"I apologize, but I encountered an error processing your message: {str(e)}"


async def call_mcp_tool_async(tool_name: str, arguments: Dict[str, Any], 
                             server_name: Optional[str] = None) -> Any:
    """
    Call MCP tool asynchronously.
    """
    try:
        from nagatha_assistant.core.mcp_manager import get_mcp_manager
        
        mcp_manager = await get_mcp_manager()
        result = await mcp_manager.call_tool(tool_name, arguments, server_name)
        
        return result
        
    except Exception as e:
        logger.error(f"Error calling MCP tool async: {e}")
        raise


async def refresh_mcp_servers_async() -> Dict[str, Any]:
    """
    Refresh MCP servers asynchronously.
    """
    try:
        from nagatha_assistant.core.mcp_manager import get_mcp_manager
        
        mcp_manager = await get_mcp_manager()
        status = await mcp_manager.refresh_servers()
        
        return status
        
    except Exception as e:
        logger.error(f"Error refreshing MCP servers async: {e}")
        raise