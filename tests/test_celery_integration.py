"""
Tests for Celery task scheduling integration.

This module tests the complete Celery integration including:
- Core Celery application setup
- Task scheduling functionality
- CLI commands
- Task execution and history
- Event integration
"""

import pytest
import asyncio
import tempfile
import json
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from celery import Celery
from celery.schedules import crontab, timedelta as celery_timedelta

# Import the modules we're testing
from nagatha_assistant.core.celery_app import (
    celery_app, add_periodic_task, remove_periodic_task, 
    clear_beat_schedule, get_beat_schedule, initialize_celery,
    reload_beat_schedule
)
from nagatha_assistant.plugins.tasks import system_health_check
from nagatha_assistant.core.scheduler import (
    TaskScheduler, get_scheduler, schedule_task, 
    schedule_one_time, schedule_recurring, cancel_task, 
    list_scheduled_tasks
)
from nagatha_assistant.core.memory import get_memory_manager
from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import create_system_event, StandardEventTypes


class TestCeleryApp:
    """Test the core Celery application configuration and functions."""
    
    def test_celery_app_configuration(self):
        """Test that Celery app is properly configured."""
        assert celery_app is not None
        assert isinstance(celery_app, Celery)
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.accept_content == ['json']
        assert celery_app.conf.timezone == 'UTC'
        assert celery_app.conf.enable_utc is True
    
    def test_add_periodic_task(self, tmp_path):
        """Test adding periodic tasks to the beat schedule."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear any existing schedule
        celery_app.conf.beat_schedule.clear()
        
        # Add a test task
        add_periodic_task(
            "test_task",
            "nagatha.system.health_check",
            celery_timedelta(minutes=5)
        )
        
        # Check that task was added to schedule
        assert "test_task" in celery_app.conf.beat_schedule
        task_config = celery_app.conf.beat_schedule["test_task"]
        assert task_config["task"] == "nagatha.system.health_check"
        assert isinstance(task_config["schedule"], celery_timedelta)
        assert task_config["schedule"].total_seconds() == 300  # 5 minutes
    
    def test_remove_periodic_task(self, tmp_path):
        """Test removing periodic tasks from the beat schedule."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Add a task first
        add_periodic_task(
            "test_task",
            "nagatha.system.health_check",
            celery_timedelta(minutes=5)
        )
        
        # Verify task exists
        assert "test_task" in celery_app.conf.beat_schedule
        
        # Remove the task
        remove_periodic_task("test_task")
        
        # Verify task was removed
        assert "test_task" not in celery_app.conf.beat_schedule
    
    def test_clear_beat_schedule(self, tmp_path):
        """Test clearing all periodic tasks from the beat schedule."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Add multiple tasks
        add_periodic_task("task1", "nagatha.system.health_check", celery_timedelta(minutes=5))
        add_periodic_task("task2", "nagatha.system.backup_database", celery_timedelta(hours=1))
        
        # Verify tasks exist
        assert len(celery_app.conf.beat_schedule) >= 2
        
        # Clear all tasks
        clear_beat_schedule()
        
        # Verify all tasks were removed
        assert len(celery_app.conf.beat_schedule) == 0
    
    def test_get_beat_schedule(self, tmp_path):
        """Test getting the current beat schedule."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear and add a test task
        clear_beat_schedule()
        add_periodic_task(
            "test_task",
            "nagatha.system.health_check",
            celery_timedelta(minutes=5)
        )
        
        # Get the schedule
        schedule = get_beat_schedule()
        
        # Verify schedule contains our task
        assert "test_task" in schedule
        assert schedule["test_task"]["task"] == "nagatha.system.health_check"
    
    def test_health_check_task(self):
        """Test the health check task execution."""
        # Mock the task request
        mock_request = Mock()
        mock_request.id = "test_task_id"
        mock_request.hostname = "test_worker"
        
        # Create a mock task instance
        mock_task = Mock()
        mock_task.request = mock_request
        
        # Patch psutil to avoid system calls
        with patch('psutil.cpu_percent', return_value=25.0), \
             patch('psutil.virtual_memory', return_value=Mock(percent=50.0)), \
             patch('psutil.disk_usage', return_value=Mock(percent=30.0)):
            
            # Execute the health check by calling the underlying function
            result = system_health_check.run()
            
            # Verify the result structure
            assert isinstance(result, dict)
            assert 'cpu_percent' in result
            assert 'memory_percent' in result
            assert 'disk_percent' in result
            assert 'timestamp' in result
            assert result['cpu_percent'] == 25.0
            assert result['memory_percent'] == 50.0
            assert result['disk_percent'] == 30.0


