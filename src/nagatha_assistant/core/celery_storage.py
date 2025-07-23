"""
Storage compatibility layer for Celery-based Nagatha system.

This module provides storage functions that work with both SQLAlchemy
and Redis backends, allowing gradual migration to the Celery system.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


# Session and Message Storage with dual backend support

async def create_session_async(user_id: Optional[str] = None) -> int:
    """
    Create a new conversation session (async version).
    
    Args:
        user_id: Optional user ID
        
    Returns:
        Session ID
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import create_session
        return create_session(user_id)
        
    except Exception as redis_error:
        logger.warning(f"Redis storage failed, falling back to SQLAlchemy: {redis_error}")
        
        try:
            # Fallback to SQLAlchemy
            from nagatha_assistant.db import SessionLocal
            from nagatha_assistant.db_models import ConversationSession
            
            async with SessionLocal() as session:
                new_session = ConversationSession(user_id=user_id)
                session.add(new_session)
                await session.commit()
                await session.refresh(new_session)
                return new_session.id
                
        except Exception as sql_error:
            logger.error(f"Both storage backends failed: Redis={redis_error}, SQL={sql_error}")
            raise


def create_session_sync(user_id: Optional[str] = None) -> int:
    """
    Create a new conversation session (sync version).
    
    Args:
        user_id: Optional user ID
        
    Returns:
        Session ID
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import create_session
        return create_session(user_id)
        
    except Exception as redis_error:
        logger.warning(f"Redis storage failed for sync session creation: {redis_error}")
        # For sync version, we can only use Redis since SQLAlchemy is async
        raise


async def store_message_async(session_id: int, content: str, message_type: str) -> str:
    """
    Store a message in a session (async version).
    
    Args:
        session_id: Session ID
        content: Message content
        message_type: Type of message ('user' or 'assistant')
        
    Returns:
        Message ID
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import store_message
        return store_message(session_id, content, message_type)
        
    except Exception as redis_error:
        logger.warning(f"Redis storage failed, falling back to SQLAlchemy: {redis_error}")
        
        try:
            # Fallback to SQLAlchemy
            from nagatha_assistant.db import SessionLocal
            from nagatha_assistant.db_models import ConversationSession, Message
            from sqlalchemy import select
            
            async with SessionLocal() as session:
                # Get the conversation session
                stmt = select(ConversationSession).where(ConversationSession.id == session_id)
                result = await session.execute(stmt)
                conv_session = result.scalar_one_or_none()
                
                if not conv_session:
                    raise ValueError(f"Session {session_id} not found")
                
                # Create message
                new_message = Message(
                    session_id=session_id,
                    content=content,
                    role='user' if message_type == 'user' else 'assistant'
                )
                session.add(new_message)
                await session.commit()
                await session.refresh(new_message)
                return str(new_message.id)
                
        except Exception as sql_error:
            logger.error(f"Both storage backends failed: Redis={redis_error}, SQL={sql_error}")
            raise


