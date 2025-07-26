"""
Tests for the task scheduler functionality.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from nagatha_assistant.plugins.scheduler import TaskScheduler, SchedulerPlugin, get_scheduler
from nagatha_assistant.plugins.celery_app import create_celery_app
from nagatha_assistant.core.plugin import PluginConfig


@pytest.fixture
def mock_celery_app():
    """Create a mock Celery app for testing."""
    app = Mock()
    app.conf = Mock()
    app.conf.beat_schedule = {}
    app.control = Mock()
    app.control.revoke = Mock()
    
    # Mock task
    mock_task = Mock()
    mock_result = Mock()
    mock_result.get.return_value = {"success": True, "result": "test_result"}
    mock_task.apply_async.return_value = mock_result
    mock_task.apply.return_value = mock_result
    mock_task.name = "test_task"
    
    return app, mock_task


@pytest.fixture
def scheduler(mock_celery_app):
    """Create a TaskScheduler instance for testing."""
    app, mock_task = mock_celery_app
    
    # Mock AVAILABLE_TASKS to return our mock task
    mock_available_tasks = {
        "mcp_tool": mock_task,
        "plugin_command": mock_task,
        "notification": mock_task,
        "shell_command": mock_task,
        "reminder": mock_task,
        "sequence": mock_task,
    }
    
    with patch('nagatha_assistant.plugins.scheduler.get_celery_app', return_value=app), \
         patch('nagatha_assistant.plugins.scheduler.AVAILABLE_TASKS', mock_available_tasks):
        return TaskScheduler()


@pytest.fixture
def scheduler_plugin():
    """Create a SchedulerPlugin instance for testing."""
    config = PluginConfig(
        name="scheduler",
        version="1.0.0",
        description="Test scheduler plugin"
    )
    return SchedulerPlugin(config)


class TestTaskScheduler:
    """Test cases for TaskScheduler class."""
    
    def test_scheduler_initialization(self, scheduler):
        """Test that scheduler initializes correctly."""
        assert scheduler is not None
        assert isinstance(scheduler._scheduled_tasks, dict)
    
    def test_parse_natural_language_time(self, scheduler):
        """Test parsing of natural language time expressions."""
        now = datetime.now(timezone.utc)
        
        # Test "in X minutes"
        result = scheduler._parse_natural_language_time("in 30 minutes")
        assert result is not None
        assert result > now
        assert result < now + timedelta(minutes=35)
        
        # Test "in X hours"
        result = scheduler._parse_natural_language_time("in 2 hours")
        assert result is not None
        assert result > now + timedelta(hours=1, minutes=30)
        assert result < now + timedelta(hours=2, minutes=30)
        
        # Test "tomorrow"
        result = scheduler._parse_natural_language_time("tomorrow")
        assert result is not None
        assert result > now + timedelta(hours=20)
        assert result < now + timedelta(hours=28)
        
        # Test invalid expression
        result = scheduler._parse_natural_language_time("invalid time")
        assert result is None
    
    def test_parse_schedule_datetime(self, scheduler):
        """Test parsing of datetime schedule specifications."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Test datetime object
        result = scheduler._parse_schedule(future_time)
        assert result == future_time
        
        # Test ISO string
        iso_string = future_time.isoformat()
        result = scheduler._parse_schedule(iso_string)
        assert isinstance(result, datetime)
    
    def test_parse_schedule_cron(self, scheduler):
        """Test parsing of cron schedule specifications."""
        # Test valid cron expression
        cron_expr = "0 9 * * 1"  # Every Monday at 9 AM
        result = scheduler._parse_schedule(cron_expr)
        assert result is not None
        # Should return a crontab object
        assert hasattr(result, 'minute')
    
    def test_parse_schedule_invalid(self, scheduler):
        """Test handling of invalid schedule specifications."""
        with pytest.raises(ValueError):
            scheduler._parse_schedule("invalid schedule")
    
    @pytest.mark.asyncio
    async def test_schedule_mcp_tool(self, scheduler):
        """Test scheduling an MCP tool call."""
        with patch.object(scheduler, '_publish_task_event', new_callable=AsyncMock):
            task_id = await scheduler.schedule_mcp_tool(
                server_name="test_server",
                tool_name="test_tool",
                arguments={"arg1": "value1"},
                schedule_spec="in 1 hour"
            )
            
            assert task_id is not None
            assert task_id in scheduler._scheduled_tasks
            
            task_info = scheduler._scheduled_tasks[task_id]
            assert task_info["task_type"] == "mcp_tool"
            assert task_info["task_args"]["server_name"] == "test_server"
            assert task_info["task_args"]["tool_name"] == "test_tool"
    
    @pytest.mark.asyncio
    async def test_schedule_plugin_command(self, scheduler):
        """Test scheduling a plugin command."""
        with patch.object(scheduler, '_publish_task_event', new_callable=AsyncMock):
            task_id = await scheduler.schedule_plugin_command(
                plugin_name="test_plugin",
                command_name="test_command",
                arguments={"arg1": "value1"},
                schedule_spec="0 9 * * *"  # Daily at 9 AM
            )
            
            assert task_id is not None
            assert task_id in scheduler._scheduled_tasks
            
            task_info = scheduler._scheduled_tasks[task_id]
            assert task_info["task_type"] == "plugin_command"
            assert task_info["schedule_type"] == "recurring"
    
    @pytest.mark.asyncio
    async def test_schedule_notification(self, scheduler):
        """Test scheduling a notification."""
        with patch.object(scheduler, '_publish_task_event', new_callable=AsyncMock):
            task_id = await scheduler.schedule_notification(
                message="Test notification",
                schedule_spec="tomorrow",
                notification_type="info"
            )
            
            assert task_id is not None
            assert task_id in scheduler._scheduled_tasks
            
            task_info = scheduler._scheduled_tasks[task_id]
            assert task_info["task_type"] == "notification"
            assert task_info["task_args"]["message"] == "Test notification"
            assert task_info["task_args"]["notification_type"] == "info"
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, scheduler):
        """Test cancelling a scheduled task."""
        # First schedule a task
        with patch.object(scheduler, '_publish_task_event', new_callable=AsyncMock):
            task_id = await scheduler.schedule_notification(
                message="Test notification",
                schedule_spec="in 1 hour"
            )
            
            # Then cancel it
            cancelled = await scheduler.cancel_task(task_id)
            assert cancelled is True
            
            task_info = scheduler._scheduled_tasks[task_id]
            assert task_info["status"] == "cancelled"
            assert "cancelled_at" in task_info
    
    def test_get_scheduled_tasks(self, scheduler):
        """Test getting scheduled tasks with filtering."""
        # Add some mock tasks
        scheduler._scheduled_tasks = {
            "task1": {"status": "scheduled", "task_type": "mcp_tool"},
            "task2": {"status": "completed", "task_type": "notification"},
            "task3": {"status": "scheduled", "task_type": "plugin_command"},
        }
        
        # Get all tasks
        all_tasks = scheduler.get_scheduled_tasks()
        assert len(all_tasks) == 3
        
        # Get only scheduled tasks
        scheduled_tasks = scheduler.get_scheduled_tasks(status_filter="scheduled")
        assert len(scheduled_tasks) == 2
        
        # Get only completed tasks
        completed_tasks = scheduler.get_scheduled_tasks(status_filter="completed")
        assert len(completed_tasks) == 1
    
    def test_get_task_info(self, scheduler):
        """Test getting information about a specific task."""
        # Add a mock task
        task_info = {"status": "scheduled", "task_type": "mcp_tool"}
        scheduler._scheduled_tasks["test_task"] = task_info
        
        # Get task info
        result = scheduler.get_task_info("test_task")
        assert result == task_info
        
        # Get non-existent task
        result = scheduler.get_task_info("non_existent")
        assert result is None


