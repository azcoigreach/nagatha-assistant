"""
Tests for the Nagatha Assistant Dashboard UI components.
"""

import pytest
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

# Set up test environment
os.environ["OPENAI_API_KEY"] = "dummy-test-key"

from nagatha_assistant.ui.widgets import StatusPanel, CommandPanel, NotificationPanel, ResourceMonitor
from nagatha_assistant.ui.dashboard import DashboardApp
from nagatha_assistant.core.event import Event, EventPriority


class TestDashboardWidgets:
    """Test suite for dashboard widget components."""

    def test_status_panel_creation(self):
        """Test that StatusPanel can be created."""
        panel = StatusPanel()
        assert panel is not None
        assert panel.session_id is None
        assert panel.refresh_interval == 30

    def test_command_panel_creation(self):
        """Test that CommandPanel can be created."""
        panel = CommandPanel()
        assert panel is not None
        assert panel.current_session_id is None
        assert panel.command_mode == "chat"
        assert len(panel.command_history) == 0

    def test_notification_panel_creation(self):
        """Test that NotificationPanel can be created."""
        panel = NotificationPanel()
        assert panel is not None
        assert panel.unread_count == 0
        assert panel.total_notifications == 0
        assert len(panel.notifications) == 0

    def test_resource_monitor_creation(self):
        """Test that ResourceMonitor can be created."""
        monitor = ResourceMonitor()
        assert monitor is not None
        assert monitor.cpu_usage == 0.0
        assert monitor.memory_usage == 0.0
        assert monitor.disk_usage == 0.0

    def test_dashboard_app_creation(self):
        """Test that DashboardApp can be created."""
        app = DashboardApp()
        assert app is not None
        assert app.title == "Nagatha Assistant - Dashboard"
        assert app.current_session_id is None


class TestCommandPanel:
    """Focused tests for CommandPanel functionality."""

    def test_determine_command_type(self):
        """Test command type determination."""
        panel = CommandPanel()
        
        # Test system commands
        assert panel._determine_command_type("/help") == "system"
        assert panel._determine_command_type("/status") == "system"
        assert panel._determine_command_type("/sessions") == "system"
        
        # Test tool commands
        assert panel._determine_command_type("run: python script") == "tool"
        assert panel._determine_command_type("execute: command") == "tool"
        assert panel._determine_command_type("tool: something") == "tool"
        
        # Test chat commands
        assert panel._determine_command_type("Hello there") == "chat"
        assert panel._determine_command_type("What's the weather?") == "chat"

    def test_command_history_management(self):
        """Test command history functionality."""
        panel = CommandPanel()
        
        # Test adding commands
        panel._add_to_history("first command")
        assert len(panel.command_history) == 1
        assert panel.command_history[0] == "first command"
        
        # Test avoiding duplicates
        panel._add_to_history("first command")
        assert len(panel.command_history) == 1
        
        # Test adding different command
        panel._add_to_history("second command")
        assert len(panel.command_history) == 2
        assert panel.command_history[-1] == "second command"

    def test_session_id_setting(self):
        """Test setting session ID."""
        panel = CommandPanel()
        assert panel.current_session_id is None
        
        panel.set_session_id(123)
        assert panel.current_session_id == 123


class TestNotificationPanel:
    """Focused tests for NotificationPanel functionality."""

    @pytest.mark.asyncio
    async def test_notification_creation_and_management(self):
        """Test notification creation and management."""
        panel = NotificationPanel()
        
        # Test adding a system notification
        await panel._add_system_notification("Test Title", "Test message", "info")
        
        assert panel.total_notifications == 1
        assert panel.unread_count == 1
        assert len(panel.notifications) == 1
        
        notification = panel.notifications[0]
        assert notification.title == "Test Title"
        assert notification.message == "Test message"
        assert notification.type == "info"
        assert not notification.read

    @pytest.mark.asyncio
    async def test_event_handling(self):
        """Test event handling for notifications."""
        panel = NotificationPanel()
        
        # Create test event
        test_event = Event(
            event_type="agent.message.received",
            data={"session_id": 123, "content": "Test message content"},
            priority=EventPriority.NORMAL,
            source="agent"
        )
        
        # Handle the event
        await panel._handle_event(test_event)
        
        # Check notification was created
        assert panel.total_notifications == 1
        assert panel.unread_count == 1

    def test_mark_all_read(self):
        """Test marking all notifications as read."""
        panel = NotificationPanel()
        
        # Add some test notifications manually
        from nagatha_assistant.ui.widgets.notification_panel import NotificationItem
        
        panel.notifications = [
            NotificationItem("1", "Title 1", "Message 1"),
            NotificationItem("2", "Title 2", "Message 2"),
        ]
        panel.unread_count = 2
        
        # Mark all as read
        panel.action_mark_all_read()
        
        assert panel.unread_count == 0
        assert all(n.read for n in panel.notifications)


