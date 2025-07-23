"""
Celery tasks for the Nagatha Dashboard.

This module provides Celery tasks for the Nagatha Dashboard, including
both legacy Redis-based tasks and new Nagatha core integration tasks.
"""

import asyncio
import sys
import os
from pathlib import Path
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import Session, Message, SystemStatus, Task
from .nagatha_redis_adapter import NagathaRedisAdapter
from .nagatha_real_adapter import NagathaRealAdapter
from .nagatha_celery_integration import (
    process_message_with_nagatha,
    check_mcp_servers_health,
    cleanup_memory_and_maintenance,
    track_usage_metrics,
    process_scheduled_tasks,
    reload_mcp_configuration
)
import logging

logger = logging.getLogger(__name__)


def get_simple_response(message: str) -> str:
    """Provide a simple response when Nagatha is not available."""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        return "Hello! I'm Nagatha Assistant. I'm currently experiencing some technical difficulties, but I'm here to help with basic questions."
    elif any(word in message_lower for word in ['help', 'what can you do']):
        return "I'm Nagatha Assistant, an AI assistant designed to help with various tasks. I can help with conversations, answer questions, and assist with different tools. I'm currently in a limited mode due to technical issues."
    elif any(word in message_lower for word in ['status', 'health', 'working']):
        return "I'm currently experiencing some technical difficulties with my database connection. My core functionality is temporarily limited, but I'm still here to help with basic questions."
    else:
        return "I'm sorry, I'm currently experiencing technical difficulties with my database connection. I can still help with basic questions, but my full functionality is temporarily unavailable. Please try again later or contact support if the issue persists."


