"""
Integration tests for the event bus system with the agent module.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import patch, Mock, AsyncMock

from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import StandardEventTypes, EventPriority
from nagatha_assistant.core.agent import startup, shutdown, start_session


class TestEventBusIntegration:
    """Test integration between event bus and agent module."""
    
    @pytest_asyncio.fixture
    async def clean_event_bus(self):
        """Ensure we have a clean event bus for testing."""
        # Stop any existing event bus
        try:
            bus = get_event_bus()
            if bus._running:
                await bus.stop()
        except:
            pass
        
        # Clear the global event bus
        from nagatha_assistant.core.event_bus import _event_bus, _bus_lock
        global _event_bus
        with _bus_lock:
            _event_bus = None
        
        yield
        
        # Cleanup after test
        try:
            bus = get_event_bus()
            if bus._running:
                await bus.stop()
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_startup_publishes_system_event(self, clean_event_bus):
        """Test that startup() publishes a system startup event."""
        received_events = []
        
        # Start event bus
        event_bus = get_event_bus()
        await event_bus.start()
        
        # Subscribe to system events
        def system_handler(event):
            received_events.append(event)
        
        event_bus.subscribe("system.*", system_handler)
        
        # Mock the MCP manager to avoid database requirements
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_mcp:
            with patch('nagatha_assistant.core.agent.init_db') as mock_db:
                mock_manager = Mock()
                mock_manager.get_initialization_summary.return_value = {
                    "connected": 0, 
                    "total_configured": 0, 
                    "errors": []
                }
                mock_mcp.return_value = mock_manager
                
                # Call startup
                await startup()
        
        # Give time for event processing
        await asyncio.sleep(0.1)
        
        # Verify system startup event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == StandardEventTypes.SYSTEM_STARTUP
        assert event.priority == EventPriority.HIGH
        assert event.source == "system"
        
        await event_bus.stop()
    
    @pytest.mark.asyncio
    async def test_shutdown_publishes_system_event(self, clean_event_bus):
        """Test that shutdown() publishes a system shutdown event."""
        received_events = []
        
        # Start event bus
        event_bus = get_event_bus()
        await event_bus.start()
        
        # Subscribe to system events
        def system_handler(event):
            received_events.append(event)
        
        event_bus.subscribe("system.*", system_handler)
        
        # Mock the MCP manager and other dependencies
        with patch('nagatha_assistant.core.agent.shutdown_mcp_manager') as mock_shutdown:
            with patch('nagatha_assistant.core.plugin_manager.shutdown_plugin_manager') as mock_plugin_shutdown:
                with patch('nagatha_assistant.core.memory.shutdown_memory_manager') as mock_memory_shutdown:
                    # Call shutdown but don't let it stop the event bus
                    with patch.object(event_bus, 'stop') as mock_stop:
                        await shutdown()
                        
                        # Give time for event processing
                        await asyncio.sleep(0.1)
                        
                        # Verify system shutdown event was published
                        assert len(received_events) == 1
                        event = received_events[0]
                        assert event.event_type == StandardEventTypes.SYSTEM_SHUTDOWN
                        assert event.priority == EventPriority.HIGH
                        assert event.source == "system"
    
    @pytest.mark.asyncio
    async def test_start_session_publishes_agent_event(self, clean_event_bus):
        """Test that start_session() publishes an agent conversation started event."""
        received_events = []
        
        # Start event bus
        event_bus = get_event_bus()
        await event_bus.start()
        
        # Subscribe to agent events
        def agent_handler(event):
            received_events.append(event)
        
        event_bus.subscribe("agent.*", agent_handler)
        
        # Mock the database and MCP manager
        with patch('nagatha_assistant.core.agent.init_db') as mock_db:
            with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_mcp:
                with patch('nagatha_assistant.core.agent.SessionLocal') as mock_session:
                    # Mock database session
                    mock_db_session = Mock()
                    mock_session.return_value.__aenter__.return_value = mock_db_session
                    
                    # Mock conversation session
                    mock_conv_session = Mock()
                    mock_conv_session.id = 123
                    mock_conv_session.created_at = None
                    
                    mock_db_session.add = Mock()
                    mock_db_session.commit = AsyncMock()
                    mock_db_session.refresh = AsyncMock()
                    
                    # Setup return values
                    mock_db_session.add.return_value = None
                    
                    with patch('nagatha_assistant.core.agent.ConversationSession', return_value=mock_conv_session):
                        # Call start_session
                        session_id = await start_session()
        
        # Give time for event processing
        await asyncio.sleep(0.1)
        
        # Verify conversation started event was published
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == StandardEventTypes.AGENT_CONVERSATION_STARTED
        assert event.data["session_id"] == 123
        assert event.source == "agent"
        
        await event_bus.stop()
    
    @pytest.mark.asyncio
    async def test_event_history_tracking(self, clean_event_bus):
        """Test that events are properly tracked in history."""
        # Start event bus
        event_bus = get_event_bus()
        await event_bus.start()
        
        # Initially no history
        assert len(event_bus.get_event_history()) == 0
        
        # Mock and call startup
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_mcp:
            with patch('nagatha_assistant.core.agent.init_db') as mock_db:
                mock_manager = Mock()
                mock_manager.get_initialization_summary.return_value = {
                    "connected": 0, 
                    "total_configured": 0, 
                    "errors": []
                }
                mock_mcp.return_value = mock_manager
                
                await startup()
        
        # Give time for processing
        await asyncio.sleep(0.1)
        
        # Check history - should have system startup event plus plugin events
        history = event_bus.get_event_history()
        assert len(history) >= 1
        
        # Find the system startup event
        startup_events = [event for event in history if event.event_type == StandardEventTypes.SYSTEM_STARTUP]
        assert len(startup_events) == 1
        assert startup_events[0].event_type == StandardEventTypes.SYSTEM_STARTUP
        
        # Call shutdown but don't let it stop the event bus
        with patch('nagatha_assistant.core.agent.shutdown_mcp_manager') as mock_shutdown:
            with patch('nagatha_assistant.core.plugin_manager.shutdown_plugin_manager') as mock_plugin_shutdown:
                with patch('nagatha_assistant.core.memory.shutdown_memory_manager') as mock_memory_shutdown:
                    with patch.object(event_bus, 'stop') as mock_stop:
                        await shutdown()
                        
                        await asyncio.sleep(0.1)
                        
                        # Check history again - should have both startup and shutdown events
                        history = event_bus.get_event_history()
                        assert len(history) >= 2
                        
                        # Find the system events
                        system_events = [event for event in history if event.event_type in [StandardEventTypes.SYSTEM_STARTUP, StandardEventTypes.SYSTEM_SHUTDOWN]]
                        assert len(system_events) >= 2
                        
                        # Check that we have both startup and shutdown events
                        startup_events = [event for event in system_events if event.event_type == StandardEventTypes.SYSTEM_STARTUP]
                        shutdown_events = [event for event in system_events if event.event_type == StandardEventTypes.SYSTEM_SHUTDOWN]
                        assert len(startup_events) >= 1
                        assert len(shutdown_events) >= 1
    
    @pytest.mark.asyncio
    async def test_multiple_event_subscribers(self, clean_event_bus):
        """Test that multiple subscribers can receive the same events."""
        received_by_handler1 = []
        received_by_handler2 = []
        
        # Start event bus
        event_bus = get_event_bus()
        await event_bus.start()
        
        # Subscribe multiple handlers to system events
        def handler1(event):
            received_by_handler1.append(event)
        
        def handler2(event):
            received_by_handler2.append(event)
        
        event_bus.subscribe("system.*", handler1)
        event_bus.subscribe("system.*", handler2)
        
        # Mock and call startup
        with patch('nagatha_assistant.core.agent.get_mcp_manager') as mock_mcp:
            with patch('nagatha_assistant.core.agent.init_db') as mock_db:
                mock_manager = Mock()
                mock_manager.get_initialization_summary.return_value = {
                    "connected": 0, 
                    "total_configured": 0, 
                    "errors": []
                }
                mock_mcp.return_value = mock_manager
                
                await startup()
        
        await asyncio.sleep(0.1)
        
        # Both handlers should have received the event
        assert len(received_by_handler1) == 1
        assert len(received_by_handler2) == 1
        assert received_by_handler1[0].event_type == StandardEventTypes.SYSTEM_STARTUP
        assert received_by_handler2[0].event_type == StandardEventTypes.SYSTEM_STARTUP
        
        await event_bus.stop()