"""
Django views for the Nagatha Dashboard.
"""
import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.conf import settings
from .models import Session, Message, SystemStatus, Task, UserPreferences
from .tasks import process_user_message, test_simple_message_task, test_minimal_orm

logger = logging.getLogger(__name__)


class ComponentsExampleView(TemplateView):
    """Example page showcasing Bootstrap 5 components."""
    template_name = 'dashboard/components_example.html'


class DashboardView(TemplateView):
    """Main dashboard view."""
    template_name = 'dashboard/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_openai_key'] = bool(settings.NAGATHA_OPENAI_API_KEY)
        
        # Get user theme preference if user is authenticated
        if self.request.user.is_authenticated:
            try:
                preferences = UserPreferences.objects.get(user=self.request.user)
                context['user_theme'] = preferences.theme
            except UserPreferences.DoesNotExist:
                context['user_theme'] = 'dark'  # Default to dark
        else:
            context['user_theme'] = 'dark'  # Default to dark
            
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
def test_minimal_orm_api(request):
    """API endpoint to test minimal ORM task."""
    try:
        logger.info("Starting test_minimal_orm_api")
        result = test_minimal_orm.delay()
        logger.info(f"Started minimal ORM test task: {result.id}")
        
        return JsonResponse({
            'success': True,
            'task_id': result.id,
            'message': 'Minimal ORM test task started'
        })
        
    except Exception as e:
        logger.error(f"Error in test_minimal_orm_api: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def test_simple_task_api(request):
    """Temporary API endpoint to test minimal Celery task."""
    try:
        logger.info("Starting test_simple_task_api")
        data = json.loads(request.body)
        session_id = data.get('session_id')
        content = data.get('content', 'Hello from Celery!')
        
        if not session_id:
            return JsonResponse({'error': 'session_id is required'}, status=400)
        
        logger.info(f"Triggering test task for session {session_id}")
        result = test_simple_message_task.delay(session_id, content)
        logger.info(f"Started test task: {result.id}")
        
        return JsonResponse({
            'success': True,
            'task_id': result.id,
            'message': 'Test task started'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in test_simple_task_api: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_message(request):
    """Send a message to Nagatha Assistant."""
    try:
        logger.info("Starting send_message view")
        data = json.loads(request.body)
        message_content = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not message_content:
            return JsonResponse({'error': 'Message content is required'}, status=400)
        
        logger.info(f"Processing message: {message_content[:50]}...")
        
        # Get or create session
        if session_id:
            try:
                logger.info(f"Getting existing session: {session_id}")
                session = Session.objects.get(id=session_id)
                if request.user.is_authenticated and session.user != request.user:
                    return JsonResponse({'error': 'Access denied'}, status=403)
            except Session.DoesNotExist:
                return JsonResponse({'error': 'Session not found'}, status=404)
        else:
            # Create new session
            logger.info("Creating new session")
            session = Session.objects.create(
                user=request.user if request.user.is_authenticated else None,
                title=message_content[:50] + ('...' if len(message_content) > 50 else '')
            )
            logger.info(f"Created session: {session.id}")
        
        # Save user message
        logger.info("Creating user message")
        user_message = Message.objects.create(
            session=session,
            content=message_content,
            message_type='user'
        )
        logger.info(f"Created user message: {user_message.id}")
        
        # Use proper process_user_message task instead of minimal ORM test
        logger.info("Starting process_user_message task")
        task = process_user_message.delay(str(session.id), message_content)
        logger.info(f"Started process_user_message task: {task.id}")
        
        logger.info("Sending success response")
        return JsonResponse({
            'success': True,
            'session_id': str(session.id),
            'message_id': str(user_message.id),
            'task_id': task.id
        })
        
    except json.JSONDecodeError:
        logger.error("JSON decode error")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        # Trigger status refresh in background
        # refresh_system_status.delay() # Temporarily removed
        
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
    """Health check endpoint for Docker health checks."""
    return JsonResponse({'status': 'healthy', 'service': 'nagatha_dashboard'})


@login_required
@require_http_methods(["GET"])
def get_user_preferences(request):
    """Get user preferences."""
    try:
        preferences, created = UserPreferences.objects.get_or_create(user=request.user)
        return JsonResponse({
            'success': True,
            'preferences': {
                'theme': preferences.theme,
                'language': preferences.language,
                'notifications_enabled': preferences.notifications_enabled,
                'auto_refresh_interval': preferences.auto_refresh_interval,
            }
        })
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        return JsonResponse({'error': 'Failed to get preferences'}, status=500)


@require_http_methods(["GET"])
def test_theme_api(request):
    """Test endpoint for theme API (no authentication required)."""
    return JsonResponse({
        'success': True,
        'message': 'Theme API is working',
        'current_theme': 'dark',
        'available_themes': ['light', 'dark', 'auto']
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_user_preferences(request):
    """Update user preferences."""
    try:
        data = json.loads(request.body)
        preferences, created = UserPreferences.objects.get_or_create(user=request.user)
        
        # Update theme if provided
        if 'theme' in data:
            if data['theme'] in ['light', 'dark', 'auto']:
                preferences.theme = data['theme']
            else:
                return JsonResponse({'error': 'Invalid theme value'}, status=400)
        
        # Update other preferences if provided
        if 'language' in data:
            preferences.language = data['language']
        if 'notifications_enabled' in data:
            preferences.notifications_enabled = data['notifications_enabled']
        if 'auto_refresh_interval' in data:
            preferences.auto_refresh_interval = data['auto_refresh_interval']
        
        preferences.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Preferences updated successfully',
            'preferences': {
                'theme': preferences.theme,
                'language': preferences.language,
                'notifications_enabled': preferences.notifications_enabled,
                'auto_refresh_interval': preferences.auto_refresh_interval,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        return JsonResponse({'error': 'Failed to update preferences'}, status=500)