class TestTaskScheduler:
    """Test the TaskScheduler class and its functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.scheduler = TaskScheduler()
    
    def test_parse_natural_time_minutes(self):
        """Test parsing natural language time for minutes."""
        # Test "in X minutes"
        result = self.scheduler.parse_natural_time("in 5 minutes")
        assert isinstance(result, timedelta)
        assert result.total_seconds() == 300  # 5 minutes
        
        # Test "every X minutes"
        result = self.scheduler.parse_natural_time("every 10 minutes")
        assert isinstance(result, celery_timedelta)
        assert result.total_seconds() == 600  # 10 minutes
    
    def test_parse_natural_time_seconds(self):
        """Test parsing natural language time for seconds."""
        # Test "in X seconds"
        result = self.scheduler.parse_natural_time("in 30 seconds")
        assert isinstance(result, timedelta)
        assert result.total_seconds() == 30
        
        # Test "every X seconds"
        result = self.scheduler.parse_natural_time("every 10 seconds")
        assert isinstance(result, celery_timedelta)
        assert result.total_seconds() == 10
        
        # Test "every X secs"
        result = self.scheduler.parse_natural_time("every 5 secs")
        assert isinstance(result, celery_timedelta)
        assert result.total_seconds() == 5

    def test_parse_natural_time_hours(self):
        """Test parsing natural language time for hours."""
        # Test "in X hours"
        result = self.scheduler.parse_natural_time("in 2 hours")
        assert isinstance(result, timedelta)
        assert result.total_seconds() == 7200  # 2 hours
        
        # Test "every X hours"
        result = self.scheduler.parse_natural_time("every 3 hours")
        assert isinstance(result, celery_timedelta)
        assert result.total_seconds() == 10800  # 3 hours
    
    def test_parse_natural_time_days(self):
        """Test parsing natural language time for days."""
        # Test "every day at X"
        result = self.scheduler.parse_natural_time("every day at 2pm")
        assert isinstance(result, crontab)
        assert 14 in result.hour  # 2pm in 24-hour format
        assert 0 in result.minute
    
    def test_parse_natural_time_cron(self):
        """Test parsing cron-like expressions."""
        result = self.scheduler.parse_natural_time("0 2 * * *")
        assert isinstance(result, crontab)
        assert 2 in result.hour
        assert 0 in result.minute
    
    def test_parse_natural_time_specific_datetime(self):
        """Test parsing specific datetime strings."""
        result = self.scheduler.parse_natural_time("2024-12-01 14:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 1
        assert result.hour == 14
        assert result.minute == 30
    
    def test_schedule_task(self, tmp_path):
        """Test scheduling a task."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear existing schedule
        clear_beat_schedule()
        
        # Schedule a task
        task_id = self.scheduler.schedule_task(
            "nagatha.system.health_check",
            "every 5 minutes"
        )
        
        # Verify task was scheduled
        assert task_id is not None
        schedule = get_beat_schedule()
        assert task_id in schedule
        assert schedule[task_id]["task"] == "nagatha.system.health_check"
    
    def test_cancel_task(self, tmp_path):
        """Test canceling a scheduled task."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear and schedule a task
        clear_beat_schedule()
        task_id = self.scheduler.schedule_task(
            "nagatha.system.health_check",
            "every 5 minutes"
        )
        
        # Verify task exists
        assert task_id in get_beat_schedule()
        
        # Cancel the task
        result = self.scheduler.cancel_task(task_id)
        
        # Verify task was canceled
        assert result is True
        assert task_id not in get_beat_schedule()
    
    def test_cancel_nonexistent_task(self):
        """Test canceling a task that doesn't exist."""
        result = self.scheduler.cancel_task("nonexistent_task")
        assert result is False
    
    def test_clear_all_tasks(self, tmp_path):
        """Test clearing all scheduled tasks."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear and add multiple tasks
        clear_beat_schedule()
        self.scheduler.schedule_task("nagatha.system.health_check", "every 5 minutes")
        self.scheduler.schedule_task("nagatha.system.backup_database", "every day at 2am")
        
        # Verify tasks exist
        assert len(get_beat_schedule()) >= 2
        
        # Clear all tasks
        self.scheduler.clear_all_tasks()
        
        # Verify all tasks were cleared
        assert len(get_beat_schedule()) == 0


class TestSchedulerFunctions:
    """Test the scheduler utility functions."""
    
    def test_get_scheduler(self):
        """Test getting the global scheduler instance."""
        scheduler = get_scheduler()
        assert isinstance(scheduler, TaskScheduler)
    
    def test_schedule_task_function(self, tmp_path):
        """Test the schedule_task utility function."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear existing schedule
        clear_beat_schedule()
        
        # Schedule a task
        task_id = schedule_task("nagatha.system.health_check", "every 10 minutes")
        
        # Verify task was scheduled
        assert task_id is not None
        schedule = get_beat_schedule()
        assert task_id in schedule
    
    def test_schedule_one_time_function(self, tmp_path):
        """Test the schedule_one_time utility function."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear existing schedule
        clear_beat_schedule()
        
        # Schedule a one-time task
        future_time = datetime.now() + timedelta(minutes=5)
        task_id = schedule_one_time("nagatha.system.health_check", future_time)
        
        # Verify task was scheduled
        assert task_id is not None
        schedule = get_beat_schedule()
        assert task_id in schedule
    
    def test_schedule_recurring_function(self, tmp_path):
        """Test the schedule_recurring utility function."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear existing schedule
        clear_beat_schedule()
        
        # Schedule a recurring task
        task_id = schedule_recurring("nagatha.system.health_check", "every hour")
        
        # Verify task was scheduled
        assert task_id is not None
        schedule = get_beat_schedule()
        assert task_id in schedule
    
    def test_cancel_task_function(self, tmp_path):
        """Test the cancel_task utility function."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear and schedule a task
        clear_beat_schedule()
        task_id = schedule_task("nagatha.system.health_check", "every 5 minutes")
        
        # Cancel the task
        result = cancel_task(task_id)
        
        # Verify task was canceled
        assert result is True
        assert task_id not in get_beat_schedule()
    
    def test_list_scheduled_tasks_function(self, tmp_path):
        """Test the list_scheduled_tasks utility function."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Clear and add tasks
        clear_beat_schedule()
        schedule_task("nagatha.system.health_check", "every 5 minutes")
        schedule_task("nagatha.system.backup_database", "every day at 2am")
        
        # List tasks
        tasks = list_scheduled_tasks()
        
        # Verify tasks are listed
        assert isinstance(tasks, dict)
        assert len(tasks) >= 2
        
        # Verify task structure
        for task_id, task_info in tasks.items():
            assert 'task' in task_info
            assert 'schedule' in task_info


