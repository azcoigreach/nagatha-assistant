"""
Simple tests for the task scheduler functionality (without Celery integration).
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from nagatha_assistant.plugins.scheduler import TaskScheduler, SchedulerPlugin, get_scheduler
from nagatha_assistant.core.plugin import PluginConfig


class TestTaskSchedulerBasic:
    """Basic test cases for TaskScheduler class without Celery integration."""
    
    def test_scheduler_initialization(self):
        """Test that scheduler initializes correctly."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            assert scheduler is not None
            assert isinstance(scheduler._scheduled_tasks, dict)
    
    def test_parse_natural_language_time(self):
        """Test parsing of natural language time expressions."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
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
    
    def test_parse_schedule_datetime(self):
        """Test parsing of datetime schedule specifications."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            future_time = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # Test datetime object
            result = scheduler._parse_schedule(future_time)
            assert result == future_time
            
            # Test ISO string
            iso_string = future_time.isoformat()
            result = scheduler._parse_schedule(iso_string)
            assert isinstance(result, datetime)
    
    def test_parse_schedule_cron(self):
        """Test parsing of cron schedule specifications."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            
            # Test valid cron expression
            cron_expr = "0 9 * * 1"  # Every Monday at 9 AM
            result = scheduler._parse_schedule(cron_expr)
            assert result is not None
            # Should return a crontab object
            assert hasattr(result, 'minute')
    
    def test_parse_schedule_invalid(self):
        """Test handling of invalid schedule specifications."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            with pytest.raises(ValueError):
                scheduler._parse_schedule("invalid schedule")
    
    def test_prepare_task_args(self):
        """Test task argument preparation."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            
            # Test MCP tool args
            args = scheduler._prepare_task_args("mcp_tool", {
                "server_name": "test_server",
                "tool_name": "test_tool", 
                "arguments": {"arg1": "value1"}
            })
            assert args == ["test_server", "test_tool", {"arg1": "value1"}]
            
            # Test plugin command args
            args = scheduler._prepare_task_args("plugin_command", {
                "plugin_name": "test_plugin",
                "command_name": "test_command",
                "arguments": {"arg1": "value1"}
            })
            assert args == ["test_plugin", "test_command", {"arg1": "value1"}]
            
            # Test notification args
            args = scheduler._prepare_task_args("notification", {
                "message": "test message"
            })
            assert args == ["test message"]
    
    def test_get_scheduled_tasks(self):
        """Test getting scheduled tasks with filtering."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            
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
    
    def test_get_task_info(self):
        """Test getting information about a specific task."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler = TaskScheduler()
            
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
    async def test_plugin_initialization(self):
        """Test that scheduler plugin initializes correctly."""
        config = PluginConfig(
            name="scheduler",
            version="1.0.0",
            description="Test scheduler plugin"
        )
        
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            plugin = SchedulerPlugin(config)
            assert plugin.name == "scheduler"
            assert plugin.scheduler is not None
    
    @pytest.mark.asyncio
    async def test_handle_schedule_task(self):
        """Test handling of schedule_task command."""
        config = PluginConfig(
            name="scheduler",
            version="1.0.0",
            description="Test scheduler plugin"
        )
        
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            plugin = SchedulerPlugin(config)
            
            with patch.object(plugin.scheduler, 'schedule_task', new_callable=AsyncMock) as mock_schedule:
                mock_schedule.return_value = "test_task_id"
                
                result = await plugin.handle_schedule_task(
                    task_type="notification",
                    task_args={"message": "test"},
                    schedule="in 1 hour"
                )
                
                assert "test_task_id" in result
                mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_cancel_task(self):
        """Test handling of cancel_task command."""
        config = PluginConfig(
            name="scheduler",
            version="1.0.0",
            description="Test scheduler plugin"
        )
        
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            plugin = SchedulerPlugin(config)
            
            with patch.object(plugin.scheduler, 'cancel_task', new_callable=AsyncMock) as mock_cancel:
                mock_cancel.return_value = True
                
                result = await plugin.handle_cancel_task(task_id="test_task_id")
                
                assert "cancelled successfully" in result
                mock_cancel.assert_called_once_with("test_task_id")
    
    @pytest.mark.asyncio
    async def test_handle_list_tasks(self):
        """Test handling of list_tasks command."""
        config = PluginConfig(
            name="scheduler",
            version="1.0.0",
            description="Test scheduler plugin"
        )
        
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            plugin = SchedulerPlugin(config)
            
            mock_tasks = [
                {"task_id": "task1", "name": "Test Task 1", "status": "scheduled", "task_type": "notification"},
                {"task_id": "task2", "name": "Test Task 2", "status": "completed", "task_type": "mcp_tool"},
            ]
            
            with patch.object(plugin.scheduler, 'get_scheduled_tasks') as mock_get:
                mock_get.return_value = mock_tasks
                
                result = await plugin.handle_list_tasks()
                
                assert "Found 2 scheduled tasks" in result
                assert "task1" in result
                assert "task2" in result


class TestIntegration:
    """Integration tests for the scheduler system."""
    
    def test_get_scheduler_singleton(self):
        """Test that get_scheduler returns the same instance."""
        with patch('nagatha_assistant.plugins.scheduler.get_celery_app'):
            scheduler1 = get_scheduler()
            scheduler2 = get_scheduler()
            
            assert scheduler1 is scheduler2


if __name__ == "__main__":
    pytest.main([__file__])