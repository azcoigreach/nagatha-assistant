"""
Redis-based Short-Term Memory System for Nagatha Assistant.

This module provides fast, temporary memory storage for conversation context,
recent interactions, and immediate session state that needs to be quickly
accessible during conversations.
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import redis.asyncio as redis
from redis.exceptions import RedisError

from nagatha_assistant.utils.logger import get_logger
from nagatha_assistant.core.event import StandardEventTypes, create_memory_event, EventPriority
from nagatha_assistant.core.event_bus import get_event_bus

logger = get_logger()


@dataclass
class ConversationContext:
    """Represents a conversation context entry."""
    session_id: int
    message_id: int
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            message_id=data["message_id"],
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class SessionState:
    """Represents current session state."""
    session_id: int
    current_topic: Optional[str] = None
    current_task: Optional[str] = None
    user_intent: Optional[str] = None
    conversation_mode: str = "normal"  # normal, focused, quick
    last_activity: datetime = None
    context_window_size: int = 10  # Number of recent messages to keep in context
    
    def __post_init__(self):
        if self.last_activity is None:
            self.last_activity = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "current_topic": self.current_topic,
            "current_task": self.current_task,
            "user_intent": self.user_intent,
            "conversation_mode": self.conversation_mode,
            "last_activity": self.last_activity.isoformat(),
            "context_window_size": self.context_window_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            current_topic=data.get("current_topic"),
            current_task=data.get("current_task"),
            user_intent=data.get("user_intent"),
            conversation_mode=data.get("conversation_mode", "normal"),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            context_window_size=data.get("context_window_size", 10)
        )


class ShortTermMemory:
    """
    Redis-based short-term memory system for fast conversation context access.
    
    This system provides:
    - Fast conversation context retrieval
    - Session state management
    - Temporary data caching
    - Conversation window management
    - Real-time context updates
    """
    
    def __init__(self, redis_url: str = None):
        """
        Initialize the short-term memory system.
        
        Args:
            redis_url: Redis connection URL. Defaults to environment variable REDIS_URL.
        """
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.redis_client: Optional[redis.Redis] = None
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.default_ttl = 3600  # 1 hour default TTL
        self.max_context_window = 20  # Maximum messages in context window
        self.cleanup_interval = 300  # 5 minutes
        
    async def start(self) -> None:
        """Start the short-term memory system."""
        if self._running:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Short-term memory system connected to Redis")
            
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the short-term memory system."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Short-term memory system stopped")
    
    async def add_conversation_context(self, session_id: int, message_id: int, 
                                     role: str, content: str, 
                                     metadata: Dict[str, Any] = None) -> None:
        """
        Add a message to the conversation context.
        
        Args:
            session_id: Session identifier
            message_id: Message identifier
            role: Message role (user/assistant)
            content: Message content
            metadata: Additional metadata
        """
        if not self._running or not self.redis_client:
            return
        
        try:
            context = ConversationContext(
                session_id=session_id,
                message_id=message_id,
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Store in Redis with TTL
            key = f"conversation:{session_id}:{message_id}"
            await self.redis_client.setex(
                key,
                self.default_ttl,
                json.dumps(context.to_dict())
            )
            
            # Add to conversation list (for context window)
            list_key = f"conversation_list:{session_id}"
            await self.redis_client.lpush(list_key, json.dumps(context.to_dict()))
            
            # Trim list to maintain context window size
            await self.redis_client.ltrim(list_key, 0, self.max_context_window - 1)
            
            # Set TTL on the list
            await self.redis_client.expire(list_key, self.default_ttl)
            
            # Update session state
            await self._update_session_activity(session_id)
            
            # Publish event
            await self._publish_event(
                StandardEventTypes.MEMORY_ENTRY_CREATED,
                "conversation_context",
                f"{session_id}:{message_id}",
                {"session_id": session_id, "role": role}
            )
            
            logger.debug(f"Added conversation context: {session_id}:{message_id}")
            
        except RedisError as e:
            logger.error(f"Error adding conversation context: {e}")
    
    async def get_conversation_context(self, session_id: int, 
                                     limit: int = 10) -> List[ConversationContext]:
        """
        Get recent conversation context for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of conversation context entries
        """
        if not self._running or not self.redis_client:
            return []
        
        try:
            list_key = f"conversation_list:{session_id}"
            messages_data = await self.redis_client.lrange(list_key, 0, limit - 1)
            
            contexts = []
            for msg_data in messages_data:
                try:
                    data = json.loads(msg_data)
                    context = ConversationContext.from_dict(data)
                    contexts.append(context)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Error parsing conversation context: {e}")
                    continue
            
            return contexts
            
        except RedisError as e:
            logger.error(f"Error getting conversation context: {e}")
            return []
    
    async def get_session_state(self, session_id: int) -> Optional[SessionState]:
        """
        Get current session state.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session state or None if not found
        """
        if not self._running or not self.redis_client:
            return None
        
        try:
            key = f"session_state:{session_id}"
            data = await self.redis_client.get(key)
            
            if data:
                state_data = json.loads(data)
                return SessionState.from_dict(state_data)
            
            return None
            
        except RedisError as e:
            logger.error(f"Error getting session state: {e}")
            return None
    
    async def update_session_state(self, session_id: int, 
                                 updates: Dict[str, Any]) -> None:
        """
        Update session state.
        
        Args:
            session_id: Session identifier
            updates: Dictionary of state updates
        """
        if not self._running or not self.redis_client:
            return
        
        try:
            # Get current state or create new one
            current_state = await self.get_session_state(session_id)
            if not current_state:
                current_state = SessionState(session_id=session_id)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(current_state, key):
                    setattr(current_state, key, value)
            
            # Update last activity
            current_state.last_activity = datetime.now(timezone.utc)
            
            # Store in Redis
            key = f"session_state:{session_id}"
            await self.redis_client.setex(
                key,
                self.default_ttl,
                json.dumps(current_state.to_dict())
            )
            
            logger.debug(f"Updated session state for {session_id}")
            
        except RedisError as e:
            logger.error(f"Error updating session state: {e}")
    
    async def set_temporary_data(self, key: str, value: Any, 
                               ttl_seconds: int = None) -> None:
        """
        Set temporary data with TTL.
        
        Args:
            key: Data key
            value: Data value
            ttl_seconds: Time to live in seconds
        """
        if not self._running or not self.redis_client:
            return
        
        try:
            ttl = ttl_seconds or self.default_ttl
            await self.redis_client.setex(
                f"temp:{key}",
                ttl,
                json.dumps(value)
            )
            
            logger.debug(f"Set temporary data: {key}")
            
        except RedisError as e:
            logger.error(f"Error setting temporary data: {e}")
    
    async def get_temporary_data(self, key: str) -> Any:
        """
        Get temporary data.
        
        Args:
            key: Data key
            
        Returns:
            Stored value or None if not found
        """
        if not self._running or not self.redis_client:
            return None
        
        try:
            data = await self.redis_client.get(f"temp:{key}")
            if data:
                return json.loads(data)
            return None
            
        except RedisError as e:
            logger.error(f"Error getting temporary data: {e}")
            return None
    
    async def search_conversation_context(self, session_id: int, 
                                        query: str) -> List[ConversationContext]:
        """
        Search conversation context for specific content.
        
        Args:
            session_id: Session identifier
            query: Search query
            
        Returns:
            List of matching conversation contexts
        """
        if not self._running or not self.redis_client:
            return []
        
        try:
            # Get all conversation context for the session
            contexts = await self.get_conversation_context(session_id, limit=50)
            
            # Simple text search (could be enhanced with vector search)
            query_lower = query.lower()
            matches = []
            
            for context in contexts:
                if (query_lower in context.content.lower() or 
                    query_lower in str(context.metadata).lower()):
                    matches.append(context)
            
            return matches
            
        except RedisError as e:
            logger.error(f"Error searching conversation context: {e}")
            return []
    
    async def clear_session_context(self, session_id: int) -> None:
        """
        Clear all conversation context for a session.
        
        Args:
            session_id: Session identifier
        """
        if not self._running or not self.redis_client:
            return
        
        try:
            # Clear conversation list
            list_key = f"conversation_list:{session_id}"
            await self.redis_client.delete(list_key)
            
            # Clear session state
            state_key = f"session_state:{session_id}"
            await self.redis_client.delete(state_key)
            
            # Clear individual conversation entries
            pattern = f"conversation:{session_id}:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
            
            logger.info(f"Cleared conversation context for session {session_id}")
            
        except RedisError as e:
            logger.error(f"Error clearing session context: {e}")
    
    async def get_active_sessions(self) -> List[int]:
        """
        Get list of active session IDs.
        
        Returns:
            List of active session IDs
        """
        if not self._running or not self.redis_client:
            return []
        
        try:
            pattern = "session_state:*"
            keys = await self.redis_client.keys(pattern)
            
            session_ids = []
            for key in keys:
                # Extract session ID from key format "session_state:{session_id}"
                session_id = key.split(":")[1]
                try:
                    session_ids.append(int(session_id))
                except ValueError:
                    continue
            
            return session_ids
            
        except RedisError as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def _update_session_activity(self, session_id: int) -> None:
        """Update session activity timestamp."""
        try:
            current_state = await self.get_session_state(session_id)
            if current_state:
                await self.update_session_state(session_id, {})
            else:
                # Create new session state
                await self.update_session_state(session_id, {
                    "session_id": session_id,
                    "last_activity": datetime.now(timezone.utc)
                })
        except Exception as e:
            logger.warning(f"Error updating session activity: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup task."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                if not self._running:
                    break
                
                # Redis handles TTL automatically, but we can do additional cleanup here
                logger.debug("Short-term memory cleanup cycle completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in short-term memory cleanup: {e}")
                await asyncio.sleep(60)
    
    async def _publish_event(self, event_type: str, section: str, key: str, 
                           data: Dict[str, Any]) -> None:
        """Publish memory event."""
        try:
            event_bus = get_event_bus()
            if event_bus and event_bus._running:
                event = create_memory_event(event_type, section, key, data)
                await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish short-term memory event: {e}")


# Global short-term memory instance
_short_term_memory: Optional[ShortTermMemory] = None


def get_short_term_memory() -> ShortTermMemory:
    """Get the global short-term memory instance."""
    global _short_term_memory
    
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    
    return _short_term_memory


async def ensure_short_term_memory_started() -> ShortTermMemory:
    """Ensure the global short-term memory is started and return it."""
    memory = get_short_term_memory()
    await memory.start()
    return memory


async def shutdown_short_term_memory() -> None:
    """Shutdown the global short-term memory."""
    global _short_term_memory
    
    if _short_term_memory is not None:
        await _short_term_memory.stop()
        _short_term_memory = None 