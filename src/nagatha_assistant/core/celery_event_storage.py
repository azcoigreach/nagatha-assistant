"""
Redis-based storage for the Celery event system.

This module provides storage functions for events, subscribers, and
session data using Redis as the backend.
"""

import json
import logging
import redis
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()

# Redis connection
_redis_client = None


def get_redis_client():
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        import os
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


# Event Storage Functions

def store_event(event_metadata: Dict[str, Any]):
    """
    Store an event in Redis for history and debugging.
    
    Args:
        event_metadata: Complete event metadata
    """
    try:
        redis_client = get_redis_client()
        event_id = event_metadata['event_id']
        
        # Store event data
        redis_client.hset(f"event:{event_id}", mapping=event_metadata)
        
        # Add to event history list (with expiration)
        redis_client.lpush("event_history", event_id)
        redis_client.ltrim("event_history", 0, 999)  # Keep last 1000 events
        
        # Add to event type index
        event_type = event_metadata['event_type']
        redis_client.sadd(f"events_by_type:{event_type}", event_id)
        
        # Set expiration for individual event (24 hours)
        redis_client.expire(f"event:{event_id}", 86400)
        
        logger.debug(f"Stored event {event_id} of type {event_type}")
        
    except Exception as e:
        logger.error(f"Error storing event: {e}")