class TestTaskHistory:
    """Test task history recording and retrieval."""
    
    @pytest.mark.asyncio
    async def test_record_task_history(self):
        """Test recording task execution history."""
        from unittest.mock import Mock, patch
        
        # Mock the memory manager to avoid database dependencies
        mock_memory = Mock()
        mock_memory.get.return_value = []
        mock_memory.set.return_value = None
        
        with patch('nagatha_assistant.plugins.tasks.get_memory_manager', return_value=mock_memory):
            # Record a task history entry
            from nagatha_assistant.plugins.tasks import record_task_history
            
            await record_task_history(
                task_id="test_task_123",
                task_name="nagatha.system.health_check",
                status="completed",
                result={"status": "healthy"},
                duration=1.5,
                worker="test_worker"
            )
            
            # Verify memory.set was called with the correct data
            mock_memory.set.assert_called_once()
            call_args = mock_memory.set.call_args
            assert call_args[0][0] == 'system'  # section
            assert call_args[0][1] == 'task_history'  # key
            
            # Verify the history data
            history_data = call_args[0][2]  # value
            assert len(history_data) == 1
            entry = history_data[0]
            assert entry['task_id'] == "test_task_123"
            assert entry['task_name'] == "nagatha.system.health_check"
            assert entry['status'] == "completed"
            assert entry['result'] == {"status": "healthy"}
            assert entry['duration'] == 1.5
            assert entry['worker'] == "test_worker"
            assert 'timestamp' in entry
    
    @pytest.mark.asyncio
    async def test_history_limit_enforcement(self):
        """Test that history is limited to prevent memory bloat."""
        from unittest.mock import Mock, patch
        
        # Mock the memory manager to avoid database dependencies
        mock_memory = Mock()
        mock_memory.get.return_value = []
        mock_memory.set.return_value = None
        
        with patch('nagatha_assistant.plugins.tasks.get_memory_manager', return_value=mock_memory):
            from nagatha_assistant.plugins.tasks import record_task_history
            
            # Add more than 1000 entries
            for i in range(1005):
                await record_task_history(
                    task_id=f"task_{i}",
                    task_name="nagatha.system.health_check",
                    status="completed"
                )
            
            # Verify memory.set was called multiple times
            assert mock_memory.set.call_count >= 1000
            
            # Get the last call to verify the final history
            last_call_args = mock_memory.set.call_args
            history_data = last_call_args[0][2]  # value
            
            # Verify only last 1000 entries are kept
            assert len(history_data) == 1000
            assert history_data[0]['task_id'] == "task_5"  # First entry should be task_5
            assert history_data[-1]['task_id'] == "task_1004"  # Last entry should be task_1004


