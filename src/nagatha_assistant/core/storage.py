"""
Storage backend implementations for the memory system.

This module provides different storage backends for the memory system,
including database storage and in-memory caching.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select, delete, and_, or_
from sqlalchemy.exc import IntegrityError

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
            # Try to serialize as JSON for other types
            try:
                return "json", json.dumps(value)
            except (TypeError, ValueError):
                # Fall back to string representation
                return "string", str(value)
    
    def _deserialize_value(self, value_type: str, value: str) -> Any:
        """Deserialize a value based on its type."""
        if value_type == "string":
            return value
        elif value_type == "json":
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to deserialize JSON value: {value}")
                return value
        else:
            return value
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from the database."""
        section_id = await self._ensure_section(section)
        
        async with SessionLocal() as db_session:
            stmt = select(MemoryEntry).where(
                and_(
                    MemoryEntry.section_id == section_id,
                    MemoryEntry.key == key,
                    or_(
                        MemoryEntry.session_id == session_id,
                        MemoryEntry.session_id.is_(None)
                    ),
                    or_(
                        MemoryEntry.expires_at.is_(None),
                        MemoryEntry.expires_at > datetime.now(timezone.utc)
                    )
                )
            ).order_by(MemoryEntry.session_id.desc().nulls_last())  # Prefer session-specific over global
            
            result = await db_session.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if entry is None:
                return None
            
            return self._deserialize_value(entry.value_type, entry.value)
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in the database."""
        section_id = await self._ensure_section(section)
        value_type, serialized_value = await self._serialize_value(value)
        
        async with SessionLocal() as db_session:
            # Check if entry already exists
            stmt = select(MemoryEntry).where(
                and_(
                    MemoryEntry.section_id == section_id,
                    MemoryEntry.key == key,
                    or_(
                        MemoryEntry.session_id == session_id,
                        MemoryEntry.session_id.is_(None)
                    )
                )
            )
            result = await db_session.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if entry is None:
                # Create new entry
                entry = MemoryEntry(
                    section_id=section_id,
                    key=key,
                    value_type=value_type,
                    value=serialized_value,
                    session_id=session_id,
                    expires_at=expires_at
                )
                db_session.add(entry)
            else:
                # Update existing entry
                entry.value_type = value_type
                entry.value = serialized_value
                entry.updated_at = datetime.now(timezone.utc)
                entry.expires_at = expires_at
            
            await db_session.commit()
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from the database."""
        section_id = await self._ensure_section(section)
        
        async with SessionLocal() as db_session:
            stmt = delete(MemoryEntry).where(
                and_(
                    MemoryEntry.section_id == section_id,
                    MemoryEntry.key == key,
                    or_(
                        MemoryEntry.session_id == session_id,
                        MemoryEntry.session_id.is_(None)
                    )
                )
            )
            result = await db_session.execute(stmt)
            await db_session.commit()
            
            return result.rowcount > 0
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a section."""
        section_id = await self._ensure_section(section)
        
        async with SessionLocal() as db_session:
            stmt = select(MemoryEntry.key).where(
                and_(
                    MemoryEntry.section_id == section_id,
                    or_(
                        MemoryEntry.session_id == session_id,
                        MemoryEntry.session_id.is_(None)
                    ),
                    or_(
                        MemoryEntry.expires_at.is_(None),
                        MemoryEntry.expires_at > datetime.now(timezone.utc)
                    )
                )
            )
            
            if pattern:
                # Simple pattern matching with LIKE
                stmt = stmt.where(MemoryEntry.key.like(pattern.replace('*', '%')))
            
            result = await db_session.execute(stmt)
            return [row[0] for row in result.fetchall()]
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries containing the query."""
        section_id = await self._ensure_section(section)
        
        async with SessionLocal() as db_session:
            # Search in both keys and values
            stmt = select(MemoryEntry).where(
                and_(
                    MemoryEntry.section_id == section_id,
                    or_(
                        MemoryEntry.session_id == session_id,
                        MemoryEntry.session_id.is_(None)
                    ),
                    or_(
                        MemoryEntry.expires_at.is_(None),
                        MemoryEntry.expires_at > datetime.now(timezone.utc)
                    ),
                    or_(
                        MemoryEntry.key.contains(query),
                        MemoryEntry.value.contains(query)
                    )
                )
            )
            
            result = await db_session.execute(stmt)
            entries = result.scalars().all()
            
            search_results = []
            for entry in entries:
                search_results.append({
                    "key": entry.key,
                    "value": self._deserialize_value(entry.value_type, entry.value),
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                    "session_id": entry.session_id
                })
            
            return search_results
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        async with SessionLocal() as db_session:
            stmt = delete(MemoryEntry).where(
                and_(
                    MemoryEntry.expires_at.is_not(None),
                    MemoryEntry.expires_at <= datetime.now(timezone.utc)
                )
            )
            result = await db_session.execute(stmt)
            await db_session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Cleaned up {result.rowcount} expired memory entries")
            
            return result.rowcount


