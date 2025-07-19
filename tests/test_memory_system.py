"""
Tests for the memory system functionality.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from nagatha_assistant.core.memory import MemoryManager, PersistenceLevel, MemorySection
from nagatha_assistant.core.storage import InMemoryStorageBackend, DatabaseStorageBackend
from nagatha_assistant.core.event import StandardEventTypes


class TestMemorySystem:
    """Test suite for the memory system."""
    
    @pytest_asyncio.fixture
    async def memory_manager(self):
        """Create a memory manager with in-memory storage for testing."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_basic_get_set(self, memory_manager):
        """Test basic get/set operations."""
        # Test setting and getting a simple value
        await memory_manager.set("test_section", "key1", "value1")
        result = await memory_manager.get("test_section", "key1")
        assert result == "value1"
        
        # Test getting non-existent key
        result = await memory_manager.get("test_section", "nonexistent")
        assert result is None
        
        # Test getting with default
        result = await memory_manager.get("test_section", "nonexistent", default="default_value")
        assert result == "default_value"
    
    @pytest.mark.asyncio
    async def test_complex_data_types(self, memory_manager):
        """Test storing and retrieving complex data types."""
        # Test dictionary
        data_dict = {"name": "test", "value": 42, "list": [1, 2, 3]}
        await memory_manager.set("test_section", "dict_key", data_dict)
        result = await memory_manager.get("test_section", "dict_key")
        assert result == data_dict
        
        # Test list
        data_list = [1, "two", {"three": 3}]
        await memory_manager.set("test_section", "list_key", data_list)
        result = await memory_manager.get("test_section", "list_key")
        assert result == data_list
        
        # Test numbers and booleans
        await memory_manager.set("test_section", "int_key", 42)
        await memory_manager.set("test_section", "float_key", 3.14)
        await memory_manager.set("test_section", "bool_key", True)
        
        assert await memory_manager.get("test_section", "int_key") == 42
        assert await memory_manager.get("test_section", "float_key") == 3.14
        assert await memory_manager.get("test_section", "bool_key") is True
    
    @pytest.mark.asyncio
    async def test_session_scoped_storage(self, memory_manager):
        """Test session-scoped storage."""
        # Set global value
        await memory_manager.set("test_section", "shared_key", "global_value")
        
        # Set session-specific values
        await memory_manager.set("test_section", "shared_key", "session1_value", session_id=1)
        await memory_manager.set("test_section", "shared_key", "session2_value", session_id=2)
        
        # Test retrieval
        assert await memory_manager.get("test_section", "shared_key") == "global_value"
        assert await memory_manager.get("test_section", "shared_key", session_id=1) == "session1_value"
        assert await memory_manager.get("test_section", "shared_key", session_id=2) == "session2_value"
        
        # Session-specific should take precedence over global
        assert await memory_manager.get("test_section", "shared_key", session_id=1) == "session1_value"
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, memory_manager):
        """Test TTL (time-to-live) functionality."""
        # Set a value with very short TTL
        await memory_manager.set("test_section", "ttl_key", "ttl_value", ttl_seconds=1)
        
        # Should be available immediately
        result = await memory_manager.get("test_section", "ttl_key")
        assert result == "ttl_value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired now
        result = await memory_manager.get("test_section", "ttl_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_operations(self, memory_manager):
        """Test deletion operations."""
        # Set some values
        await memory_manager.set("test_section", "key1", "value1")
        await memory_manager.set("test_section", "key2", "value2", session_id=1)
        
        # Test successful deletion
        deleted = await memory_manager.delete("test_section", "key1")
        assert deleted is True
        assert await memory_manager.get("test_section", "key1") is None
        
        # Test session-scoped deletion
        deleted = await memory_manager.delete("test_section", "key2", session_id=1)
        assert deleted is True
        assert await memory_manager.get("test_section", "key2", session_id=1) is None
        
        # Test deleting non-existent key
        deleted = await memory_manager.delete("test_section", "nonexistent")
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_list_keys(self, memory_manager):
        """Test key listing functionality."""
        # Set some values
        await memory_manager.set("test_section", "key1", "value1")
        await memory_manager.set("test_section", "key2", "value2")
        await memory_manager.set("test_section", "another_key", "value3", session_id=1)
        
        # List all keys
        keys = await memory_manager.list_keys("test_section")
        assert "key1" in keys
        assert "key2" in keys
        assert "another_key" in keys
        
        # List session-specific keys
        session_keys = await memory_manager.list_keys("test_section", session_id=1)
        assert "another_key" in session_keys
        
        # Test pattern matching
        pattern_keys = await memory_manager.list_keys("test_section", pattern="key*")
        assert "key1" in pattern_keys
        assert "key2" in pattern_keys
        # "another_key" might or might not be included depending on pattern implementation
    
    @pytest.mark.asyncio
    async def test_search_functionality(self, memory_manager):
        """Test search functionality."""
        # Set up test data
        await memory_manager.set("test_section", "user_john", {"name": "John", "age": 30})
        await memory_manager.set("test_section", "user_jane", {"name": "Jane", "age": 25})
        await memory_manager.set("test_section", "config_timeout", 30)
        
        # Search for "john"
        results = await memory_manager.search("test_section", "john")
        assert len(results) >= 1
        found_john = any("john" in result["key"].lower() for result in results)
        assert found_john
        
        # Search for "30" (should match both John's age and timeout config)
        results = await memory_manager.search("test_section", "30")
        assert len(results) >= 2
    
    @pytest.mark.asyncio
    async def test_user_preferences(self, memory_manager):
        """Test user preference storage."""
        # Set preferences
        await memory_manager.set_user_preference("theme", "dark")
        await memory_manager.set_user_preference("language", "en")
        
        # Get preferences
        assert await memory_manager.get_user_preference("theme") == "dark"
        assert await memory_manager.get_user_preference("language") == "en"
        assert await memory_manager.get_user_preference("nonexistent", "default") == "default"
    
    @pytest.mark.asyncio
    async def test_session_state(self, memory_manager):
        """Test session state management."""
        session_id = 123
        
        # Set session state
        await memory_manager.set_session_state(session_id, "current_task", "testing")
        await memory_manager.set_session_state(session_id, "progress", 0.5)
        
        # Get session state
        assert await memory_manager.get_session_state(session_id, "current_task") == "testing"
        assert await memory_manager.get_session_state(session_id, "progress") == 0.5
        assert await memory_manager.get_session_state(session_id, "nonexistent", "default") == "default"
    
    @pytest.mark.asyncio
    async def test_command_history(self, memory_manager):
        """Test command history functionality."""
        session_id = 456
        
        # Add commands to history
        await memory_manager.add_command_to_history("list files", "file1.txt, file2.txt", session_id)
        await memory_manager.add_command_to_history("help", "Available commands: ...", session_id)
        
        # Get history
        history = await memory_manager.get_command_history(session_id, limit=10)
        assert len(history) >= 2
        
        # Check structure of history entries
        latest_entry = history[0]  # Should be most recent
        assert "command" in latest_entry["value"]
        assert "response" in latest_entry["value"]
        assert "timestamp" in latest_entry["value"]
    
    @pytest.mark.asyncio
    async def test_facts_storage(self, memory_manager):
        """Test fact storage and retrieval."""
        # Store facts
        await memory_manager.store_fact("python_version", "Python 3.12", source="system")
        await memory_manager.store_fact("project_name", "Nagatha Assistant", source="config")
        
        # Get individual fact
        fact = await memory_manager.get_fact("python_version")
        assert fact is not None
        assert fact["fact"] == "Python 3.12"
        assert fact["source"] == "system"
        assert "stored_at" in fact
        
        # Search facts
        results = await memory_manager.search_facts("python")
        assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_temporary_storage(self, memory_manager):
        """Test temporary storage with TTL."""
        # Store temporary data
        await memory_manager.set_temporary("temp_key", "temp_value", ttl_seconds=1)
        
        # Should be available immediately
        result = await memory_manager.get_temporary("temp_key")
        assert result == "temp_value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        result = await memory_manager.get_temporary("temp_key", default="expired")
        assert result == "expired"
    
    @pytest.mark.asyncio
    async def test_clear_section(self, memory_manager):
        """Test clearing entire sections."""
        # Set up test data
        await memory_manager.set("test_section", "key1", "value1")
        await memory_manager.set("test_section", "key2", "value2")
        await memory_manager.set("test_section", "key3", "value3", session_id=1)
        
        # Clear global entries only
        cleared_count = await memory_manager.clear_section("test_section")
        assert cleared_count >= 2  # At least the two global entries
        
        # Global entries should be gone
        assert await memory_manager.get("test_section", "key1") is None
        assert await memory_manager.get("test_section", "key2") is None
        
        # Session entry might still exist depending on implementation
    
    @pytest.mark.asyncio
    async def test_storage_stats(self, memory_manager):
        """Test storage statistics."""
        # Add some data
        await memory_manager.set_user_preference("test_pref", "value")
        await memory_manager.store_fact("test_fact", "fact_value")
        
        # Get stats
        stats = await memory_manager.get_storage_stats()
        assert isinstance(stats, dict)
        assert "user_preferences" in stats
        assert "facts" in stats
        assert "cleanup_running" in stats
        assert stats["cleanup_running"] is True
    
    @pytest.mark.asyncio
    async def test_memory_sections(self):
        """Test memory section definitions."""
        # Test predefined sections
        assert "user_preferences" in MemoryManager.SECTIONS
        assert "session_state" in MemoryManager.SECTIONS
        assert "command_history" in MemoryManager.SECTIONS
        assert "facts" in MemoryManager.SECTIONS
        assert "temporary" in MemoryManager.SECTIONS
        
        # Test section properties
        user_prefs_section = MemoryManager.SECTIONS["user_preferences"]
        assert user_prefs_section.persistence_level == PersistenceLevel.PERMANENT
        
        temp_section = MemoryManager.SECTIONS["temporary"]
        assert temp_section.persistence_level == PersistenceLevel.TEMPORARY


class TestStorageBackends:
    """Test suite for storage backend implementations."""
    
    @pytest.mark.asyncio
    async def test_in_memory_backend(self):
        """Test in-memory storage backend."""
        backend = InMemoryStorageBackend()
        
        # Basic operations
        await backend.set("test", "key1", "value1")
        result = await backend.get("test", "key1")
        assert result == "value1"
        
        # Session-scoped storage
        await backend.set("test", "key1", "session_value", session_id=1)
        assert await backend.get("test", "key1", session_id=1) == "session_value"
        assert await backend.get("test", "key1") == "value1"  # Global still exists
        
        # TTL functionality
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        await backend.set("test", "ttl_key", "ttl_value", expires_at=expires_at)
        assert await backend.get("test", "ttl_key") == "ttl_value"
        
        await asyncio.sleep(1.1)
        assert await backend.get("test", "ttl_key") is None
        
        # Cleanup
        cleaned = await backend.cleanup_expired()
        assert isinstance(cleaned, int)
    
    @pytest.mark.asyncio
    async def test_database_backend(self):
        """Test database storage backend."""
        from nagatha_assistant.db import ensure_schema
        
        # Ensure schema is up to date
        await ensure_schema()
        
        backend = DatabaseStorageBackend()
        
        # Basic operations (integration test)
        await backend.set("test", "db_key", "db_value")
        result = await backend.get("test", "db_key")
        assert result == "db_value"
        
        # Cleanup
        deleted = await backend.delete("test", "db_key")
        assert deleted is True
        
        result = await backend.get("test", "db_key")
        assert result is None


class TestMemoryIntegration:
    """Integration tests for the memory system."""
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle(self):
        """Test memory manager start/stop lifecycle."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        
        # Test start
        await manager.start()
        assert manager._running is True
        assert manager._cleanup_task is not None
        
        # Test stop
        await manager.stop()
        assert manager._running is False
        assert manager._cleanup_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_global_manager_singleton(self):
        """Test global memory manager singleton pattern."""
        from nagatha_assistant.core.memory import get_memory_manager, ensure_memory_manager_started
        
        manager1 = get_memory_manager()
        manager2 = get_memory_manager()
        assert manager1 is manager2  # Same instance
        
        # Test ensure started
        started_manager = await ensure_memory_manager_started()
        assert started_manager is manager1
        assert started_manager._running is True
        
        # Cleanup
        await started_manager.stop()