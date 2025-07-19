"""
Integration tests for the memory system with the broader Nagatha ecosystem.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

import nagatha_assistant.core.event_bus
from nagatha_assistant.core.memory import MemoryManager, get_memory_manager, ensure_memory_manager_started
from nagatha_assistant.core.storage import InMemoryStorageBackend
from nagatha_assistant.core.event_bus import EventBus, get_event_bus
from nagatha_assistant.core.event import StandardEventTypes, create_memory_event
from nagatha_assistant.db_models import ConversationSession, Message
from nagatha_assistant.db import SessionLocal


class TestMemoryIntegration:
    """Test integration of memory system with the broader codebase."""

    @pytest_asyncio.fixture
    async def memory_manager_with_events(self):
        """Create a memory manager with event bus integration."""
        # Make sure we're using the global event bus
        from nagatha_assistant.core.event_bus import _event_bus, _bus_lock
        
        # Clean up any existing event bus
        global_bus = None
        with _bus_lock:
            if _event_bus is not None:
                await _event_bus.stop()
        
        # Create and start new event bus
        event_bus = EventBus()
        await event_bus.start()
        
        # Set as global
        with _bus_lock:
            nagatha_assistant.core.event_bus._event_bus = event_bus
        
        # Create memory manager
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        # Store for cleanup
        events_received = []
        
        def event_handler(event):
            events_received.append(event)
        
        # Subscribe to memory events
        event_bus.subscribe("memory.*", event_handler)
        
        try:
            yield manager, event_bus, events_received
        finally:
            await manager.stop()
            await event_bus.stop()
            
            # Clean up global reference
            with _bus_lock:
                nagatha_assistant.core.event_bus._event_bus = None

    @pytest.mark.asyncio
    async def test_memory_events_integration(self, memory_manager_with_events):
        """Test that memory operations publish events correctly."""
        manager, event_bus, events_received = memory_manager_with_events
        
        # Clear any initial events
        events_received.clear()
        
        # Perform memory operations
        await manager.set("test_section", "test_key", "test_value")
        await manager.delete("test_section", "test_key")
        
        # Give events time to process
        import asyncio
        await asyncio.sleep(0.1)
        
        # Check that events were published
        assert len(events_received) >= 2
        
        # Check event types
        event_types = [event.event_type for event in events_received]
        assert StandardEventTypes.MEMORY_ENTRY_CREATED in event_types
        assert StandardEventTypes.MEMORY_ENTRY_DELETED in event_types

    @pytest.mark.asyncio
    async def test_session_integration(self):
        """Test memory system integration with conversation sessions."""
        from nagatha_assistant.db import ensure_schema
        
        # Ensure schema exists
        await ensure_schema()
        
        # Create a conversation session
        async with SessionLocal() as session:
            conv_session = ConversationSession()
            session.add(conv_session)
            await session.commit()
            session_id = conv_session.id
        
        # Use memory system with the session
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Set session-specific memory
            await manager.set_session_state(session_id, "current_topic", "testing memory")
            await manager.set_session_state(session_id, "step_count", 5)
            
            # Retrieve session state
            topic = await manager.get_session_state(session_id, "current_topic")
            steps = await manager.get_session_state(session_id, "step_count")
            
            assert topic == "testing memory"
            assert steps == 5
            
            # Test command history for this session
            await manager.add_command_to_history(
                "test command", 
                "test response", 
                session_id=session_id
            )
            
            history = await manager.get_command_history(session_id=session_id)
            assert len(history) >= 1
            assert history[0]["value"]["command"] == "test command"
            
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_global_memory_manager(self):
        """Test the global memory manager singleton."""
        # Get the global manager
        manager1 = get_memory_manager()
        manager2 = get_memory_manager()
        
        # Should be the same instance
        assert manager1 is manager2
        
        # Test ensure started
        started_manager = await ensure_memory_manager_started()
        assert started_manager is manager1
        assert started_manager._running is True
        
        # Test basic functionality
        await started_manager.set_user_preference("test_pref", "test_value")
        value = await started_manager.get_user_preference("test_pref")
        assert value == "test_value"
        
        # Cleanup
        await started_manager.stop()

    @pytest.mark.asyncio
    async def test_memory_persistence_levels(self):
        """Test different memory persistence levels."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Test permanent storage (user preferences)
            await manager.set_user_preference("theme", "dark")
            assert await manager.get_user_preference("theme") == "dark"
            
            # Test temporary storage with TTL
            await manager.set_temporary("temp_data", "will_expire", ttl_seconds=1)
            assert await manager.get_temporary("temp_data") == "will_expire"
            
            # Wait for expiration
            import asyncio
            await asyncio.sleep(1.1)
            assert await manager.get_temporary("temp_data") is None
            
            # Test facts storage
            await manager.store_fact("test_fact", "This is a test fact", source="integration_test")
            fact = await manager.get_fact("test_fact")
            assert fact is not None
            assert fact["fact"] == "This is a test fact"
            assert fact["source"] == "integration_test"
            
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_memory_search_across_sections(self):
        """Test searching across different memory sections."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Set up test data across different sections
            await manager.set_user_preference("search_test", "user preference data")
            await manager.store_fact("search_fact", "This contains search term", source="test")
            await manager.set("custom_section", "search_key", "custom search data")
            
            # Search in specific sections
            user_results = await manager.search("user_preferences", "search")
            fact_results = await manager.search("facts", "search")
            custom_results = await manager.search("custom_section", "search")
            
            # Verify results
            assert len(user_results) >= 1
            assert len(fact_results) >= 1
            assert len(custom_results) >= 1
            
            # Check that results contain expected data
            user_found = any("user preference" in str(result["value"]) for result in user_results)
            fact_found = any("search term" in str(result["value"]) for result in fact_results)
            custom_found = any("custom search" in str(result["value"]) for result in custom_results)
            
            assert user_found
            assert fact_found
            assert custom_found
            
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_memory_cleanup_functionality(self):
        """Test memory cleanup and management functions."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Add some test data
            await manager.set("test_section", "key1", "value1")
            await manager.set("test_section", "key2", "value2")
            await manager.set_user_preference("pref1", "value1")
            
            # Get stats before cleanup
            stats_before = await manager.get_storage_stats()
            assert stats_before["test_section"] >= 2
            assert stats_before["user_preferences"] >= 1
            
            # Clear a specific section
            cleared_count = await manager.clear_section("test_section")
            assert cleared_count >= 2
            
            # Verify section is cleared
            keys = await manager.list_keys("test_section")
            assert len(keys) == 0
            
            # But other sections should be intact
            assert await manager.get_user_preference("pref1") == "value1"
            
            # Test cleanup of expired entries
            cleaned_count = await manager._storage.cleanup_expired()
            assert isinstance(cleaned_count, int)
            
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_memory_section_configuration(self):
        """Test memory section definitions and configurations."""
        # Test predefined sections
        sections = MemoryManager.SECTIONS
        
        assert "user_preferences" in sections
        assert "session_state" in sections
        assert "command_history" in sections
        assert "facts" in sections
        assert "temporary" in sections
        
        # Test section properties
        from nagatha_assistant.core.memory import PersistenceLevel
        
        user_prefs = sections["user_preferences"]
        assert user_prefs.persistence_level == PersistenceLevel.PERMANENT
        
        session_state = sections["session_state"]
        assert session_state.persistence_level == PersistenceLevel.SESSION
        
        temporary = sections["temporary"]
        assert temporary.persistence_level == PersistenceLevel.TEMPORARY
        
        # Test that all sections have descriptions
        for section_name, section in sections.items():
            assert section.name == section_name
            assert section.description is not None
            assert len(section.description) > 0

    @pytest.mark.asyncio
    async def test_complex_data_serialization(self):
        """Test that complex data types are properly serialized and deserialized."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Test complex nested data
            complex_data = {
                "user_info": {
                    "name": "Test User",
                    "preferences": {
                        "theme": "dark",
                        "language": "en",
                        "notifications": True
                    },
                    "history": [
                        {"action": "login", "timestamp": "2023-01-01T00:00:00Z"},
                        {"action": "query", "timestamp": "2023-01-01T00:01:00Z"}
                    ]
                },
                "metadata": {
                    "version": 1.2,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "flags": [True, False, True]
                }
            }
            
            # Store and retrieve complex data
            await manager.set("test_section", "complex_data", complex_data)
            retrieved_data = await manager.get("test_section", "complex_data")
            
            # Verify data integrity
            assert retrieved_data == complex_data
            assert retrieved_data["user_info"]["name"] == "Test User"
            assert retrieved_data["user_info"]["preferences"]["theme"] == "dark"
            assert len(retrieved_data["user_info"]["history"]) == 2
            assert retrieved_data["metadata"]["version"] == 1.2
            assert retrieved_data["metadata"]["flags"] == [True, False, True]
            
        finally:
            await manager.stop()