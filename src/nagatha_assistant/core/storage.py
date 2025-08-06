"""
Storage backend implementations for the memory system.

This module provides different storage backends for the memory system,
including database storage, Redis storage, and in-memory caching.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select, delete, and_, or_
from sqlalchemy.exc import IntegrityError
import redis.asyncio as redis
from redis.exceptions import RedisError

from nagatha_assistant.db import SessionLocal
from nagatha_assistant.db_models import MemorySection, MemoryEntry
from nagatha_assistant.utils.logger import setup_logger_with_env_control, get_logger

logger = get_logger()


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from storage."""
        pass
    
    @abstractmethod
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in storage."""
        pass
    
    @abstractmethod
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from storage."""
        pass
    
    @abstractmethod
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a section."""
        pass
    
    @abstractmethod
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries containing the query."""
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        pass


class RedisStorageBackend(StorageBackend):
    """Redis-backed storage implementation for fast, temporary storage."""
    
    def __init__(self, redis_url: str = None):
        """
        Initialize Redis storage backend.
        
        Args:
            redis_url: Redis connection URL. Defaults to environment variable REDIS_URL.
        """
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.redis_client: Optional[redis.Redis] = None
        self._running = False
        self.default_ttl = 3600  # 1 hour default TTL
        
    async def start(self) -> None:
        """Start the Redis storage backend."""
        if self._running:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            self._running = True
            logger.info("Redis storage backend connected")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the Redis storage backend."""
        if self.redis_client:
            await self.redis_client.close()
        self._running = False
        logger.info("Redis storage backend stopped")
    
    def _make_key(self, section: str, key: str, session_id: Optional[int] = None) -> str:
        """Create Redis key for storage."""
        if session_id:
            return f"memory:{section}:{session_id}:{key}"
        return f"memory:{section}:{key}"
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for Redis storage."""
        if isinstance(value, (dict, list, str, int, float, bool)):
            return json.dumps(value)
        else:
            return json.dumps({"__type": type(value).__name__, "value": str(value)})
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize a value from Redis storage."""
        try:
            data = json.loads(value)
            if isinstance(data, dict) and "__type" in data:
                # Handle custom object types
                return data["value"]
            return data
        except (json.JSONDecodeError, KeyError):
            return value
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from Redis storage."""
        if not self._running or not self.redis_client:
            return None
        
        try:
            redis_key = self._make_key(section, key, session_id)
            value = await self.redis_client.get(redis_key)
            
            if value is None:
                return None
            
            return self._deserialize_value(value)
            
        except RedisError as e:
            logger.error(f"Error getting value from Redis: {e}")
            return None
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in Redis storage."""
        if not self._running or not self.redis_client:
            return
        
        try:
            redis_key = self._make_key(section, key, session_id)
            serialized_value = self._serialize_value(value)
            
            if expires_at:
                ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
                if ttl > 0:
                    await self.redis_client.setex(redis_key, ttl, serialized_value)
                else:
                    # Already expired
                    return
            else:
                await self.redis_client.setex(redis_key, self.default_ttl, serialized_value)
            
            logger.debug(f"Stored in Redis: {section}/{key} (session: {session_id})")
            
        except RedisError as e:
            logger.error(f"Error setting value in Redis: {e}")
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from Redis storage."""
        if not self._running or not self.redis_client:
            return False
        
        try:
            redis_key = self._make_key(section, key, session_id)
            result = await self.redis_client.delete(redis_key)
            return result > 0
            
        except RedisError as e:
            logger.error(f"Error deleting value from Redis: {e}")
            return False
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a Redis section."""
        if not self._running or not self.redis_client:
            return []
        
        try:
            if session_id:
                search_pattern = f"memory:{section}:{session_id}:*"
            else:
                search_pattern = f"memory:{section}:*"
            
            keys = await self.redis_client.keys(search_pattern)
            
            # Extract the actual keys from Redis keys
            result_keys = []
            for key in keys:
                # Remove the prefix to get the actual key
                parts = key.split(":")
                if len(parts) >= 4:
                    if session_id:
                        # Format: memory:section:session_id:key
                        result_keys.append(parts[3])
                    else:
                        # Format: memory:section:key
                        result_keys.append(parts[2])
            
            # Apply pattern filter if specified
            if pattern:
                import fnmatch
                result_keys = [k for k in result_keys if fnmatch.fnmatch(k, pattern)]
            
            return result_keys
            
        except RedisError as e:
            logger.error(f"Error listing keys from Redis: {e}")
            return []
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries in Redis storage."""
        if not self._running or not self.redis_client:
            return []
        
        try:
            # Get all keys in the section
            keys = await self.list_keys(section, session_id)
            results = []
            
            for key in keys:
                value = await self.get(section, key, session_id)
                if value is not None:
                    # Simple text search in key and value
                    search_text = f"{key} {str(value)}".lower()
                    if query.lower() in search_text:
                        results.append({
                            "key": key,
                            "value": value,
                            "section": section,
                            "session_id": session_id
                        })
            
            return results
            
        except RedisError as e:
            logger.error(f"Error searching Redis: {e}")
            return []
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries in Redis."""
        # Redis handles TTL automatically, so no manual cleanup needed
        return 0


class DatabaseStorageBackend(StorageBackend):
    """Database-backed storage implementation using SQLAlchemy."""
    
    def __init__(self):
        self._sections_cache: Dict[str, int] = {}
    
    async def _ensure_section(self, section_name: str, persistence_level: str = "permanent") -> int:
        """Ensure a memory section exists and return its ID."""
        if section_name in self._sections_cache:
            return self._sections_cache[section_name]
        
        async with SessionLocal() as session:
            # Try to find existing section
            stmt = select(MemorySection).where(MemorySection.name == section_name)
            result = await session.execute(stmt)
            section = result.scalar_one_or_none()
            
            if section is None:
                # Create new section
                section = MemorySection(
                    name=section_name,
                    persistence_level=persistence_level
                )
                session.add(section)
                try:
                    await session.commit()
                    logger.debug(f"Created memory section: {section_name}")
                except IntegrityError:
                    # Handle race condition - section was created by another process
                    await session.rollback()
                    stmt = select(MemorySection).where(MemorySection.name == section_name)
                    result = await session.execute(stmt)
                    section = result.scalar_one()
            
            self._sections_cache[section_name] = section.id
            return section.id
    
    async def _serialize_value(self, value: Any) -> tuple[str, str]:
        """Serialize a value and return (value_type, serialized_value)."""
        if isinstance(value, str):
            return "string", value
        elif isinstance(value, (int, float, bool, list, dict)):
            return "json", json.dumps(value)
        else:
            return "string", str(value)
    
    async def _deserialize_value(self, value_type: str, value: str) -> Any:
        """Deserialize a value based on its type."""
        if value_type == "json":
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        else:
            return value
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from database storage."""
        try:
            section_id = await self._ensure_section(section)
            
            async with SessionLocal() as session:
                # Build query
                conditions = [
                    MemoryEntry.section_id == section_id,
                    MemoryEntry.key == key
                ]
                
                if session_id is not None:
                    conditions.append(MemoryEntry.session_id == session_id)
                else:
                    conditions.append(MemoryEntry.session_id.is_(None))
                
                stmt = select(MemoryEntry).where(and_(*conditions))
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()
                
                if entry is None:
                    return None
                
                # Check if expired
                if entry.expires_at and entry.expires_at < datetime.now(timezone.utc):
                    await session.delete(entry)
                    await session.commit()
                    return None
                
                return await self._deserialize_value(entry.value_type, entry.value)
                
        except Exception as e:
            logger.error(f"Error getting value from database: {e}")
            return None
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in database storage."""
        try:
            section_id = await self._ensure_section(section)
            value_type, serialized_value = await self._serialize_value(value)
            
            async with SessionLocal() as session:
                # Check if entry exists
                conditions = [
                    MemoryEntry.section_id == section_id,
                    MemoryEntry.key == key
                ]
                
                if session_id is not None:
                    conditions.append(MemoryEntry.session_id == session_id)
                else:
                    conditions.append(MemoryEntry.session_id.is_(None))
                
                stmt = select(MemoryEntry).where(and_(*conditions))
                result = await session.execute(stmt)
                existing_entry = result.scalar_one_or_none()
                
                if existing_entry:
                    # Update existing entry
                    existing_entry.value_type = value_type
                    existing_entry.value = serialized_value
                    existing_entry.expires_at = expires_at
                    existing_entry.updated_at = datetime.now(timezone.utc)
                else:
                    # Create new entry
                    entry = MemoryEntry(
                        section_id=section_id,
                        key=key,
                        value_type=value_type,
                        value=serialized_value,
                        session_id=session_id,
                        expires_at=expires_at
                    )
                    session.add(entry)
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error setting value in database: {e}")
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from database storage."""
        try:
            section_id = await self._ensure_section(section)
            
            async with SessionLocal() as session:
                conditions = [
                    MemoryEntry.section_id == section_id,
                    MemoryEntry.key == key
                ]
                
                if session_id is not None:
                    conditions.append(MemoryEntry.session_id == session_id)
                else:
                    conditions.append(MemoryEntry.session_id.is_(None))
                
                stmt = delete(MemoryEntry).where(and_(*conditions))
                result = await session.execute(stmt)
                await session.commit()
                
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error deleting value from database: {e}")
            return False
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a database section."""
        try:
            section_id = await self._ensure_section(section)
            
            async with SessionLocal() as session:
                conditions = [MemoryEntry.section_id == section_id]
                
                if session_id is not None:
                    conditions.append(MemoryEntry.session_id == session_id)
                else:
                    conditions.append(MemoryEntry.session_id.is_(None))
                
                stmt = select(MemoryEntry.key).where(and_(*conditions))
                result = await session.execute(stmt)
                keys = [row[0] for row in result.fetchall()]
                
                # Apply pattern filter if specified
                if pattern:
                    import fnmatch
                    keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
                
                return keys
                
        except Exception as e:
            logger.error(f"Error listing keys from database: {e}")
            return []
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries in database storage."""
        try:
            section_id = await self._ensure_section(section)
            
            async with SessionLocal() as session:
                conditions = [MemoryEntry.section_id == section_id]
                
                if session_id is not None:
                    conditions.append(MemoryEntry.session_id == session_id)
                else:
                    conditions.append(MemoryEntry.session_id.is_(None))
                
                # Add search conditions
                search_conditions = or_(
                    MemoryEntry.key.contains(query),
                    MemoryEntry.value.contains(query)
                )
                conditions.append(search_conditions)
                
                stmt = select(MemoryEntry).where(and_(*conditions))
                result = await session.execute(stmt)
                entries = result.scalars().all()
                
                results = []
                for entry in entries:
                    # Check if expired
                    if entry.expires_at and entry.expires_at < datetime.now(timezone.utc):
                        await session.delete(entry)
                        continue
                    
                    value = await self._deserialize_value(entry.value_type, entry.value)
                    results.append({
                        "key": entry.key,
                        "value": value,
                        "section": section,
                        "session_id": entry.session_id
                    })
                
                await session.commit()
                return results
                
        except Exception as e:
            logger.error(f"Error searching database: {e}")
            return []
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries in database storage."""
        try:
            async with SessionLocal() as session:
                stmt = delete(MemoryEntry).where(
                    MemoryEntry.expires_at < datetime.now(timezone.utc)
                )
                result = await session.execute(stmt)
                await session.commit()
                
                cleaned_count = result.rowcount
                if cleaned_count > 0:
                    logger.debug(f"Cleaned up {cleaned_count} expired database entries")
                
                return cleaned_count
                
        except Exception as e:
            logger.error(f"Error cleaning up expired database entries: {e}")
            return 0


class InMemoryStorageBackend(StorageBackend):
    """In-memory storage implementation for testing and caching."""
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._expiry_times: Dict[str, Dict[str, datetime]] = {}
    
    def _get_section_storage(self, section: str) -> Dict[str, Dict[str, Any]]:
        """Get or create storage for a section."""
        if section not in self._storage:
            self._storage[section] = {}
        return self._storage[section]
    
    def _make_key(self, key: str, session_id: Optional[int] = None) -> str:
        """Create storage key."""
        if session_id is not None:
            return f"{session_id}:{key}"
        return key
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from in-memory storage."""
        try:
            section_storage = self._get_section_storage(section)
            storage_key = self._make_key(key, session_id)
            
            if storage_key not in section_storage:
                return None
            
            # Check if expired
            if section in self._expiry_times and storage_key in self._expiry_times[section]:
                if self._expiry_times[section][storage_key] < datetime.now(timezone.utc):
                    del section_storage[storage_key]
                    del self._expiry_times[section][storage_key]
                    return None
            
            return section_storage[storage_key]["value"]
            
        except Exception as e:
            logger.error(f"Error getting value from in-memory storage: {e}")
            return None
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in in-memory storage."""
        try:
            section_storage = self._get_section_storage(section)
            storage_key = self._make_key(key, session_id)
            
            section_storage[storage_key] = {
                "value": value,
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc)
            }
            
            # Set expiry time
            if expires_at:
                if section not in self._expiry_times:
                    self._expiry_times[section] = {}
                self._expiry_times[section][storage_key] = expires_at
            
        except Exception as e:
            logger.error(f"Error setting value in in-memory storage: {e}")
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from in-memory storage."""
        try:
            section_storage = self._get_section_storage(section)
            storage_key = self._make_key(key, session_id)
            
            if storage_key in section_storage:
                del section_storage[storage_key]
                
                # Clean up expiry time
                if section in self._expiry_times and storage_key in self._expiry_times[section]:
                    del self._expiry_times[section][storage_key]
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting value from in-memory storage: {e}")
            return False
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in in-memory storage."""
        try:
            section_storage = self._get_section_storage(section)
            keys = []
            
            for storage_key in section_storage.keys():
                # Extract the actual key from storage key
                if session_id is not None:
                    # Format: session_id:key
                    parts = storage_key.split(":", 1)
                    if len(parts) == 2 and int(parts[0]) == session_id:
                        keys.append(parts[1])
                else:
                    # Format: key
                    keys.append(storage_key)
            
            # Apply pattern filter if specified
            if pattern:
                import fnmatch
                keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
            
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys from in-memory storage: {e}")
            return []
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries in in-memory storage."""
        try:
            section_storage = self._get_section_storage(section)
            results = []
            
            for storage_key, entry in section_storage.items():
                # Check if expired
                if section in self._expiry_times and storage_key in self._expiry_times[section]:
                    if self._expiry_times[section][storage_key] < datetime.now(timezone.utc):
                        del section_storage[storage_key]
                        del self._expiry_times[section][storage_key]
                        continue
                
                # Extract key and session_id
                if session_id is not None:
                    parts = storage_key.split(":", 1)
                    if len(parts) == 2 and int(parts[0]) == session_id:
                        key = parts[1]
                    else:
                        continue
                else:
                    key = storage_key
                
                # Simple text search
                search_text = f"{key} {str(entry['value'])}".lower()
                if query.lower() in search_text:
                    results.append({
                        "key": key,
                        "value": entry["value"],
                        "section": section,
                        "session_id": entry["session_id"]
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching in-memory storage: {e}")
            return []
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries in in-memory storage."""
        try:
            cleaned_count = 0
            current_time = datetime.now(timezone.utc)
            
            for section in list(self._storage.keys()):
                section_storage = self._storage[section]
                
                for storage_key in list(section_storage.keys()):
                    if (section in self._expiry_times and 
                        storage_key in self._expiry_times[section] and
                        self._expiry_times[section][storage_key] < current_time):
                        
                        del section_storage[storage_key]
                        del self._expiry_times[section][storage_key]
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} expired in-memory entries")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired in-memory entries: {e}")
            return 0


class HybridStorageBackend(StorageBackend):
    """
    Hybrid storage backend that combines Redis (fast) and Database (persistent) storage.
    
    This backend provides:
    - Fast access to recent data via Redis
    - Persistent storage via Database
    - Automatic fallback between storage types
    - Smart caching strategies
    """
    
    def __init__(self, redis_url: str = None):
        """
        Initialize hybrid storage backend.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_backend = RedisStorageBackend(redis_url)
        self.db_backend = DatabaseStorageBackend()
        self._running = False
        
        # Configuration
        self.use_redis_for_temporary = True
        self.use_redis_for_session = True
        self.use_redis_for_user_preferences = False  # Keep in DB for persistence
        self.use_redis_for_facts = False  # Keep in DB for persistence
        self.use_redis_for_command_history = False  # Keep in DB for persistence
        
    async def start(self) -> None:
        """Start the hybrid storage backend."""
        if self._running:
            return
        
        try:
            await self.redis_backend.start()
            self._running = True
            logger.info("Hybrid storage backend started")
        except Exception as e:
            logger.warning(f"Redis backend failed to start, using database only: {e}")
            self._running = False
    
    async def stop(self) -> None:
        """Stop the hybrid storage backend."""
        if self._running:
            await self.redis_backend.stop()
        self._running = False
    
    def _should_use_redis(self, section: str) -> bool:
        """Determine if Redis should be used for a given section."""
        if not self._running:
            return False
        
        if section == "temporary":
            return self.use_redis_for_temporary
        elif section == "session_state":
            return self.use_redis_for_session
        elif section == "user_preferences":
            return self.use_redis_for_user_preferences
        elif section == "facts":
            return self.use_redis_for_facts
        elif section == "command_history":
            return self.use_redis_for_command_history
        else:
            # Default to Redis for unknown sections
            return True
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value using hybrid storage strategy."""
        try:
            if self._should_use_redis(section):
                # Try Redis first
                value = await self.redis_backend.get(section, key, session_id)
                if value is not None:
                    return value
                
                # Fallback to database
                value = await self.db_backend.get(section, key, session_id)
                if value is not None:
                    # Cache in Redis for future access
                    await self.redis_backend.set(section, key, value, session_id)
                return value
            else:
                # Use database directly
                return await self.db_backend.get(section, key, session_id)
                
        except Exception as e:
            logger.error(f"Error in hybrid storage get: {e}")
            # Fallback to database
            return await self.db_backend.get(section, key, session_id)
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value using hybrid storage strategy."""
        try:
            if self._should_use_redis(section):
                # Set in both Redis and database
                await self.redis_backend.set(section, key, value, session_id, expires_at)
                await self.db_backend.set(section, key, value, session_id, expires_at)
            else:
                # Use database only
                await self.db_backend.set(section, key, value, session_id, expires_at)
                
        except Exception as e:
            logger.error(f"Error in hybrid storage set: {e}")
            # Fallback to database
            await self.db_backend.set(section, key, value, session_id, expires_at)
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value using hybrid storage strategy."""
        try:
            if self._should_use_redis(section):
                # Delete from both Redis and database
                redis_result = await self.redis_backend.delete(section, key, session_id)
                db_result = await self.db_backend.delete(section, key, session_id)
                return redis_result or db_result
            else:
                # Use database only
                return await self.db_backend.delete(section, key, session_id)
                
        except Exception as e:
            logger.error(f"Error in hybrid storage delete: {e}")
            # Fallback to database
            return await self.db_backend.delete(section, key, session_id)
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys using hybrid storage strategy."""
        try:
            if self._should_use_redis(section):
                # Try Redis first, fallback to database
                keys = await self.redis_backend.list_keys(section, session_id, pattern)
                if not keys:
                    keys = await self.db_backend.list_keys(section, session_id, pattern)
                return keys
            else:
                # Use database only
                return await self.db_backend.list_keys(section, session_id, pattern)
                
        except Exception as e:
            logger.error(f"Error in hybrid storage list_keys: {e}")
            # Fallback to database
            return await self.db_backend.list_keys(section, session_id, pattern)
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search using hybrid storage strategy."""
        try:
            if self._should_use_redis(section):
                # Try Redis first, fallback to database
                results = await self.redis_backend.search(section, query, session_id)
                if not results:
                    results = await self.db_backend.search(section, query, session_id)
                return results
            else:
                # Use database only
                return await self.db_backend.search(section, query, session_id)
                
        except Exception as e:
            logger.error(f"Error in hybrid storage search: {e}")
            # Fallback to database
            return await self.db_backend.search(section, query, session_id)
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries using hybrid storage strategy."""
        try:
            redis_cleaned = await self.redis_backend.cleanup_expired()
            db_cleaned = await self.db_backend.cleanup_expired()
            return redis_cleaned + db_cleaned
        except Exception as e:
            logger.error(f"Error in hybrid storage cleanup: {e}")
            return await self.db_backend.cleanup_expired()