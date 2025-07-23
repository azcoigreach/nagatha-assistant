"""
Redis-based storage backend for Nagatha Assistant.

This provides a fast, async-compatible storage solution that works perfectly
with Celery and eliminates the greenlet issues we've been experiencing.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as redis
from django.conf import settings

logger = logging.getLogger(__name__)


class RedisStorageBackend:
    """
    Redis-based storage backend for Nagatha Assistant.
    
    This provides fast, async-compatible storage that works perfectly
    with Celery and eliminates greenlet issues.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis storage backend.
        
        Args:
            redis_url: Redis connection URL. Defaults to Django's Redis cache URL.
        """
        if redis_url is None:
            # Use Django's Redis cache configuration
            cache_config = getattr(settings, 'CACHES', {}).get('default', {})
            location = cache_config.get('LOCATION', 'redis://redis:6379/1')
            # Use database 2 for Nagatha storage (separate from Django cache)
            redis_url = location.replace('/1', '/2')
        
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._prefix = "nagatha"
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    def _make_key(self, section: str, key: str, session_id: Optional[int] = None) -> str:
        """Create a Redis key with proper namespacing."""
        if session_id is not None:
            return f"{self._prefix}:{section}:session:{session_id}:{key}"
        return f"{self._prefix}:{section}:global:{key}"
    
    def _make_pattern(self, section: str, session_id: Optional[int] = None) -> str:
        """Create a Redis pattern for scanning keys."""
        if session_id is not None:
            return f"{self._prefix}:{section}:session:{session_id}:*"
        return f"{self._prefix}:{section}:*"
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from Redis storage."""
        try:
            redis_client = await self._get_redis()
            redis_key = self._make_key(section, key, session_id)
            
            # Try session-specific key first
            value = await redis_client.get(redis_key)
            
            # If not found and session_id provided, try global key
            if value is None and session_id is not None:
                global_key = self._make_key(section, key, None)
                value = await redis_client.get(global_key)
            
            if value is None:
                return None
            
            # Deserialize JSON value
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # Fallback to string value
                return value
                
        except Exception as e:
            logger.error(f"Error getting value from Redis: {e}")
            return None
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in Redis storage."""
        try:
            redis_client = await self._get_redis()
            redis_key = self._make_key(section, key, session_id)
            
            # Serialize value to JSON
            if isinstance(value, (dict, list, int, float, bool)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            # Calculate TTL if expires_at is provided
            ttl = None
            if expires_at:
                ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
                if ttl <= 0:
                    # Already expired, don't store
                    return
            
            # Store in Redis
            if ttl:
                await redis_client.setex(redis_key, ttl, serialized_value)
            else:
                await redis_client.set(redis_key, serialized_value)
                
        except Exception as e:
            logger.error(f"Error setting value in Redis: {e}")
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from Redis storage."""
        try:
            redis_client = await self._get_redis()
            redis_key = self._make_key(section, key, session_id)
            
            result = await redis_client.delete(redis_key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting value from Redis: {e}")
            return False
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a section."""
        try:
            redis_client = await self._get_redis()
            scan_pattern = self._make_pattern(section, session_id)
            
            if pattern:
                # Add pattern to scan
                scan_pattern = scan_pattern.replace('*', f'*{pattern}*')
            
            keys = []
            async for key in redis_client.scan_iter(match=scan_pattern):
                # Extract the actual key name from the full Redis key
                key_parts = key.split(':')
                if len(key_parts) >= 4:
                    keys.append(key_parts[-1])  # Last part is the actual key
            
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys from Redis: {e}")
            return []
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries containing the query."""
        try:
            redis_client = await self._get_redis()
            scan_pattern = self._make_pattern(section, session_id)
            
            results = []
            async for key in redis_client.scan_iter(match=scan_pattern):
                value = await redis_client.get(key)
                if value and query.lower() in value.lower():
                    # Extract key name and deserialize value
                    key_parts = key.split(':')
                    actual_key = key_parts[-1] if len(key_parts) >= 4 else key
                    
                    try:
                        deserialized_value = json.loads(value)
                    except json.JSONDecodeError:
                        deserialized_value = value
                    
                    results.append({
                        "key": actual_key,
                        "value": deserialized_value,
                        "created_at": None,  # Redis doesn't store creation time by default
                        "updated_at": None,
                        "session_id": session_id
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Redis: {e}")
            return []
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries (Redis handles this automatically)."""
        # Redis automatically handles TTL expiration
        return 0
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


class NagathaRedisStorage:
    """
    High-level storage interface for Nagatha using Redis.
    
    This provides a simple, fast interface for storing:
    - Session data
    - Memory entries
    - User preferences
    - Temporary cache data
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.backend = RedisStorageBackend(redis_url)
    
    # Session management
    async def create_session(self) -> str:
        """Create a new session and return session ID."""
        import uuid
        session_id = str(uuid.uuid4())
        await self.backend.set("sessions", session_id, {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat()
        })
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        return await self.backend.get("sessions", session_id)
    
    async def update_session_activity(self, session_id: str) -> None:
        """Update session last activity."""
        session_data = await self.get_session(session_id)
        if session_data:
            session_data["last_activity"] = datetime.now(timezone.utc).isoformat()
            await self.backend.set("sessions", session_id, session_data)
    
    # Message storage
    async def store_message(self, session_id: str, message_id: str, 
                          role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Store a message in the session."""
        message_data = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        await self.backend.set("messages", f"{session_id}:{message_id}", message_data)
    
    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session."""
        keys = await self.backend.list_keys("messages", pattern=f"{session_id}:*")
        messages = []
        
        for key in keys:
            message_data = await self.backend.get("messages", key)
            if message_data:
                message_data["id"] = key.split(":", 1)[1]  # Extract message ID
                messages.append(message_data)
        
        # Sort by timestamp
        messages.sort(key=lambda x: x.get("timestamp", ""))
        return messages
    
    # Memory system
    async def store_memory(self, section: str, key: str, value: Any, 
                          session_id: Optional[str] = None, ttl_seconds: Optional[int] = None) -> None:
        """Store a memory entry."""
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        await self.backend.set(section, key, value, session_id, expires_at)
    
    async def get_memory(self, section: str, key: str, session_id: Optional[str] = None) -> Optional[Any]:
        """Get a memory entry."""
        return await self.backend.get(section, key, session_id)
    
    async def search_memory(self, section: str, query: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search memory entries."""
        return await self.backend.search(section, query, session_id)
    
    # System status
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status information."""
        try:
            redis_client = await self.backend._get_redis()
            info = await redis_client.info()
            
            return {
                "redis_connected": True,
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime": info.get("uptime_in_seconds"),
                "storage_backend": "redis",
                "status": "operational"
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "redis_connected": False,
                "error": str(e),
                "storage_backend": "redis",
                "status": "degraded"
            }
    
    async def close(self):
        """Close the storage connection."""
        await self.backend.close() 