class TestEventIntegration:
    """Test integration with the event system."""
    
    def test_task_events_emitted(self):
        """Test that task events are properly emitted."""
        from unittest.mock import Mock, patch
        
        # Mock the event bus to avoid async issues
        mock_event_bus = Mock()
        mock_event_bus.publish_sync.return_value = None
        
        with patch('nagatha_assistant.core.scheduler.get_event_bus', return_value=mock_event_bus):
            # Schedule a task (should emit TASK_CREATED)
            scheduler = get_scheduler()
            task_id = scheduler.schedule_task("nagatha.system.health_check", "every 5 minutes")
            
            # Verify TASK_CREATED event was emitted
            mock_event_bus.publish_sync.assert_called()
            call_args = mock_event_bus.publish_sync.call_args_list
            
            # Find the TASK_CREATED event
            created_event = None
            for call in call_args:
                event = call[0][0]  # First argument is the event
                if event.event_type == StandardEventTypes.TASK_CREATED:
                    created_event = event
                    break
            
            assert created_event is not None
            assert created_event.data['task_id'] == task_id
            assert created_event.data['task_name'] == "nagatha.system.health_check"
            
            # Cancel the task (should emit TASK_UPDATED)
            scheduler.cancel_task(task_id)
            
            # Verify TASK_UPDATED event was emitted
            call_args = mock_event_bus.publish_sync.call_args_list
            
            # Find the TASK_UPDATED event
            updated_event = None
            for call in call_args:
                event = call[0][0]  # First argument is the event
                if event.event_type == StandardEventTypes.TASK_UPDATED:
                    updated_event = event
                    break
            
            assert updated_event is not None
            assert updated_event.data['task_id'] == task_id
        assert updated_event.data['status'] == 'cancelled'


class TestCLIIntegration:
    """Test CLI command integration."""
    
    def test_celery_cli_group_exists(self):
        """Test that the celery CLI group is properly defined."""
        from nagatha_assistant.cli import cli
        
        # Check that celery group exists
        assert 'celery' in cli.list_commands(None)
        celery_group = cli.get_command(None, 'celery')
        assert celery_group is not None
    
    def test_service_commands_exist(self):
        """Test that service management commands exist."""
        from nagatha_assistant.cli import cli
        
        # Find celery group
        celery_group = cli.get_command(None, 'celery')
        assert celery_group is not None
        
        # Check for service subcommands
        assert 'service' in celery_group.list_commands(None)
        service_command = celery_group.get_command(None, 'service')
        assert service_command is not None
        
        # Check for service subcommands
        service_subcommands = service_command.list_commands(None)
        assert 'start' in service_subcommands
        assert 'stop' in service_subcommands
        assert 'status' in service_subcommands
    
    def test_task_commands_exist(self):
        """Test that task management commands exist."""
        from nagatha_assistant.cli import cli
        
        # Find celery group
        celery_group = cli.get_command(None, 'celery')
        assert celery_group is not None
        
        # Check for task subcommands
        assert 'task' in celery_group.list_commands(None)
        task_command = celery_group.get_command(None, 'task')
        assert task_command is not None
        
        # Check for task subcommands
        task_subcommands = task_command.list_commands(None)
        assert 'schedule' in task_subcommands
        assert 'list' in task_subcommands
        assert 'cancel' in task_subcommands
        assert 'clear' in task_subcommands
        assert 'history' in task_subcommands
        assert 'clear-history' in task_subcommands
        assert 'available' in task_subcommands
        assert 'reload' in task_subcommands