@shared_task(bind=True)
def test_minimal_orm(self):
    """Minimal test task that only does basic Django ORM operations."""
    task_record = None
    try:
        logger.info("Starting test_minimal_orm task")
        
        # Create a Task record to track this task
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='test_minimal_orm',
            description='Minimal ORM test task',
            status='running',
            started_at=timezone.now()
        )
        logger.info(f"Created task record: {task_record.id}")
        
        # Test 1: Simple count query
        session_count = Session.objects.count()
        logger.info(f"Session count: {session_count}")
        
        # Test 2: Simple get query
        if session_count > 0:
            first_session = Session.objects.first()
            logger.info(f"First session ID: {first_session.id}")
        
        # Test 3: Simple create query (only if we have a session)
        if session_count > 0:
            test_message = Message.objects.create(
                session=first_session,
                content="Test message from minimal ORM task",
                message_type='assistant'
            )
            logger.info(f"Created test message: {test_message.id}")
            
            # Test 4: Simple delete query
            test_message.delete()
            logger.info("Deleted test message")
        else:
            logger.info("No sessions found, skipping message creation test")
        
        # Update task record to completed
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = {'success': True, 'message': 'Minimal ORM test passed'}
        task_record.completed_at = timezone.now()
        task_record.save()
        
        logger.info("test_minimal_orm task completed successfully")
        return {'success': True, 'message': 'Minimal ORM test passed'}
        
    except Exception as e:
        logger.error(f"Error in test_minimal_orm: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update task record to failed
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def test_simple_message_task(self, session_id, content):
    """Minimal test task that only uses Django ORM - no async, no Nagatha core."""
    task_record = None
    try:
        logger.info(f"Starting test_simple_message_task for session {session_id}")
        
        # Create a Task record to track this task
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='test_simple_message_task',
            description=f'Simple message task for session {session_id}',
            status='running',
            started_at=timezone.now()
        )
        logger.info(f"Created task record: {task_record.id}")
        
        session = Session.objects.get(id=session_id)
        msg = Message.objects.create(
            session=session,
            content=content,
            message_type='assistant'
        )
        logger.info(f"Successfully created message {msg.id} in test task")
        
        # Update task record to completed
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = {'success': True, 'message_id': str(msg.id)}
        task_record.completed_at = timezone.now()
        task_record.save()
        
        return {'success': True, 'message_id': str(msg.id)}
    except Exception as e:
        logger.error(f"Error in test_simple_message_task: {e}")
        
        # Update task record to failed
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def test_django_orm(self):
    """Test basic Django ORM operations in Celery context."""
    task_record = None
    try:
        # Create a Task record to track this task
        task_record = Task.objects.create(
            celery_task_id=self.request.id,
            task_name='test_django_orm',
            description='Test Django ORM operations',
            status='running',
            started_at=timezone.now()
        )
        logger.info(f"Created task record: {task_record.id}")
        
        # Test basic database operations
        from django.db import connection
        
        # Test a simple query
        session_count = Session.objects.count()
        logger.info(f"Session count: {session_count}")
        
        # Test creating a simple record
        test_status = SystemStatus.objects.create(
            mcp_servers_connected=0,
            total_tools_available=0,
            active_sessions=0,
            system_health='test',
            additional_metrics={'test': True}
        )
        logger.info(f"Created test status: {test_status.id}")
        
        # Clean up
        test_status.delete()
        
        # Update task record to completed
        task_record.status = 'completed'
        task_record.progress = 100
        task_record.result = {'success': True, 'message': 'Django ORM test passed'}
        task_record.completed_at = timezone.now()
        task_record.save()
        
        return {'success': True, 'message': 'Django ORM test passed'}
        
    except Exception as e:
        logger.error(f"Django ORM test failed: {e}")
        
        # Update task record to failed
        if task_record:
            task_record.status = 'failed'
            task_record.error_message = str(e)
            task_record.completed_at = timezone.now()
            task_record.save()
        
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def process_user_message(self, session_id, message_content, user_id=None):
    """Process a user message with Nagatha Assistant using Redis storage."""
    print("DEBUG: process_user_message task started")
    logger.info("process_user_message task started")
    
    try:
        # Get or create the session
        session, created = Session.objects.get_or_create(
            id=session_id,
            defaults={'user_id': user_id}
        )
        
        # Create user message
        user_message = Message.objects.create(
            session=session,
            content=message_content,
            message_type='user'
        )
        
        print(f"DEBUG: User message created with ID: {user_message.id}")
        logger.info(f"User message created with ID: {user_message.id}")
        
        # Try to use real Nagatha adapter for full functionality
        try:
            print("DEBUG: Attempting to use real Nagatha adapter for message processing")
            logger.info("Attempting to use real Nagatha adapter for message processing")
            adapter = NagathaRealAdapter()
            print("DEBUG: NagathaRealAdapter created successfully")
            logger.info("NagathaRealAdapter created successfully")
            
            # Use asyncio.run() which properly handles the event loop
            try:
                # Process message with real Nagatha system
                print(f"DEBUG: Processing message with real Nagatha system")
                logger.info(f"Processing message with real Nagatha system")
                
                response = asyncio.run(
                    adapter.send_message(session.nagatha_session_id, message_content)
                )
                print(f"DEBUG: Nagatha response received: {response[:100]}...")
                logger.info(f"Nagatha response received: {response[:100]}...")
                
            except Exception as async_error:
                print(f"DEBUG: Async operation failed: {async_error}")
                logger.error(f"Async operation failed: {async_error}")
                logger.error(f"Async error type: {type(async_error)}")
                import traceback
                logger.error(f"Async error traceback: {traceback.format_exc()}")
                raise
                
        except Exception as nagatha_error:
            print(f"DEBUG: Real Nagatha adapter failed, falling back to simple response: {nagatha_error}")
            logger.warning(f"Real Nagatha adapter failed, falling back to simple response: {nagatha_error}")
            logger.warning(f"Nagatha error type: {type(nagatha_error)}")
            import traceback
            logger.warning(f"Nagatha error traceback: {traceback.format_exc()}")
            
            # Fallback to simple response
            response = get_simple_response(message_content)
        
        # Create assistant message
        assistant_message = Message.objects.create(
            session=session,
            content=response,
            message_type='assistant'
        )
        
        print(f"DEBUG: Assistant message created with ID: {assistant_message.id}")
        logger.info(f"Assistant message created with ID: {assistant_message.id}")
        
        # Update task result
        self.update_state(
            state='SUCCESS',
            meta={
                'session_id': session_id,
                'user_message_id': user_message.id,
                'assistant_message_id': assistant_message.id,
                'response': response[:100] + "..." if len(response) > 100 else response
            }
        )
        
        print("DEBUG: process_user_message task completed successfully")
        logger.info("process_user_message task completed successfully")
        
    except Exception as e:
        print(f"DEBUG: Task failed with error: {e}")
        logger.error(f"Task failed with error: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Error traceback: {traceback.format_exc()}")
        
        # Update task result with error
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@shared_task
def refresh_system_status():
    """Refresh system status information."""
    try:
        # Use the real Nagatha adapter to get actual MCP server and tool status
        adapter = NagathaRealAdapter()
        
        # Use asyncio.run() which properly handles the event loop
        try:
            # Run the async operation
            status_info = asyncio.run(adapter.get_system_status())
        except Exception as async_error:
            logger.error(f"Async operation failed: {async_error}")
            # Fallback to Redis adapter if real adapter fails
            logger.info("Falling back to Redis adapter")
            redis_adapter = NagathaRedisAdapter()
            status_info = asyncio.run(redis_adapter.get_system_status())
        
        # Create new status record
        SystemStatus.objects.create(
            mcp_servers_connected=status_info.get('mcp_servers_connected', 0),
            total_tools_available=status_info.get('total_tools_available', 0),
            active_sessions=status_info.get('active_sessions', 0),
            system_health=status_info.get('system_health', 'unknown'),
            cpu_usage=status_info.get('cpu_usage'),
            memory_usage=status_info.get('memory_usage'),
            disk_usage=status_info.get('disk_usage'),
            additional_metrics=status_info.get('additional_metrics', {})
        )
        
        # Clean up old status records (keep last 100)
        old_statuses = SystemStatus.objects.all()[100:]
        for status in old_statuses:
            status.delete()
        
        logger.info(f"System status refreshed: {status_info.get('mcp_servers_connected', 0)} servers, {status_info.get('total_tools_available', 0)} tools")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error refreshing system status: {e}")
        # Don't raise the exception, just log it and return failure
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_data():
    """Clean up old data from the database."""
    try:
        # Clean up old messages (keep last 1000 per session)
        for session in Session.objects.all():
            old_messages = session.messages.all()[1000:]
            for message in old_messages:
                message.delete()
        
        # Clean up completed tasks older than 7 days
        cutoff_date = timezone.now() - timezone.timedelta(days=7)
        old_tasks = Task.objects.filter(
            status__in=['completed', 'failed', 'cancelled'],
            completed_at__lt=cutoff_date
        )
        old_tasks.delete()
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        raise