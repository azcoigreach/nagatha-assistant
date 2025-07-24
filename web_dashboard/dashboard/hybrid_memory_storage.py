"""
Hybrid Memory Storage Backend for Nagatha Assistant.

This module provides a hybrid storage solution that combines:
- Redis for fast, async-compatible short-term storage
- SQLite for reliable long-term persistence
- Automatic synchronization between the two
- Celery-compatible operations
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as redis
from django.conf import settings
from django.db import connection
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)


class HybridMemoryStorageBackend:
    """
    Hybrid storage backend that combines Redis and SQLite.
    
    This provides the best of both worlds:
    - Fast Redis access for real-time operations
    - Reliable SQLite persistence for long-term storage
    - Automatic sync between the two systems
    - Celery-compatible operations
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize hybrid storage backend.
        
        Args:
            redis_url: Redis connection URL. Defaults to Django's Redis cache URL.
        """
        if redis_url is None:
            # Use Django's Redis cache configuration
            cache_config = getattr(settings, 'CACHES', {}).get('default', {})
            location = cache_config.get('LOCATION', 'redis://redis:6379/1')
            # Use database 3 for hybrid memory storage
            redis_url = location.replace('/1', '/3')
        
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._prefix = "nagatha_hybrid"
        self._sync_interval = 300  # Sync every 5 minutes
        self._last_sync = datetime.now(timezone.utc)
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    def _make_redis_key(self, section: str, key: str, session_id: Optional[int] = None) -> str:
        """Create a Redis key with proper namespacing."""
        if session_id is not None:
            return f"{self._prefix}:{section}:session:{session_id}:{key}"
        return f"{self._prefix}:{section}:global:{key}"
    
    def _make_redis_pattern(self, section: str, session_id: Optional[int] = None) -> str:
        """Create a Redis pattern for scanning keys."""
        if session_id is not None:
            return f"{self._prefix}:{section}:session:{session_id}:*"
        return f"{self._prefix}:{section}:*"
    
    def _should_use_redis(self, section: str, persistence_level: str = "permanent") -> bool:
        """Determine if data should be stored in Redis based on section and persistence."""
        # Use Redis for temporary and session data
        if persistence_level in ["temporary", "session"]:
            return True
        
        # Use Redis for frequently accessed permanent data
        redis_sections = ["session_state", "temporary", "user_preferences"]
        if section in redis_sections:
            return True
        
        # Use SQLite for long-term permanent data
        sqlite_sections = ["facts", "command_history"]
        if section in sqlite_sections:
            return False
        
        # Default to Redis for unknown sections
        return True
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from hybrid storage."""
        try:
            # Try Redis first for fast access
            redis_client = await self._get_redis()
            redis_key = self._make_redis_key(section, key, session_id)
            
            # Try session-specific key first
            value = await redis_client.get(redis_key)
            
            # If not found and session_id provided, try global key
            if value is None and session_id is not None:
                global_key = self._make_redis_key(section, key, None)
                value = await redis_client.get(global_key)
            
            if value is not None:
                # Deserialize JSON value
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            
            # If not in Redis, try SQLite for permanent data
            if not self._should_use_redis(section):
                return await self._get_from_sqlite(section, key, session_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting value from hybrid storage: {e}")
            return None
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in hybrid storage."""
        try:
            # Determine storage strategy
            use_redis = self._should_use_redis(section)
            
            if use_redis:
                # Store in Redis
                await self._set_in_redis(section, key, value, session_id, expires_at)
            else:
                # Store in SQLite
                await self._set_in_sqlite(section, key, value, session_id, expires_at)
                
        except Exception as e:
            logger.error(f"Error setting value in hybrid storage: {e}")
    
    async def _set_in_redis(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                           expires_at: Optional[datetime] = None) -> None:
        """Set a value in Redis."""
        redis_client = await self._get_redis()
        redis_key = self._make_redis_key(section, key, session_id)
        
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
                return  # Already expired
        
        # Store in Redis
        if ttl:
            await redis_client.setex(redis_key, ttl, serialized_value)
        else:
            await redis_client.set(redis_key, serialized_value)
    
    async def _set_in_sqlite(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                            expires_at: Optional[datetime] = None) -> None:
        """Set a value in SQLite using Django ORM."""
        try:
            from .models import MemorySection, MemoryEntry
            
            # Ensure section exists
            section_obj, created = MemorySection.objects.get_or_create(
                name=section,
                defaults={
                    'description': f'Memory section for {section}',
                    'persistence_level': 'permanent'
                }
            )
            
            # Serialize value
            if isinstance(value, (dict, list, int, float, bool)):
                value_type = 'json'
                serialized_value = json.dumps(value)
            else:
                value_type = 'string'
                serialized_value = str(value)
            
            # Create or update entry
            entry, created = MemoryEntry.objects.get_or_create(
                section=section_obj,
                key=key,
                session_id=session_id,
                defaults={
                    'value_type': value_type,
                    'value': serialized_value,
                    'expires_at': expires_at
                }
            )
            
            if not created:
                # Update existing entry
                entry.value_type = value_type
                entry.value = serialized_value
                entry.expires_at = expires_at
                entry.updated_at = django_timezone.now()
                entry.save()
                
        except Exception as e:
            logger.error(f"Error setting value in SQLite: {e}")
            raise
    
    async def _get_from_sqlite(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from SQLite using Django ORM."""
        try:
            from .models import MemorySection, MemoryEntry
            
            # Find the section
            try:
                section_obj = MemorySection.objects.get(name=section)
            except MemorySection.DoesNotExist:
                return None
            
            # Build query
            query = MemoryEntry.objects.filter(
                section=section_obj,
                key=key
            )
            
            # Add session filter
            if session_id is not None:
                query = query.filter(session_id=session_id)
            else:
                query = query.filter(session_id__isnull=True)
            
            # Add expiration filter
            query = query.filter(
                models.Q(expires_at__isnull=True) | 
                models.Q(expires_at__gt=django_timezone.now())
            )
            
            # Get the entry
            entry = query.first()
            if entry is None:
                return None
            
            # Deserialize value
            if entry.value_type == 'json':
                try:
                    return json.loads(entry.value)
                except json.JSONDecodeError:
                    return entry.value
            else:
                return entry.value
                
        except Exception as e:
            logger.error(f"Error getting value from SQLite: {e}")
            return None
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from hybrid storage."""
        try:
            deleted = False
            
            # Try Redis first
            redis_client = await self._get_redis()
            redis_key = self._make_redis_key(section, key, session_id)
            redis_result = await redis_client.delete(redis_key)
            if redis_result > 0:
                deleted = True
            
            # Also try SQLite for permanent data
            if not self._should_use_redis(section):
                sqlite_result = await self._delete_from_sqlite(section, key, session_id)
                deleted = deleted or sqlite_result
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting value from hybrid storage: {e}")
            return False
    
    async def _delete_from_sqlite(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from SQLite."""
        try:
            from .models import MemorySection, MemoryEntry
            
            # Find the section
            try:
                section_obj = MemorySection.objects.get(name=section)
            except MemorySection.DoesNotExist:
                return False
            
            # Build query
            query = MemoryEntry.objects.filter(
                section=section_obj,
                key=key
            )
            
            # Add session filter
            if session_id is not None:
                query = query.filter(session_id=session_id)
            else:
                query = query.filter(session_id__isnull=True)
            
            # Delete
            deleted_count = query.delete()[0]
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting value from SQLite: {e}")
            return False
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a section."""
        try:
            keys = []
            
            # Get keys from Redis
            if self._should_use_redis(section):
                redis_keys = await self._list_keys_from_redis(section, session_id, pattern)
                keys.extend(redis_keys)
            
            # Get keys from SQLite for permanent data
            if not self._should_use_redis(section):
                sqlite_keys = await self._list_keys_from_sqlite(section, session_id, pattern)
                keys.extend(sqlite_keys)
            
            # Remove duplicates and sort
            return sorted(set(keys))
            
        except Exception as e:
            logger.error(f"Error listing keys from hybrid storage: {e}")
            return []
    
    async def _list_keys_from_redis(self, section: str, session_id: Optional[int] = None,
                                   pattern: Optional[str] = None) -> List[str]:
        """List keys from Redis."""
        try:
            redis_client = await self._get_redis()
            scan_pattern = self._make_redis_pattern(section, session_id)
            
            if pattern:
                scan_pattern = scan_pattern.replace('*', f'*{pattern}*')
            
            keys = []
            async for key in redis_client.scan_iter(match=scan_pattern):
                # Extract the actual key name from the full Redis key
                key_parts = key.split(':')
                if len(key_parts) >= 4:
                    keys.append(key_parts[-1])
            
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys from Redis: {e}")
            return []
    
    async def _list_keys_from_sqlite(self, section: str, session_id: Optional[int] = None,
                                    pattern: Optional[str] = None) -> List[str]:
        """List keys from SQLite."""
        try:
            from .models import MemorySection, MemoryEntry
            from django.db import models
            
            # Find the section
            try:
                section_obj = MemorySection.objects.get(name=section)
            except MemorySection.DoesNotExist:
                return []
            
            # Build query
            query = MemoryEntry.objects.filter(section=section_obj)
            
            # Add session filter
            if session_id is not None:
                query = query.filter(session_id=session_id)
            else:
                query = query.filter(session_id__isnull=True)
            
            # Add expiration filter
            query = query.filter(
                models.Q(expires_at__isnull=True) | 
                models.Q(expires_at__gt=django_timezone.now())
            )
            
            # Add pattern filter
            if pattern:
                query = query.filter(key__icontains=pattern)
            
            # Get keys
            keys = list(query.values_list('key', flat=True))
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys from SQLite: {e}")
            return []
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries containing the query."""
        try:
            results = []
            
            # Search in Redis
            if self._should_use_redis(section):
                redis_results = await self._search_in_redis(section, query, session_id)
                results.extend(redis_results)
            
            # Search in SQLite for permanent data
            if not self._should_use_redis(section):
                sqlite_results = await self._search_in_sqlite(section, query, session_id)
                results.extend(sqlite_results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching hybrid storage: {e}")
            return []
    
    async def _search_in_redis(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search in Redis."""
        try:
            redis_client = await self._get_redis()
            scan_pattern = self._make_redis_pattern(section, session_id)
            
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
                        "created_at": None,
                        "updated_at": None,
                        "session_id": session_id
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Redis: {e}")
            return []
    
    async def _search_in_sqlite(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search in SQLite."""
        try:
            from .models import MemorySection, MemoryEntry
            from django.db import models
            
            # Find the section
            try:
                section_obj = MemorySection.objects.get(name=section)
            except MemorySection.DoesNotExist:
                return []
            
            # Build query
            query_filter = models.Q(key__icontains=query) | models.Q(value__icontains=query)
            db_query = MemoryEntry.objects.filter(
                section=section_obj
            ).filter(query_filter)
            
            # Add session filter
            if session_id is not None:
                db_query = db_query.filter(session_id=session_id)
            else:
                db_query = db_query.filter(session_id__isnull=True)
            
            # Add expiration filter
            db_query = db_query.filter(
                models.Q(expires_at__isnull=True) | 
                models.Q(expires_at__gt=django_timezone.now())
            )
            
            # Get results
            results = []
            for entry in db_query:
                # Deserialize value
                if entry.value_type == 'json':
                    try:
                        value = json.loads(entry.value)
                    except json.JSONDecodeError:
                        value = entry.value
                else:
                    value = entry.value
                
                results.append({
                    "key": entry.key,
                    "value": value,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                    "session_id": entry.session_id
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching SQLite: {e}")
            return []
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        try:
            cleaned_count = 0
            
            # Redis handles TTL automatically
            # Clean up SQLite expired entries
            cleaned_count += await self._cleanup_expired_sqlite()
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            return 0
    
    async def _cleanup_expired_sqlite(self) -> int:
        """Clean up expired entries from SQLite."""
        try:
            from .models import MemoryEntry
            from django.db import models
            
            # Delete expired entries
            deleted_count = MemoryEntry.objects.filter(
                models.Q(expires_at__isnull=False) & 
                models.Q(expires_at__lte=django_timezone.now())
            ).delete()[0]
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired memory entries from SQLite")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired entries from SQLite: {e}")
            return 0
    
    async def sync_redis_to_sqlite(self) -> Dict[str, int]:
        """Sync Redis data to SQLite for long-term persistence."""
        try:
            sync_results = {
                'facts_synced': 0,
                'preferences_synced': 0,
                'command_history_synced': 0,
                'errors': 0
            }
            
            redis_client = await self._get_redis()
            
            # Sync permanent sections from Redis to SQLite
            permanent_sections = ['facts', 'command_history', 'user_preferences']
            
            for section in permanent_sections:
                scan_pattern = self._make_redis_pattern(section)
                
                async for key in redis_client.scan_iter(match=scan_pattern):
                    try:
                        value = await redis_client.get(key)
                        if value:
                            # Extract key name
                            key_parts = key.split(':')
                            actual_key = key_parts[-1] if len(key_parts) >= 4 else key
                            
                            # Deserialize value
                            try:
                                deserialized_value = json.loads(value)
                            except json.JSONDecodeError:
                                deserialized_value = value
                            
                            # Store in SQLite
                            await self._set_in_sqlite(section, actual_key, deserialized_value)
                            
                            # Update sync count
                            if section == 'facts':
                                sync_results['facts_synced'] += 1
                            elif section == 'command_history':
                                sync_results['command_history_synced'] += 1
                            elif section == 'user_preferences':
                                sync_results['preferences_synced'] += 1
                                
                    except Exception as e:
                        logger.error(f"Error syncing key {key}: {e}")
                        sync_results['errors'] += 1
            
            self._last_sync = datetime.now(timezone.utc)
            logger.info(f"Synced Redis to SQLite: {sync_results}")
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error syncing Redis to SQLite: {e}")
            return {'errors': 1}
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None 