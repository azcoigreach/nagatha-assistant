"""
Views for the Nagatha Dashboard.
"""
import asyncio
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.conf import settings
from .models import Session, Message, SystemStatus, Task
from .nagatha_adapter import NagathaAdapter
from .tasks import process_user_message, refresh_system_status
import logging

logger = logging.getLogger(__name__)


class DashboardView(TemplateView):
    """Main dashboard view."""
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent sessions
        if self.request.user.is_authenticated:
            recent_sessions = Session.objects.filter(
                user=self.request.user
            ).order_by('-updated_at')[:5]
        else:
            recent_sessions = Session.objects.filter(
                user=None
            ).order_by('-updated_at')[:5]
        
        # Get latest system status
        latest_status = SystemStatus.objects.first()
        
        # Get active tasks
        active_tasks = Task.objects.filter(
            status__in=['pending', 'running']
        ).order_by('-created_at')[:10]
        
        context.update({
            'recent_sessions': recent_sessions,
            'system_status': latest_status,
            'active_tasks': active_tasks,
            'has_openai_key': bool(settings.NAGATHA_OPENAI_API_KEY),
        })
        
        return context


@login_required
def session_detail(request, session_id):
    """Display a specific chat session."""
    session = get_object_or_404(Session, id=session_id, user=request.user)
    messages = session.messages.all().order_by('created_at')
    
    context = {
        'session': session,
        'messages': messages,
    }
    
    return render(request, 'dashboard/session_detail.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def send_message(request):
    """Send a message to Nagatha Assistant."""
    try:
        data = json.loads(request.body)
        message_content = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not message_content:
            return JsonResponse({'error': 'Message content is required'}, status=400)
        
        # Get or create session
        if session_id:
            try:
                session = Session.objects.get(id=session_id)
                if request.user.is_authenticated and session.user != request.user:
                    return JsonResponse({'error': 'Access denied'}, status=403)
            except Session.DoesNotExist:
                return JsonResponse({'error': 'Session not found'}, status=404)
        else:
            # Create new session
            session = Session.objects.create(
                user=request.user if request.user.is_authenticated else None,
                title=message_content[:50] + ('...' if len(message_content) > 50 else '')
            )
        
        # Save user message
        user_message = Message.objects.create(
            session=session,
            content=message_content,
            message_type='user'
        )
        
        # Process message asynchronously
        task = process_user_message.delay(
            session_id=str(session.id),
            message_content=message_content,
            user_id=request.user.id if request.user.is_authenticated else None
        )
        
        # Create task record
        Task.objects.create(
            celery_task_id=task.id,
            user=request.user if request.user.is_authenticated else None,
            session=session,
            task_name='process_message',
            description=f'Processing message: {message_content[:50]}...'
        )
        
        return JsonResponse({
            'success': True,
            'session_id': str(session.id),
            'message_id': str(user_message.id),
            'task_id': task.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["GET"])
def get_session_messages(request, session_id):
    """Get messages for a session."""
    try:
        session = Session.objects.get(id=session_id)
        
        # Check permissions
        if request.user.is_authenticated and session.user != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        messages = session.messages.all().order_by('created_at')
        
        messages_data = [{
            'id': str(msg.id),
            'content': msg.content,
            'message_type': msg.message_type,
            'created_at': msg.created_at.isoformat(),
            'metadata': msg.metadata
        } for msg in messages]
        
        return JsonResponse({
            'session_id': str(session.id),
            'messages': messages_data
        })
        
    except Session.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["GET"])
def system_status(request):
    """Get current system status."""
    try:
        # Trigger status refresh
        refresh_system_status.delay()
        
        # Get latest status
        latest_status = SystemStatus.objects.first()
        
        if latest_status:
            status_data = {
                'timestamp': latest_status.timestamp.isoformat(),
                'mcp_servers_connected': latest_status.mcp_servers_connected,
                'total_tools_available': latest_status.total_tools_available,
                'active_sessions': latest_status.active_sessions,
                'system_health': latest_status.system_health,
                'cpu_usage': latest_status.cpu_usage,
                'memory_usage': latest_status.memory_usage,
                'disk_usage': latest_status.disk_usage,
                'additional_metrics': latest_status.additional_metrics
            }
        else:
            status_data = {
                'timestamp': None,
                'mcp_servers_connected': 0,
                'total_tools_available': 0,
                'active_sessions': 0,
                'system_health': 'unknown',
                'cpu_usage': None,
                'memory_usage': None,
                'disk_usage': None,
                'additional_metrics': {}
            }
        
        return JsonResponse(status_data)
        
    except Exception as e:
        logger.error(f"Error fetching system status: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["GET"])
def task_status(request, task_id):
    """Get task status."""
    try:
        task = Task.objects.get(celery_task_id=task_id)
        
        # Check permissions
        if request.user.is_authenticated and task.user != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        task_data = {
            'id': str(task.id),
            'celery_task_id': task.celery_task_id,
            'task_name': task.task_name,
            'description': task.description,
            'status': task.status,
            'progress': task.progress,
            'result': task.result,
            'error_message': task.error_message,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        }
        
        return JsonResponse(task_data)
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching task status: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def health_check(request):
    """Health check endpoint for Docker/monitoring."""
    try:
        # Basic health checks
        latest_status = SystemStatus.objects.first()
        
        health_data = {
            'status': 'healthy',
            'timestamp': latest_status.timestamp.isoformat() if latest_status else None,
            'database': 'connected',
            'has_openai_key': bool(settings.NAGATHA_OPENAI_API_KEY),
        }
        
        return JsonResponse(health_data)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)