class TestTaskPlugins:
    """Test task plugin functionality."""
    
    def test_task_registry(self):
        """Test that tasks are properly registered."""
        from nagatha_assistant.plugins.tasks import TASK_REGISTRY
        
        # Check that expected tasks are registered
        expected_tasks = [
            'system.health_check',
            'system.backup_database',
            'system.cleanup_logs',
            'system.execute_command',
            'memory.backup',
            'memory.cleanup',
            'notification.send'
        ]
        
        for task_name in expected_tasks:
            assert task_name in TASK_REGISTRY
            assert callable(TASK_REGISTRY[task_name])
    
    def test_task_manager_plugin(self):
        """Test the TaskManagerPlugin."""
        from nagatha_assistant.plugins.task_manager import TaskManagerPlugin
        from nagatha_assistant.core.plugin import PluginConfig
        
        # Create plugin config
        config = PluginConfig(
            name="task_manager",
            enabled=True,
            config={}
        )
        
        # Create plugin instance
        plugin = TaskManagerPlugin(config)
        
        # Verify plugin properties
        assert plugin.PLUGIN_NAME == "Task Manager"
        assert plugin.PLUGIN_VERSION == "1.0.0"
        assert "Manage scheduled tasks" in plugin.PLUGIN_DESCRIPTION
        
        # Verify plugin has scheduler
        assert hasattr(plugin, 'scheduler')
        assert isinstance(plugin.scheduler, TaskScheduler)


class TestPersistence:
    """Test persistence of scheduled tasks."""
    
    def test_schedule_persistence(self, tmp_path):
        """Test that scheduled tasks persist across application restarts."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Update Celery app configuration to use the new schedule file
        from nagatha_assistant.core.celery_app import celery_app
        celery_app.conf.beat_schedule_filename = str(schedule_file)
        
        # Clear existing schedule
        clear_beat_schedule()
        
        # Add a task
        add_periodic_task(
            "persistent_task",
            "nagatha.system.health_check",
            celery_timedelta(minutes=5)
        )
        
        # Verify task is in memory
        assert "persistent_task" in celery_app.conf.beat_schedule
        
        # Simulate application restart by clearing in-memory schedule
        celery_app.conf.beat_schedule.clear()
        
        # Reload schedule from file
        initialize_celery()
        
        # Verify task was restored
        assert "persistent_task" in celery_app.conf.beat_schedule
        task_config = celery_app.conf.beat_schedule["persistent_task"]
        assert task_config["task"] == "nagatha.system.health_check"
    
    def test_schedule_file_format(self, tmp_path):
        """Test that schedule file is properly formatted."""
        # Set up temporary schedule file
        schedule_file = tmp_path / "test_schedule.json"
        os.environ['CELERY_BEAT_SCHEDULE_FILE'] = str(schedule_file)
        
        # Update Celery app configuration to use the new schedule file
        from nagatha_assistant.core.celery_app import celery_app
        celery_app.conf.beat_schedule_filename = str(schedule_file)
        
        # Clear and add a task
        clear_beat_schedule()
        add_periodic_task(
            "test_task",
            "nagatha.system.health_check",
            celery_timedelta(minutes=5)
        )
        
        # Check that file was created
        assert schedule_file.exists()
        
        # Read and verify file content
        with open(schedule_file, 'r') as f:
            data = json.load(f)
        
        assert "test_task" in data
        assert data["test_task"]["task"] == "nagatha.system.health_check"
        assert "schedule" in data["test_task"]


if __name__ == "__main__":
    pytest.main([__file__]) 