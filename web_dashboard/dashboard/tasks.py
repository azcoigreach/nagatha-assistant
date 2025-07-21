"""
Celery tasks for the Nagatha Dashboard.
"""
import asyncio
import sys
import os
from pathlib import Path
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import Session, Message, SystemStatus, Task
from .nagatha_adapter import NagathaAdapter
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_user_message(self, session_id, message_content, user_id=None):
    """Process a user message with Nagatha Assistant."""
    try:
        # Update task status
        task_record = Task.objects.filter(celery_task_id=self.request.id).first()
        if task_record:
            task_record.status = 'running'
            task_record.started_at = timezone.now()
            task_record.save()
        
        # Get session
        session = Session.objects.get(id=session_id)
        
        # Initialize Nagatha adapter
        adapter = NagathaAdapter()
        
        # Send message to Nagatha
        # Create a new event loop for this task to avoid conflicts with Celery
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(adapter.send_message(
                session_id=session.nagatha_session_id,
                message=message_content
            ))
        finally:
            loop.close()
        
        # Save assistant response
        assistant_message = Message.objects.create(
            session=session,
            content=response,
            message_type='assistant'
        )
        
        # Update task status
        if task_record:
            task_record.status = 'completed'
            task_record.completed_at = timezone.now()
            task_record.progress = 100
            task_record.result = {
                'response_message_id': str(assistant_message.id),
                'response_length': len(response)
            }
            task_record.save()
        
        return {
            'success': True,
            'response_message_id': str(assistant_message.id)
        }
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        
        # Update task status
        if task_record:
            task_record.status = 'failed'
            task_record.completed_at = timezone.now()
            task_record.error_message = str(e)
            task_record.save()
        
        # Save error message
        try:
            session = Session.objects.get(id=session_id)
            Message.objects.create(
                session=session,
                content=f"Sorry, I encountered an error: {str(e)}",
                message_type='error'
            )
        except Exception:
            pass
        
        raise


@shared_task
def refresh_system_status():
    """Refresh system status information."""
    try:
        adapter = NagathaAdapter()
        # Create a new event loop for this task to avoid conflicts with Celery
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            status_info = loop.run_until_complete(adapter.get_system_status())
        finally:
            loop.close()
        
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
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error refreshing system status: {e}")
        raise


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