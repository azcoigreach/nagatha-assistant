"""
Django-Nagatha Bridge for Celery Integration.

This module provides functions to bridge between the Django web dashboard
and the new Nagatha Celery-based event system.
"""

import asyncio
import logging
import os
import sys

# Add Nagatha src to path
nagatha_src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src')
if nagatha_src not in sys.path:
    sys.path.insert(0, nagatha_src)

logger = logging.getLogger(__name__)


def use_nagatha_celery_system(session_id: int, message_content: str) -> str:
    """
    Use the new Nagatha Celery system to process a message.
    
    Args:
        session_id: Django session ID (will be mapped to Nagatha session)
        message_content: User message content
        
    Returns:
        AI response from Nagatha
    """
    try:
        # Import Nagatha's Celery-based functions
        from nagatha_assistant.core.celery_storage import send_message_async
        from nagatha_assistant.core.celery_tasks import process_message_task
        
        # For synchronous Django views, we'll use the Celery task directly
        task = process_message_task.delay(session_id, message_content, 'user')
        
        # Wait for result (with timeout)
        result = task.get(timeout=60)
        
        if result.get('success'):
            return result.get('response', 'No response generated')
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"Nagatha Celery processing failed: {error}")
            return f"I apologize, but I encountered an error: {error}"
            
    except Exception as e:
        logger.error(f"Error using Nagatha Celery system: {e}")
        # Fall back to error message
        return f"I'm sorry, I'm experiencing technical difficulties: {str(e)}"


def get_nagatha_session_status(session_id: int) -> dict:
    """
    Get status information for a Nagatha session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Status dictionary
    """
    try:
        from nagatha_assistant.core.celery_event_storage import get_session_messages, get_system_status
        
        # Get session messages
        messages = get_session_messages(session_id, limit=10)
        
        # Get system status
        system_status = get_system_status()
        
        return {
            'session_id': session_id,
            'message_count': len(messages),
            'last_messages': messages[:5],  # Last 5 messages
            'system_health': system_status.get('system_health', 'unknown'),
            'redis_connected': system_status.get('redis_connected', False)
        }
        
    except Exception as e:
        logger.error(f"Error getting Nagatha session status: {e}")
        return {
            'session_id': session_id,
            'error': str(e),
            'system_health': 'error'
        }


def start_nagatha_session(user_id: str = None) -> int:
    """
    Start a new Nagatha session.
    
    Args:
        user_id: Optional user ID
        
    Returns:
        Session ID
    """
    try:
        from nagatha_assistant.core.celery_tasks import start_session_task
        
        task = start_session_task.delay(user_id)
        result = task.get(timeout=30)
        
        if result.get('success'):
            return result.get('session_id')
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"Failed to start Nagatha session: {error}")
            raise Exception(f"Failed to start session: {error}")
            
    except Exception as e:
        logger.error(f"Error starting Nagatha session: {e}")
        raise


def publish_event_to_nagatha(event_type: str, data: dict, priority: int = 2) -> bool:
    """
    Publish an event to the Nagatha event system.
    
    Args:
        event_type: Type of event
        data: Event data
        priority: Event priority (0=CRITICAL, 1=HIGH, 2=NORMAL, 3=LOW)
        
    Returns:
        True if successful
    """
    try:
        from nagatha_assistant.core.celery_tasks import publish_event_task
        
        task = publish_event_task.delay(event_type, data, priority, 'django_dashboard')
        # Don't wait for result, just fire and forget
        
        return True
        
    except Exception as e:
        logger.error(f"Error publishing event to Nagatha: {e}")
        return False


def get_nagatha_system_health() -> dict:
    """
    Get Nagatha system health information.
    
    Returns:
        Health status dictionary
    """
    try:
        from nagatha_assistant.core.celery_tasks import system_health_check_task
        
        task = system_health_check_task.delay()
        result = task.get(timeout=30)
        
        if result.get('success'):
            return result.get('status', {})
        else:
            return {'system_health': 'error', 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"Error getting Nagatha system health: {e}")
        return {'system_health': 'error', 'error': str(e)}


def check_nagatha_celery_availability() -> bool:
    """
    Check if the Nagatha Celery system is available.
    
    Returns:
        True if Celery system is available
    """
    try:
        # Try to import core modules
        from nagatha_assistant.core.celery_tasks import publish_event_task
        from nagatha_assistant.core.celery_event_storage import get_system_status
        
        # Test Redis connectivity
        status = get_system_status()
        return status.get('redis_connected', False)
        
    except ImportError:
        logger.warning("Nagatha Celery modules not available")
        return False
    except Exception as e:
        logger.warning(f"Nagatha Celery system not available: {e}")
        return False


# Convenience function for Django views
def process_message_with_nagatha(session_id: int, message_content: str, 
                                use_celery: bool = True) -> dict:
    """
    Process a message with Nagatha, with fallback options.
    
    Args:
        session_id: Session ID
        message_content: Message content
        use_celery: Whether to try Celery system first
        
    Returns:
        Result dictionary with response and metadata
    """
    result = {
        'success': False,
        'response': '',
        'method': 'unknown',
        'error': None
    }
    
    if use_celery and check_nagatha_celery_availability():
        try:
            response = use_nagatha_celery_system(session_id, message_content)
            result.update({
                'success': True,
                'response': response,
                'method': 'celery'
            })
            return result
        except Exception as e:
            logger.warning(f"Celery processing failed, will try fallback: {e}")
            result['error'] = str(e)
    
    # Fallback to existing Django task processing
    try:
        from .nagatha_redis_adapter import NagathaRedisAdapter
        
        adapter = NagathaRedisAdapter()
        response = asyncio.run(adapter.send_message(session_id, message_content))
        
        result.update({
            'success': True,
            'response': response,
            'method': 'redis_adapter'
        })
        return result
        
    except Exception as e:
        logger.error(f"All processing methods failed: {e}")
        result.update({
            'success': False,
            'response': f"I apologize, but I'm experiencing technical difficulties: {str(e)}",
            'method': 'error_fallback',
            'error': str(e)
        })
        return result