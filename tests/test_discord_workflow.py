"""
Integration test for Discord CLI daemon workflow.

Tests the complete workflow of starting, checking status, and stopping
the Discord bot daemon via CLI commands.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from nagatha_assistant.cli import discord_start, discord_stop, discord_status


class TestDiscordDaemonWorkflow:
    """Test the complete Discord daemon CLI workflow."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runner = CliRunner()
        
        # Mock the daemon manager
        self.daemon_patcher = patch('nagatha_assistant.utils.daemon.DaemonManager')
        self.mock_daemon_class = self.daemon_patcher.start()
        self.mock_daemon = MagicMock()
        self.mock_daemon_class.return_value = self.mock_daemon
    
    def teardown_method(self):
        """Clean up test environment."""
        self.daemon_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token'})
    def test_complete_daemon_workflow(self):
        """Test the complete workflow: start -> status -> stop."""
        
        # Initially not running
        self.mock_daemon.is_running.return_value = False
        self.mock_daemon.get_status.return_value = {
            "name": "discord_bot",
            "running": False,
            "pid": None,
            "status": "stopped"
        }
        
        # Test initial status - should be stopped
        result = self.runner.invoke(discord_status)
        assert result.exit_code == 0
        assert "Discord bot: Stopped" in result.output
        
        # Test start - should succeed
        self.mock_daemon.start_daemon.return_value = True
        result = self.runner.invoke(discord_start)
        assert result.exit_code == 0
        assert "Discord bot started successfully in the background" in result.output
        assert "Use 'nagatha discord status' to check status" in result.output
        assert "Use 'nagatha discord stop' to stop the bot" in result.output
        
        # Simulate daemon now running
        self.mock_daemon.is_running.return_value = True
        self.mock_daemon.get_status.return_value = {
            "name": "discord_bot",
            "running": True,
            "pid": 1234,
            "status": "running",
            "memory": 50 * 1024 * 1024,  # 50MB
            "cpu_percent": 3.5,
            "create_time": 1234567890
        }
        
        # Test status while running
        result = self.runner.invoke(discord_status)
        assert result.exit_code == 0
        assert "Discord bot: Running" in result.output
        assert "PID: 1234" in result.output
        assert "Status: running" in result.output
        assert "Memory: 50.0 MB" in result.output
        assert "CPU: 3.5%" in result.output
        
        # Test trying to start again while running
        result = self.runner.invoke(discord_start)
        assert result.exit_code == 0
        assert "Discord bot is already running" in result.output
        assert "Use 'nagatha discord status'" in result.output
        
        # Test stop - should succeed
        self.mock_daemon.stop_daemon.return_value = True
        result = self.runner.invoke(discord_stop)
        assert result.exit_code == 0
        assert "Discord bot stopped successfully" in result.output
        
        # Simulate daemon now stopped
        self.mock_daemon.is_running.return_value = False
        self.mock_daemon.get_status.return_value = {
            "name": "discord_bot",
            "running": False,
            "pid": None,
            "status": "stopped"
        }
        
        # Test final status - should be stopped again
        result = self.runner.invoke(discord_status)
        assert result.exit_code == 0
        assert "Discord bot: Stopped" in result.output
        
        # Test trying to stop when already stopped
        result = self.runner.invoke(discord_stop)
        assert result.exit_code == 0
        assert "Discord bot is not running" in result.output
    
    def test_start_without_token(self):
        """Test starting without Discord token configured."""
        # Ensure no token is set
        with patch.dict(os.environ, {}, clear=True):
            result = self.runner.invoke(discord_start)
            assert result.exit_code == 0
            assert "Discord bot token not configured" in result.output
            assert "Set DISCORD_BOT_TOKEN" in result.output
            
            # Should not attempt to start daemon
            self.mock_daemon.start_daemon.assert_not_called()
    
    @patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token'})
    def test_start_daemon_failure(self):
        """Test handling daemon start failure."""
        self.mock_daemon.is_running.return_value = False
        self.mock_daemon.start_daemon.return_value = False
        
        result = self.runner.invoke(discord_start)
        assert result.exit_code == 0
        assert "Failed to start Discord bot daemon" in result.output
    
    def test_stop_daemon_failure(self):
        """Test handling daemon stop failure."""
        self.mock_daemon.is_running.return_value = True
        self.mock_daemon.stop_daemon.return_value = False
        
        result = self.runner.invoke(discord_stop)
        assert result.exit_code == 0
        assert "Failed to stop Discord bot" in result.output


def test_behavior_comparison():
    """Test that verifies the behavior change from blocking to non-blocking."""
    # This test documents the expected behavior change:
    # 
    # OLD BEHAVIOR:
    # - `nagatha discord start` would block with "Discord bot is now running. Press Ctrl+C to stop."
    # - User had to keep terminal open and use Ctrl+C to stop
    # - No way to check status or stop from another terminal
    #
    # NEW BEHAVIOR:  
    # - `nagatha discord start` returns immediately with success message
    # - Bot runs in background daemon process
    # - `nagatha discord status` shows detailed status
    # - `nagatha discord stop` cleanly terminates daemon
    # - User can close terminal and bot continues running
    
    runner = CliRunner()
    
    with patch('nagatha_assistant.utils.daemon.DaemonManager') as mock_daemon_class:
        mock_daemon = MagicMock()
        mock_daemon_class.return_value = mock_daemon
        mock_daemon.is_running.return_value = False
        mock_daemon.start_daemon.return_value = True
        
        with patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token'}):
            result = runner.invoke(discord_start)
            
            # NEW: Command returns immediately (exit_code 0)
            assert result.exit_code == 0
            
            # NEW: Returns with success message instead of blocking
            assert "Discord bot started successfully in the background" in result.output
            
            # NEW: Provides guidance for management commands
            assert "Use 'nagatha discord status' to check status" in result.output
            assert "Use 'nagatha discord stop' to stop the bot" in result.output
            
            # NEW: No blocking message like "Press Ctrl+C to stop"
            assert "Press Ctrl+C to stop" not in result.output
            assert "Discord bot is now running" not in result.output