class TestResourceMonitor:
    """Focused tests for ResourceMonitor functionality."""

    @pytest.mark.asyncio
    async def test_resource_metrics_collection(self):
        """Test resource metrics collection."""
        from nagatha_assistant.ui.widgets.resource_monitor import ResourceMetrics
        
        # Test that metrics can be collected without errors
        metrics = await ResourceMetrics.collect()
        
        assert isinstance(metrics.cpu_percent, float)
        assert isinstance(metrics.memory_percent, float)
        assert isinstance(metrics.disk_percent, float)
        assert metrics.memory_used_mb >= 0
        assert metrics.memory_total_mb > 0
        assert metrics.disk_used_gb >= 0
        assert metrics.disk_total_gb > 0

    @pytest.mark.asyncio
    async def test_token_usage_metrics(self):
        """Test token usage metrics collection."""
        from nagatha_assistant.ui.widgets.resource_monitor import TokenUsageMetrics
        
        # Mock the load_usage function
        with patch('nagatha_assistant.ui.widgets.resource_monitor.load_usage') as mock_load:
            mock_load.return_value = {
                "gpt-4o": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost": 0.025,
                    "requests": 5
                }
            }
            
            metrics = await TokenUsageMetrics.collect()
            
            assert metrics.total_input_tokens == 1000
            assert metrics.total_output_tokens == 500
            assert metrics.total_cost == 0.025
            assert metrics.requests_count == 5
            assert metrics.average_tokens_per_request == 300  # (1000 + 500) / 5

    def test_resource_trend_calculation(self):
        """Test resource trend calculation."""
        from nagatha_assistant.ui.widgets.resource_monitor import ResourceMetrics
        
        monitor = ResourceMonitor()
        
        # Add some test metrics to history
        for i in range(5):
            metrics = ResourceMetrics()
            metrics.cpu_percent = i * 20.0  # 0, 20, 40, 60, 80
            monitor.metrics_history.append(metrics)
        
        # Test CPU trend
        cpu_trend = monitor.get_resource_trend("cpu", 3)
        assert cpu_trend == [40.0, 60.0, 80.0]  # Last 3 values


class TestDashboardIntegration:
    """Integration tests for the complete dashboard."""

    @pytest.mark.asyncio
    async def test_dashboard_compose(self):
        """Test that dashboard composes without errors."""
        app = DashboardApp()
        
        # Test that the compose method exists and is callable
        assert hasattr(app, 'compose')
        assert callable(app.compose)
        
        # Test that the app can be created without errors
        assert app.title == "Nagatha Assistant - Dashboard"
        assert app.current_session_id is None

    def test_dashboard_bindings(self):
        """Test that dashboard has proper key bindings."""
        app = DashboardApp()
        
        # Check that important bindings exist
        binding_keys = [binding.key for binding in app.BINDINGS]
        
        assert "ctrl+q" in binding_keys  # Quit
        assert "ctrl+r" in binding_keys  # Refresh
        assert "ctrl+s" in binding_keys  # Sessions
        assert "ctrl+t" in binding_keys  # Tools
        assert "ctrl+1" in binding_keys  # Focus command

    @pytest.mark.asyncio
    async def test_system_command_handling(self):
        """Test system command handling."""
        app = DashboardApp()
        
        # Test help command
        await app._handle_system_command("/help")
        # Should not raise exceptions
        
        # Test status command
        with patch.object(app, '_show_system_status') as mock_status:
            await app._handle_system_command("/status")
            mock_status.assert_called_once()

    def test_conversation_area_updates(self):
        """Test conversation area updating."""
        app = DashboardApp()
        
        # Mock the conversation area widget
        with patch.object(app, 'query_one') as mock_query:
            mock_widget = Mock()
            mock_widget.renderable = "Initial text"
            mock_query.return_value = mock_widget
            
            # Test updating conversation area
            app._update_conversation_area("Test message")
            
            # Should have called update on the widget
            mock_widget.update.assert_called_once()

    def test_help_text_generation(self):
        """Test help text generation."""
        app = DashboardApp()
        
        help_text = app._get_help_text()
        
        assert "Available Commands:" in help_text
        assert "/help" in help_text
        assert "/status" in help_text
        assert "Keyboard Shortcuts:" in help_text
        assert "Ctrl+1" in help_text


if __name__ == "__main__":
    pytest.main([__file__])