def store_message_sync(session_id: int, content: str, message_type: str) -> str:
    """
    Store a message in a session (sync version).
    
    Args:
        session_id: Session ID
        content: Message content
        message_type: Type of message ('user' or 'assistant')
        
    Returns:
        Message ID
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import store_message
        return store_message(session_id, content, message_type)
        
    except Exception as redis_error:
        logger.warning(f"Redis storage failed for sync message storage: {redis_error}")
        # For sync version, we can only use Redis since SQLAlchemy is async
        raise


async def get_session_messages_async(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get messages for a session (async version).
    
    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
        
    Returns:
        List of message data
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import get_session_messages
        return get_session_messages(session_id, limit)
        
    except Exception as redis_error:
        logger.warning(f"Redis storage failed, falling back to SQLAlchemy: {redis_error}")
        
        try:
            # Fallback to SQLAlchemy
            from nagatha_assistant.db import SessionLocal
            from nagatha_assistant.db_models import Message
            from sqlalchemy import select
            
            async with SessionLocal() as session:
                stmt = (select(Message)
                       .where(Message.session_id == session_id)
                       .order_by(Message.timestamp.desc())
                       .limit(limit))
                result = await session.execute(stmt)
                messages = result.scalars().all()
                
                # Convert to dict format
                message_list = []
                for msg in reversed(messages):  # Reverse for chronological order
                    message_list.append({
                        'id': str(msg.id),
                        'session_id': session_id,
                        'content': msg.content,
                        'type': 'user' if msg.role == 'user' else 'assistant',
                        'timestamp': msg.timestamp.isoformat()
                    })
                
                return message_list
                
        except Exception as sql_error:
            logger.error(f"Both storage backends failed: Redis={redis_error}, SQL={sql_error}")
            return []


def get_session_messages_sync(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get messages for a session (sync version).
    
    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
        
    Returns:
        List of message data
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import get_session_messages
        return get_session_messages(session_id, limit)
        
    except Exception as redis_error:
        logger.warning(f"Redis storage failed for sync message retrieval: {redis_error}")
        # For sync version, we can only use Redis since SQLAlchemy is async
        return []


# System Status Functions

async def get_system_status_async() -> Dict[str, Any]:
    """
    Get current system status (async version).
    
    Returns:
        System status dictionary
    """
    try:
        # Try Redis-based storage first
        from nagatha_assistant.core.celery_event_storage import get_system_status
        redis_status = get_system_status()
        
        # Enhance with additional system info
        try:
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            mcp_manager = await get_mcp_manager()
            mcp_status = await mcp_manager.get_status()
            
            redis_status.update({
                'mcp_servers_connected': len(mcp_status.get('servers', [])),
                'total_tools_available': sum(s.get('tools_count', 0) for s in mcp_status.get('servers', []))
            })
        except Exception as e:
            logger.warning(f"Could not get MCP status: {e}")
        
        return redis_status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            'system_health': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def get_system_status_sync() -> Dict[str, Any]:
    """
    Get current system status (sync version).
    
    Returns:
        System status dictionary
    """
    try:
        # Try Redis-based storage
        from nagatha_assistant.core.celery_event_storage import get_system_status
        return get_system_status()
        
    except Exception as e:
        logger.error(f"Error getting system status sync: {e}")
        return {
            'system_health': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


# Event Bus Bridge Functions

def get_event_bus():
    """
    Get the appropriate event bus based on configuration.
    
    Returns:
        Event bus instance (Celery-based if available, otherwise original)
    """
    try:
        # Try to use Celery event bus
        from nagatha_assistant.core.celery_event_bus import get_celery_event_bus
        return get_celery_event_bus()
        
    except Exception as e:
        logger.warning(f"Celery event bus not available, falling back to original: {e}")
        
        # Fallback to original event bus
        from nagatha_assistant.core.event_bus import get_event_bus as get_original_event_bus
        return get_original_event_bus()


async def ensure_event_bus_started():
    """
    Ensure the event bus is started.
    
    Returns:
        Started event bus instance
    """
    try:
        # Try Celery event bus first
        from nagatha_assistant.core.celery_event_bus import ensure_celery_event_bus_started
        return await ensure_celery_event_bus_started()
        
    except Exception as e:
        logger.warning(f"Celery event bus failed to start, falling back: {e}")
        
        # Fallback to original event bus
        from nagatha_assistant.core.event_bus import ensure_event_bus_started as ensure_original_started
        return await ensure_original_started()


async def shutdown_event_bus():
    """
    Shutdown the event bus.
    """
    try:
        # Try to shutdown Celery event bus
        from nagatha_assistant.core.celery_event_bus import shutdown_celery_event_bus
        await shutdown_celery_event_bus()
        
    except Exception as e:
        logger.warning(f"Error shutting down Celery event bus: {e}")
    
    try:
        # Also try to shutdown original event bus
        from nagatha_assistant.core.event_bus import shutdown_event_bus as shutdown_original
        await shutdown_original()
        
    except Exception as e:
        logger.warning(f"Error shutting down original event bus: {e}")


# Convenience functions for common operations

async def send_message_async(session_id: int, content: str) -> str:
    """
    Send a message and get AI response (async version).
    
    Args:
        session_id: Session ID
        content: Message content
        
    Returns:
        AI response content
    """
    try:
        # Use Celery task for processing
        from nagatha_assistant.core.celery_tasks import process_message_task
        
        task = process_message_task.delay(session_id, content, 'user')
        
        # Wait for result (with timeout)
        result = task.get(timeout=60)  # 60 second timeout
        
        if result.get('success'):
            return result.get('response', 'No response generated')
        else:
            raise Exception(result.get('error', 'Unknown error'))
            
    except Exception as e:
        logger.error(f"Error sending message async: {e}")
        return f"I apologize, but I encountered an error: {str(e)}"


def send_message_sync(session_id: int, content: str) -> str:
    """
    Send a message and get AI response (sync version - just queues the task).
    
    Args:
        session_id: Session ID
        content: Message content
        
    Returns:
        Task ID for tracking
    """
    try:
        # Use Celery task for processing
        from nagatha_assistant.core.celery_tasks import process_message_task
        
        task = process_message_task.delay(session_id, content, 'user')
        return task.id
        
    except Exception as e:
        logger.error(f"Error sending message sync: {e}")
        return ""


# Aliases for backward compatibility
create_session = create_session_sync
store_message = store_message_sync
get_session_messages = get_session_messages_sync
get_system_status = get_system_status_sync