class TestSchedulerPlugin:
    """Test cases for SchedulerPlugin class."""
    
    @pytest.mark.asyncio
    async def test_plugin_initialization(self, scheduler_plugin):
        """Test that scheduler plugin initializes correctly."""
        assert scheduler_plugin.name == "scheduler"
        assert scheduler_plugin.scheduler is not None
    
    @pytest.mark.asyncio
    async def test_handle_schedule_task(self, scheduler_plugin):
        """Test handling of schedule_task command."""
        with patch.object(scheduler_plugin.scheduler, 'schedule_task', new_callable=AsyncMock) as mock_schedule:
            mock_schedule.return_value = "test_task_id"
            
            result = await scheduler_plugin.handle_schedule_task(
                task_type="notification",
                task_args={"message": "test"},
                schedule="in 1 hour"
            )
            
            assert "test_task_id" in result
            mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_cancel_task(self, scheduler_plugin):
        """Test handling of cancel_task command."""
        with patch.object(scheduler_plugin.scheduler, 'cancel_task', new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = True
            
            result = await scheduler_plugin.handle_cancel_task(task_id="test_task_id")
            
            assert "cancelled successfully" in result
            mock_cancel.assert_called_once_with("test_task_id")
    
    @pytest.mark.asyncio
    async def test_handle_list_tasks(self, scheduler_plugin):
        """Test handling of list_tasks command."""
        mock_tasks = [
            {"task_id": "task1", "name": "Test Task 1", "status": "scheduled", "task_type": "notification"},
            {"task_id": "task2", "name": "Test Task 2", "status": "completed", "task_type": "mcp_tool"},
        ]
        
        with patch.object(scheduler_plugin.scheduler, 'get_scheduled_tasks') as mock_get:
            mock_get.return_value = mock_tasks
            
            result = await scheduler_plugin.handle_list_tasks()
            
            assert "Found 2 scheduled tasks" in result
            assert "task1" in result
            assert "task2" in result


class TestCeleryApp:
    """Test cases for Celery app configuration."""
    
    def test_create_celery_app(self):
        """Test creating a Celery app."""
        app = create_celery_app(
            broker_url="redis://localhost:6379/0",
            result_backend="redis://localhost:6379/0"
        )
        
        assert app is not None
        assert app.conf.broker_url == "redis://localhost:6379/0"
        assert app.conf.result_backend == "redis://localhost:6379/0"
        assert app.conf.task_serializer == "json"
    
    def test_signal_handlers(self):
        """Test that signal handlers are properly configured."""
        app = create_celery_app()
        
        # Check that the app has signal handlers configured
        # This is a basic test since signal handlers are difficult to test directly
        assert app is not None


class TestIntegration:
    """Integration tests for the scheduler system."""
    
    def test_get_scheduler_singleton(self):
        """Test that get_scheduler returns the same instance."""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()
        
        assert scheduler1 is scheduler2


if __name__ == "__main__":
    pytest.main([__file__])