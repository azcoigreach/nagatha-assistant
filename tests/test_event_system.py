"""
Tests for the event system (event.py and event_bus.py).
"""

import asyncio
import pytest
import pytest_asyncio
import time
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from nagatha_assistant.core.event import (
    Event, EventPriority, StandardEventTypes,
    create_system_event, create_agent_event, create_mcp_event
)
from nagatha_assistant.core.event_bus import EventBus, EventBusError


class TestEvent:
    """Test the Event class and helper functions."""
    
    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(event_type="test.event", data={"key": "value"})
        
        assert event.event_type == "test.event"
        assert event.data == {"key": "value"}
        assert event.priority == EventPriority.NORMAL
        assert event.source is None
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.timestamp.tzinfo is not None  # Should be timezone-aware
    
    def test_event_with_all_fields(self):
        """Test event creation with all fields specified."""
        timestamp = datetime.now(timezone.utc)
        event = Event(
            event_type="test.priority",
            data={"test": True},
            priority=EventPriority.HIGH,
            source="test_source",
            correlation_id="test-123",
            event_id="custom-id",
            timestamp=timestamp
        )
        
        assert event.event_type == "test.priority"
        assert event.data == {"test": True}
        assert event.priority == EventPriority.HIGH
        assert event.source == "test_source"
        assert event.correlation_id == "test-123"
        assert event.event_id == "custom-id"
        assert event.timestamp == timestamp
    
    def test_event_priority_ordering(self):
        """Test that event priorities are ordered correctly."""
        assert EventPriority.CRITICAL < EventPriority.HIGH
        assert EventPriority.HIGH < EventPriority.NORMAL
        assert EventPriority.NORMAL < EventPriority.LOW
    
    def test_create_system_event(self):
        """Test the create_system_event helper."""
        event = create_system_event("system.test", {"key": "value"}, EventPriority.HIGH)
        
        assert event.event_type == "system.test"
        assert event.data == {"key": "value"}
        assert event.priority == EventPriority.HIGH
        assert event.source == "system"
    
    def test_create_agent_event(self):
        """Test the create_agent_event helper."""
        event = create_agent_event("agent.test", 123, {"message": "hello"})
        
        assert event.event_type == "agent.test"
        assert event.data == {"session_id": 123, "message": "hello"}
        assert event.source == "agent"
    
    def test_create_mcp_event(self):
        """Test the create_mcp_event helper."""
        event = create_mcp_event("mcp.test", "test-server", {"tool": "test_tool"})
        
        assert event.event_type == "mcp.test"
        assert event.data == {"server_name": "test-server", "tool": "test_tool"}
        assert event.source == "mcp"
    
    def test_standard_event_types(self):
        """Test that standard event types are defined."""
        assert hasattr(StandardEventTypes, 'SYSTEM_STARTUP')
        assert hasattr(StandardEventTypes, 'AGENT_MESSAGE_RECEIVED')
        assert hasattr(StandardEventTypes, 'MCP_SERVER_CONNECTED')
        assert hasattr(StandardEventTypes, 'DB_ENTITY_CREATED')


