"""
Persistent Memory System for Nagatha Assistant.

This module provides a comprehensive memory system that allows Nagatha to store
and retrieve information across sessions, including:
- Key-value store for simple data
- Structured data storage for complex objects
- Automatic serialization/deserialization
- Memory sections with different persistence levels
- Memory search capabilities
- Event bus integration for change notifications
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from nagatha_assistant.core.storage import StorageBackend, DatabaseStorageBackend, InMemoryStorageBackend
from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import StandardEventTypes, create_memory_event, EventPriority
from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


class PersistenceLevel(Enum):
    """Enumeration of memory persistence levels."""
    TEMPORARY = "temporary"      # Expires automatically, suitable for short-term data
    SESSION = "session"          # Persists for the duration of a session
    PERMANENT = "permanent"      # Persists indefinitely


class MemorySection:
    """Represents a logical section of memory with specific persistence characteristics."""
    
    def __init__(self, name: str, persistence_level: PersistenceLevel = PersistenceLevel.PERMANENT,
                 description: Optional[str] = None):
        self.name = name
        self.persistence_level = persistence_level
        self.description = description


class MemoryManager:
    """
    Central memory management system for Nagatha.
    
    Provides key-value storage with different persistence levels, automatic
    serialization, search capabilities, and event integration.
    """
    
    # Predefined memory sections
    SECTIONS = {
        "user_preferences": MemorySection("user_preferences", PersistenceLevel.PERMANENT,
                                         "User preferences and settings"),
        "session_state": MemorySection("session_state", PersistenceLevel.SESSION,
                                     "Current session state and context"),
        "command_history": MemorySection("command_history", PersistenceLevel.PERMANENT,
                                       "History of user commands and interactions"),
        "facts": MemorySection("facts", PersistenceLevel.PERMANENT,
                              "Long-term facts and knowledge"),
        "temporary": MemorySection("temporary", PersistenceLevel.TEMPORARY,
                                 "Short-term temporary data"),
    }
    
    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        """
        Initialize the memory manager.
        
        Args:
            storage_backend: Optional storage backend. Defaults to DatabaseStorageBackend.
        """
        self._storage = storage_backend or DatabaseStorageBackend()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the memory manager and cleanup tasks."""
        if self._running:
            return
        
        self._running = True
        # Start cleanup task for expired entries
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Memory manager started")
    
    async def stop(self) -> None:
        """Stop the memory manager and cleanup tasks."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Memory manager stopped")
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  ttl_seconds: Optional[int] = None) -> None:
        """
        Store a value in memory.
        
        Args:
            section: Memory section name
            key: Key to store the value under
            value: Value to store (will be automatically serialized)
            session_id: Optional session ID for session-scoped storage
            ttl_seconds: Time to live in seconds (for temporary data)
        """
        expires_at = None
        if ttl_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        await self._storage.set(section, key, value, session_id, expires_at)
        
        # Publish event
        try:
            event_bus = get_event_bus()
            if event_bus and event_bus._running:
                event = create_memory_event(
                    StandardEventTypes.MEMORY_ENTRY_CREATED,
                    section,
                    key,
                    {
                        "value_type": type(value).__name__,
                        "session_id": session_id,
                        "has_ttl": ttl_seconds is not None
                    }
                )
                await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish memory event: {e}")
        
        logger.debug(f"Stored memory: {section}/{key} (session: {session_id})")
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None,
                  default: Any = None) -> Any:
        """
        Retrieve a value from memory.
        
        Args:
            section: Memory section name
            key: Key to retrieve
            session_id: Optional session ID for session-scoped retrieval
            default: Default value to return if key not found
        
        Returns:
            Stored value or default if not found
        """
        value = await self._storage.get(section, key, session_id)
        if value is None:
            return default
        return value
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """
        Delete a value from memory.
        
        Args:
            section: Memory section name
            key: Key to delete
            session_id: Optional session ID for session-scoped deletion
        
        Returns:
            True if the key was found and deleted, False otherwise
        """
        deleted = await self._storage.delete(section, key, session_id)
        
        if deleted:
            # Publish event
            try:
                event_bus = get_event_bus()
                if event_bus and event_bus._running:
                    event = create_memory_event(
                        StandardEventTypes.MEMORY_ENTRY_DELETED,
                        section,
                        key,
                        {"session_id": session_id}
                    )
                    await event_bus.publish(event)
            except Exception as e:
                logger.warning(f"Failed to publish memory event: {e}")
            
            logger.debug(f"Deleted memory: {section}/{key} (session: {session_id})")
        
        return deleted
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """
        List keys in a memory section.
        
        Args:
            section: Memory section name
            session_id: Optional session ID to filter by
            pattern: Optional pattern to filter keys (supports wildcards)
        
        Returns:
            List of matching keys
        """
        return await self._storage.list_keys(section, session_id, pattern)
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for entries in a memory section.
        
        Args:
            section: Memory section name
            query: Search query (searches both keys and values)
            session_id: Optional session ID to filter by
        
        Returns:
            List of matching entries with metadata
        """
        results = await self._storage.search(section, query, session_id)
        
        # Publish search event
        try:
            event_bus = get_event_bus()
            if event_bus and event_bus._running:
                event = create_memory_event(
                    StandardEventTypes.MEMORY_SEARCH_PERFORMED,
                    section,
                    None,
                    {
                        "query": query,
                        "session_id": session_id,
                        "result_count": len(results)
                    }
                )
                await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish memory event: {e}")
        
        return results
    
    async def set_user_preference(self, key: str, value: Any) -> None:
        """Set a user preference (permanent storage)."""
        await self.set("user_preferences", key, value)
    
    async def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return await self.get("user_preferences", key, default=default)
    
    async def set_session_state(self, session_id: int, key: str, value: Any) -> None:
        """Set session-specific state."""
        await self.set("session_state", key, value, session_id=session_id)
    
    async def get_session_state(self, session_id: int, key: str, default: Any = None) -> Any:
        """Get session-specific state."""
        return await self.get("session_state", key, session_id=session_id, default=default)
    
    async def add_command_to_history(self, command: str, response: Optional[str] = None,
                                   session_id: Optional[int] = None) -> None:
        """Add a command to the command history."""
        timestamp = datetime.now(timezone.utc).isoformat()
        history_entry = {
            "command": command,
            "response": response,
            "timestamp": timestamp,
            "session_id": session_id
        }
        
        # Use timestamp as key for ordering
        key = f"{timestamp}_{session_id or 'global'}"
        await self.set("command_history", key, history_entry)
    
    async def get_command_history(self, session_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get command history, optionally filtered by session."""
        # Search for all commands (empty query matches all)
        results = await self.search("command_history", "", session_id)
        
        # Sort by timestamp (most recent first) and limit
        results.sort(key=lambda x: x.get("value", {}).get("timestamp", ""), reverse=True)
        return results[:limit]
    
    async def store_fact(self, key: str, fact: str, source: Optional[str] = None) -> None:
        """Store a long-term fact."""
        fact_data = {
            "fact": fact,
            "source": source,
            "stored_at": datetime.now(timezone.utc).isoformat()
        }
        await self.set("facts", key, fact_data)
    
    async def get_fact(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored fact."""
        return await self.get("facts", key)
    
    async def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search for facts containing the query."""
        return await self.search("facts", query)
    
    async def set_temporary(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Store temporary data with TTL."""
        await self.set("temporary", key, value, ttl_seconds=ttl_seconds)
    
    async def get_temporary(self, key: str, default: Any = None) -> Any:
        """Get temporary data."""
        return await self.get("temporary", key, default=default)
    
    async def clear_section(self, section: str, session_id: Optional[int] = None) -> int:
        """
        Clear all entries in a section.
        
        Args:
            section: Section to clear
            session_id: Optional session ID to filter by
        
        Returns:
            Number of entries deleted
        """
        keys = await self.list_keys(section, session_id)
        deleted_count = 0
        
        for key in keys:
            if await self.delete(section, key, session_id):
                deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} entries from section {section}")
        return deleted_count
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about memory storage."""
        stats = {}
        
        # Check predefined sections
        for section_name in self.SECTIONS.keys():
            keys = await self.list_keys(section_name)
            stats[section_name] = len(keys)
        
        # Also check for any other sections that might have data
        # This is a best-effort attempt for in-memory backend
        if hasattr(self._storage, '_storage'):
            # InMemoryStorageBackend
            for section_name in self._storage._storage.keys():
                if section_name not in stats:
                    keys = await self.list_keys(section_name)
                    stats[section_name] = len(keys)
        
        # Add cleanup info
        stats["cleanup_running"] = self._running
        
        return stats
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired entries."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                if not self._running:
                    break
                
                cleaned_count = await self._storage.cleanup_expired()
                if cleaned_count > 0:
                    logger.debug(f"Cleaned up {cleaned_count} expired memory entries")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in memory cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance (singleton pattern)."""
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    
    return _memory_manager


async def ensure_memory_manager_started() -> MemoryManager:
    """Ensure the global memory manager is started and return it."""
    manager = get_memory_manager()
    await manager.start()
    return manager


async def shutdown_memory_manager() -> None:
    """Shutdown the global memory manager."""
    global _memory_manager
    
    if _memory_manager is not None:
        await _memory_manager.stop()
        _memory_manager = None