class InMemoryStorageBackend(StorageBackend):
    """In-memory storage backend for testing and temporary data."""
    
    def __init__(self):
        self._storage: Dict[str, Dict[str, Dict[str, Any]]] = {}  # section -> key -> data
    
    def _get_section_storage(self, section: str) -> Dict[str, Dict[str, Any]]:
        """Get or create storage for a section."""
        if section not in self._storage:
            self._storage[section] = {}
        return self._storage[section]
    
    def _make_key(self, key: str, session_id: Optional[int] = None) -> str:
        """Create a storage key that includes session if provided."""
        if session_id is not None:
            return f"session:{session_id}:{key}"
        return f"global:{key}"
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None) -> Optional[Any]:
        """Get a value from memory."""
        section_storage = self._get_section_storage(section)
        storage_key = self._make_key(key, session_id)
        
        if storage_key in section_storage:
            entry = section_storage[storage_key]
            # Check expiration
            if entry.get("expires_at") and entry["expires_at"] <= datetime.now(timezone.utc):
                del section_storage[storage_key]
                return None
            return entry["value"]
        
        # If session-specific key not found, try global key
        if session_id is not None:
            global_key = self._make_key(key, None)
            if global_key in section_storage:
                entry = section_storage[global_key]
                if entry.get("expires_at") and entry["expires_at"] <= datetime.now(timezone.utc):
                    del section_storage[global_key]
                    return None
                return entry["value"]
        
        return None
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  expires_at: Optional[datetime] = None) -> None:
        """Set a value in memory."""
        section_storage = self._get_section_storage(section)
        storage_key = self._make_key(key, session_id)
        
        section_storage[storage_key] = {
            "value": value,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "session_id": session_id
        }
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """Delete a value from memory."""
        section_storage = self._get_section_storage(section)
        storage_key = self._make_key(key, session_id)
        
        if storage_key in section_storage:
            del section_storage[storage_key]
            return True
        return False
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """List keys in a section."""
        section_storage = self._get_section_storage(section)
        keys = []
        
        for storage_key, entry in section_storage.items():
            # Check expiration
            if entry.get("expires_at") and entry["expires_at"] <= datetime.now(timezone.utc):
                continue
                
            # Extract original key
            if storage_key.startswith("session:"):
                _, sid, original_key = storage_key.split(":", 2)
                if session_id is None or int(sid) == session_id:
                    keys.append(original_key)
            elif storage_key.startswith("global:"):
                original_key = storage_key[7:]  # Remove "global:" prefix
                keys.append(original_key)
        
        # Apply pattern filter if provided
        if pattern:
            import fnmatch
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
        
        return sorted(set(keys))  # Remove duplicates and sort
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for entries containing the query."""
        section_storage = self._get_section_storage(section)
        results = []
        
        for storage_key, entry in section_storage.items():
            # Check expiration
            if entry.get("expires_at") and entry["expires_at"] <= datetime.now(timezone.utc):
                continue
            
            # Extract original key
            if storage_key.startswith("session:"):
                _, sid, original_key = storage_key.split(":", 2)
                if session_id is not None and int(sid) != session_id:
                    continue
            elif storage_key.startswith("global:"):
                original_key = storage_key[7:]  # Remove "global:" prefix
            else:
                continue
            
            # Search in key and value
            value = entry["value"]
            value_str = str(value) if not isinstance(value, str) else value
            
            if query.lower() in original_key.lower() or query.lower() in value_str.lower():
                results.append({
                    "key": original_key,
                    "value": value,
                    "created_at": entry["created_at"],
                    "updated_at": entry["created_at"],  # Same as created for in-memory
                    "session_id": entry.get("session_id")
                })
        
        return results
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        now = datetime.now(timezone.utc)
        removed_count = 0
        
        for section_storage in self._storage.values():
            to_remove = []
            for storage_key, entry in section_storage.items():
                if entry.get("expires_at") and entry["expires_at"] <= now:
                    to_remove.append(storage_key)
            
            for key in to_remove:
                del section_storage[key]
                removed_count += 1
        
        return removed_count