class TestEventBus:
    """Test the EventBus class."""
    
    @pytest_asyncio.fixture
    async def event_bus(self):
        """Create and start an event bus for testing."""
        bus = EventBus(max_history=100)
        await bus.start()
        yield bus
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_event_bus_start_stop(self):
        """Test starting and stopping the event bus."""
        bus = EventBus()
        
        # Should not be running initially
        assert not bus._running
        
        # Start the bus
        await bus.start()
        assert bus._running
        assert bus._event_queue is not None
        assert bus._processor_task is not None
        
        # Stop the bus
        await bus.stop()
        assert not bus._running
    
    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self, event_bus):
        """Test subscribing and unsubscribing from events."""
        handler = Mock()
        
        # Subscribe
        sub_id = event_bus.subscribe("test.*", handler)
        assert isinstance(sub_id, int)
        
        # Check subscription exists
        subs = event_bus.get_subscriptions()
        assert len(subs) == 1
        assert subs[0]["pattern"] == "test.*"
        
        # Unsubscribe
        result = event_bus.unsubscribe(sub_id)
        assert result is True
        
        # Check subscription removed
        subs = event_bus.get_subscriptions()
        assert len(subs) == 0
        
        # Try to unsubscribe again
        result = event_bus.unsubscribe(sub_id)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_and_receive_event(self, event_bus):
        """Test publishing and receiving events."""
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Subscribe to all test events
        event_bus.subscribe("test.*", handler)
        
        # Publish an event
        test_event = Event("test.example", {"data": "test"})
        await event_bus.publish(test_event)
        
        # Give some time for processing
        await asyncio.sleep(0.1)
        
        # Check event was received
        assert len(received_events) == 1
        assert received_events[0].event_type == "test.example"
        assert received_events[0].data == {"data": "test"}
    
    @pytest.mark.asyncio
    async def test_async_handler(self, event_bus):
        """Test async event handlers."""
        received_events = []
        
        async def async_handler(event):
            await asyncio.sleep(0.01)  # Simulate async work
            received_events.append(event)
        
        event_bus.subscribe("async.*", async_handler)
        
        test_event = Event("async.test", {"async": True})
        await event_bus.publish(test_event)
        
        # Give time for async processing
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].event_type == "async.test"
    
    @pytest.mark.asyncio
    async def test_wildcard_patterns(self, event_bus):
        """Test wildcard pattern matching."""
        all_events = []
        agent_events = []
        specific_events = []
        
        event_bus.subscribe("*", lambda e: all_events.append(e))
        event_bus.subscribe("agent.*", lambda e: agent_events.append(e))
        event_bus.subscribe("agent.message.*", lambda e: specific_events.append(e))
        
        # Publish various events
        events = [
            Event("system.startup"),
            Event("agent.started"),
            Event("agent.message.sent"),
            Event("mcp.tool.called")
        ]
        
        for event in events:
            await event_bus.publish(event)
        
        await asyncio.sleep(0.1)
        
        # Check pattern matching
        assert len(all_events) == 4  # All events
        assert len(agent_events) == 2  # agent.started and agent.message.sent
        assert len(specific_events) == 1  # Only agent.message.sent
    
    @pytest.mark.asyncio
    async def test_priority_filtering(self, event_bus):
        """Test event filtering by priority."""
        high_events = []
        all_events = []
        
        # Subscribe with priority filter
        event_bus.subscribe("test.*", lambda e: high_events.append(e), 
                          priority_filter=EventPriority.HIGH)
        event_bus.subscribe("test.*", lambda e: all_events.append(e))
        
        # Publish events with different priorities
        events = [
            Event("test.critical", priority=EventPriority.CRITICAL),
            Event("test.high", priority=EventPriority.HIGH),
            Event("test.normal", priority=EventPriority.NORMAL),
            Event("test.low", priority=EventPriority.LOW)
        ]
        
        for event in events:
            await event_bus.publish(event)
        
        await asyncio.sleep(0.1)
        
        # All handler should receive all events
        assert len(all_events) == 4
        
        # High priority handler should only receive CRITICAL and HIGH
        assert len(high_events) == 2
        assert all(e.priority <= EventPriority.HIGH for e in high_events)
    
    @pytest.mark.asyncio
    async def test_source_filtering(self, event_bus):
        """Test event filtering by source."""
        agent_events = []
        all_events = []
        
        # Subscribe with source filter
        event_bus.subscribe("*", lambda e: agent_events.append(e), source_filter="agent")
        event_bus.subscribe("*", lambda e: all_events.append(e))
        
        # Publish events from different sources
        events = [
            Event("test.event1", source="agent"),
            Event("test.event2", source="mcp"),
            Event("test.event3", source="agent"),
            Event("test.event4", source="system")
        ]
        
        for event in events:
            await event_bus.publish(event)
        
        await asyncio.sleep(0.1)
        
        assert len(all_events) == 4
        assert len(agent_events) == 2
        assert all(e.source == "agent" for e in agent_events)
    
    @pytest.mark.asyncio
    async def test_event_history(self, event_bus):
        """Test event history tracking."""
        # Initially no history
        history = event_bus.get_event_history()
        assert len(history) == 0
        
        # Publish some events
        events = [
            Event("test.first"),
            Event("test.second"),
            Event("other.event")
        ]
        
        for event in events:
            await event_bus.publish(event)
        
        await asyncio.sleep(0.1)
        
        # Check full history
        history = event_bus.get_event_history()
        assert len(history) == 3
        # Should be in reverse chronological order (most recent first)
        assert history[0].event_type == "other.event"
        assert history[2].event_type == "test.first"
        
        # Check filtered history
        test_history = event_bus.get_event_history(event_type_pattern="test.*")
        assert len(test_history) == 2
        assert all("test." in e.event_type for e in test_history)
        
        # Check limited history
        limited_history = event_bus.get_event_history(limit=1)
        assert len(limited_history) == 1
        assert limited_history[0].event_type == "other.event"
    
    @pytest.mark.asyncio 
    async def test_unsubscribe_handler(self, event_bus):
        """Test unsubscribing all subscriptions for a handler."""
        handler = Mock()
        
        # Subscribe same handler to multiple patterns
        sub1 = event_bus.subscribe("test.*", handler)
        sub2 = event_bus.subscribe("agent.*", handler)
        sub3 = event_bus.subscribe("mcp.*", handler)
        
        assert len(event_bus.get_subscriptions()) == 3
        
        # Unsubscribe by handler
        removed_count = event_bus.unsubscribe_handler(handler)
        assert removed_count == 3
        assert len(event_bus.get_subscriptions()) == 0
    
    @pytest.mark.asyncio
    async def test_publish_when_not_running(self):
        """Test publishing when event bus is not running."""
        bus = EventBus()
        
        with pytest.raises(EventBusError):
            await bus.publish(Event("test.event"))
    
    def test_publish_sync(self, event_bus):
        """Test synchronous publish method."""
        handler = Mock()
        event_bus.subscribe("sync.*", handler)
        
        # Should not raise exception
        event_bus.publish_sync(Event("sync.test"))
        
        # Note: We can't easily test the async processing in sync context
        # This mainly tests that the method doesn't crash
    
    @pytest.mark.asyncio
    async def test_clear_history(self, event_bus):
        """Test clearing event history."""
        # Publish some events
        await event_bus.publish(Event("test.1"))
        await event_bus.publish(Event("test.2"))
        
        await asyncio.sleep(0.1)
        
        # Verify history exists
        history = event_bus.get_event_history()
        assert len(history) == 2
        
        # Clear history
        event_bus.clear_history()
        
        # Verify history is empty
        history = event_bus.get_event_history()
        assert len(history) == 0


class TestEventBusGlobal:
    """Test the global event bus functions."""
    
    def test_get_event_bus_singleton(self):
        """Test that get_event_bus returns the same instance."""
        from nagatha_assistant.core.event_bus import get_event_bus
        
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is bus2
    
    @pytest.mark.asyncio
    async def test_ensure_event_bus_started(self):
        """Test ensure_event_bus_started function."""
        from nagatha_assistant.core.event_bus import ensure_event_bus_started, shutdown_event_bus
        
        bus = await ensure_event_bus_started()
        assert bus._running
        
        # Cleanup
        await shutdown_event_bus()
    
    @pytest.mark.asyncio
    async def test_shutdown_event_bus(self):
        """Test shutdown_event_bus function."""
        from nagatha_assistant.core.event_bus import ensure_event_bus_started, shutdown_event_bus, _event_bus
        
        # Start bus
        await ensure_event_bus_started()
        
        # Shutdown
        await shutdown_event_bus()
        
        # Should be None after shutdown
        assert _event_bus is None