def get_event_history(limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get event history from Redis.
    
    Args:
        limit: Maximum number of events to return
        event_type: Optional filter by event type
        
    Returns:
        List of event metadata dictionaries
    """
    try:
        redis_client = get_redis_client()
        events = []
        
        if event_type:
            # Get events by type
            event_ids = redis_client.smembers(f"events_by_type:{event_type}")
            # Limit the results
            event_ids = list(event_ids)[:limit]
        else:
            # Get from general history
            event_ids = redis_client.lrange("event_history", 0, limit - 1)
        
        for event_id in event_ids:
            event_data = redis_client.hgetall(f"event:{event_id}")
            if event_data:
                events.append(event_data)
        
        return events
        
    except Exception as e:
        logger.error(f"Error getting event history: {e}")
        return []


# Subscription Management

def add_subscriber(pattern: str, handler_task: str, priority_filter: Optional[int] = None,
                  source_filter: Optional[str] = None) -> str:
    """
    Add a subscriber for events matching a pattern.
    
    Args:
        pattern: Event type pattern (supports wildcards)
        handler_task: Celery task name to handle matching events
        priority_filter: Only receive events with this priority or higher
        source_filter: Only receive events from this source
        
    Returns:
        Subscription ID
    """
    try:
        redis_client = get_redis_client()
        subscription_id = str(uuid.uuid4())
        
        subscription_data = {
            'id': subscription_id,
            'pattern': pattern,
            'handler_task': handler_task,
            'priority_filter': priority_filter or '',
            'source_filter': source_filter or '',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Store subscription
        redis_client.hset(f"subscription:{subscription_id}", mapping=subscription_data)
        
        # Add to pattern index
        redis_client.sadd(f"subscriptions_by_pattern:{pattern}", subscription_id)
        
        # Add to global subscriptions list
        redis_client.sadd("all_subscriptions", subscription_id)
        
        logger.debug(f"Added subscriber {subscription_id} for pattern {pattern}")
        return subscription_id
        
    except Exception as e:
        logger.error(f"Error adding subscriber: {e}")
        return ""


def remove_subscriber(subscription_id: str) -> bool:
    """
    Remove a subscriber.
    
    Args:
        subscription_id: ID of subscription to remove
        
    Returns:
        True if subscription was found and removed
    """
    try:
        redis_client = get_redis_client()
        
        # Get subscription data first
        subscription_data = redis_client.hgetall(f"subscription:{subscription_id}")
        if not subscription_data:
            return False
        
        pattern = subscription_data['pattern']
        
        # Remove from pattern index
        redis_client.srem(f"subscriptions_by_pattern:{pattern}", subscription_id)
        
        # Remove from global list
        redis_client.srem("all_subscriptions", subscription_id)
        
        # Remove subscription data
        redis_client.delete(f"subscription:{subscription_id}")
        
        logger.debug(f"Removed subscriber {subscription_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error removing subscriber: {e}")
        return False


def get_subscribers(event_type: str) -> List[Dict[str, Any]]:
    """
    Get all subscribers that match an event type.
    
    Args:
        event_type: Event type to match against
        
    Returns:
        List of matching subscriber data
    """
    try:
        redis_client = get_redis_client()
        subscribers = []
        
        # Get all subscription IDs
        subscription_ids = redis_client.smembers("all_subscriptions")
        
        for subscription_id in subscription_ids:
            subscription_data = redis_client.hgetall(f"subscription:{subscription_id}")
            if not subscription_data:
                continue
            
            pattern = subscription_data['pattern']
            
            # Check if pattern matches event type
            if matches_pattern(event_type, pattern):
                subscribers.append(subscription_data)
        
        return subscribers
        
    except Exception as e:
        logger.error(f"Error getting subscribers: {e}")
        return []


def matches_pattern(event_type: str, pattern: str) -> bool:
    """
    Check if an event type matches a pattern.
    
    Args:
        event_type: Event type to check
        pattern: Pattern to match against (supports * wildcards)
        
    Returns:
        True if pattern matches
    """
    import fnmatch
    return fnmatch.fnmatch(event_type, pattern)


# Session and Message Storage

def create_session(user_id: Optional[str] = None) -> int:
    """
    Create a new conversation session.
    
    Args:
        user_id: Optional user ID
        
    Returns:
        Session ID
    """
    try:
        redis_client = get_redis_client()
        
        # Generate session ID
        session_id = int(redis_client.incr("session_counter"))
        
        session_data = {
            'id': session_id,
            'user_id': user_id or '',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_activity': datetime.now(timezone.utc).isoformat()
        }
        
        # Store session data
        redis_client.hset(f"session:{session_id}", mapping=session_data)
        
        # Add to active sessions
        redis_client.sadd("active_sessions", session_id)
        
        logger.debug(f"Created session {session_id}")
        return session_id
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise


def store_message(session_id: int, content: str, message_type: str) -> str:
    """
    Store a message in a session.
    
    Args:
        session_id: Session ID
        content: Message content
        message_type: Type of message ('user' or 'assistant')
        
    Returns:
        Message ID
    """
    try:
        redis_client = get_redis_client()
        
        message_id = str(uuid.uuid4())
        
        message_data = {
            'id': message_id,
            'session_id': session_id,
            'content': content,
            'type': message_type,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Store message data
        redis_client.hset(f"message:{message_id}", mapping=message_data)
        
        # Add to session message list
        redis_client.lpush(f"session_messages:{session_id}", message_id)
        
        # Update session last activity
        redis_client.hset(f"session:{session_id}", "last_activity", 
                         datetime.now(timezone.utc).isoformat())
        
        logger.debug(f"Stored message {message_id} in session {session_id}")
        return message_id
        
    except Exception as e:
        logger.error(f"Error storing message: {e}")
        raise


def get_session_messages(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get messages for a session.
    
    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
        
    Returns:
        List of message data
    """
    try:
        redis_client = get_redis_client()
        
        # Get message IDs (most recent first)
        message_ids = redis_client.lrange(f"session_messages:{session_id}", 0, limit - 1)
        
        messages = []
        for message_id in reversed(message_ids):  # Reverse to get chronological order
            message_data = redis_client.hgetall(f"message:{message_id}")
            if message_data:
                messages.append(message_data)
        
        return messages
        
    except Exception as e:
        logger.error(f"Error getting session messages: {e}")
        return []


# System Status and Health

def get_system_status() -> Dict[str, Any]:
    """
    Get current system status.
    
    Returns:
        System status dictionary
    """
    try:
        redis_client = get_redis_client()
        
        # Basic Redis connectivity test
        redis_connected = True
        try:
            redis_client.ping()
        except:
            redis_connected = False
        
        # Count active sessions
        active_sessions_count = redis_client.scard("active_sessions")
        
        # Count total events in history
        event_count = redis_client.llen("event_history")
        
        # Count total subscriptions
        subscription_count = redis_client.scard("all_subscriptions")
        
        status = {
            'redis_connected': redis_connected,
            'active_sessions': active_sessions_count,
            'total_events': event_count,
            'total_subscriptions': subscription_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_health': 'healthy' if redis_connected else 'degraded'
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            'redis_connected': False,
            'system_health': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def cleanup_old_data() -> Dict[str, Any]:
    """
    Clean up old data from Redis.
    
    Returns:
        Cleanup results
    """
    try:
        redis_client = get_redis_client()
        
        # Clean up old events (older than 24 hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        cutoff_str = cutoff_time.isoformat()
        
        cleaned_events = 0
        cleaned_messages = 0
        
        # Clean up old events
        event_ids = redis_client.lrange("event_history", 0, -1)
        for event_id in event_ids:
            event_data = redis_client.hgetall(f"event:{event_id}")
            if event_data and event_data.get('timestamp', '') < cutoff_str:
                redis_client.delete(f"event:{event_id}")
                redis_client.lrem("event_history", 0, event_id)
                cleaned_events += 1
        
        # Clean up old messages (keep last 100 per session)
        session_ids = redis_client.smembers("active_sessions")
        for session_id in session_ids:
            message_ids = redis_client.lrange(f"session_messages:{session_id}", 100, -1)
            for message_id in message_ids:
                redis_client.delete(f"message:{message_id}")
                cleaned_messages += 1
            if message_ids:
                redis_client.ltrim(f"session_messages:{session_id}", 0, 99)
        
        result = {
            'cleaned_events': cleaned_events,
            'cleaned_messages': cleaned_messages,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Cleanup completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return {'error': str(e), 'timestamp': datetime.now(timezone.utc).isoformat()}