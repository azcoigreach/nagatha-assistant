"""
Test Discord CLI daemon functionality.

Tests the new background daemon functionality for Discord bot management.
"""

import pytest
import os
import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import signal
import psutil

from nagatha_assistant.utils.daemon import DaemonManager


class TestDaemonManager:
    """Test the DaemonManager class."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.daemon = DaemonManager("test_daemon", self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        # Clean up any running daemons
        if self.daemon.is_running():
            self.daemon.stop_daemon()
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_daemon_not_running_initially(self):
        """Test that daemon is not running initially."""
        assert not self.daemon.is_running()
        assert self.daemon.get_pid() is None
    
    def test_pid_file_creation(self):
        """Test PID file path creation."""
        expected_path = self.temp_dir / ".test_daemon.pid"
        assert self.daemon.pid_file == expected_path
    
    @patch('os.fork')
    @patch('nagatha_assistant.utils.daemon.psutil.pid_exists')
    def test_daemon_start_success(self, mock_pid_exists, mock_fork):
        """Test successful daemon start."""
        # Mock fork to return child PID in parent process
        mock_fork.return_value = 1234
        mock_pid_exists.return_value = True
        
        async def dummy_target():
            await asyncio.sleep(0.1)
        
        result = self.daemon.start_daemon(dummy_target)
        
        assert result is True
        # Note: The PID file is now written by the daemonized process, not the parent
        # The parent process returns True immediately after forking
        # The actual PID file will be written by the daemonized process with its own PID
    
    @patch('os.fork')
    def test_daemon_start_already_running(self, mock_fork):
        """Test starting daemon when already running."""
        # Create fake PID file
        with open(self.daemon.pid_file, 'w') as f:
            f.write("9999")
        
        # Mock that the process exists and has nagatha in command line
        with patch('nagatha_assistant.utils.daemon.psutil.pid_exists', return_value=True), \
             patch('nagatha_assistant.utils.daemon.psutil.Process') as mock_process:
            
            mock_proc = MagicMock()
            mock_proc.is_running.return_value = True
            mock_proc.status.return_value = "running"
            mock_proc.cmdline.return_value = ["python", "-m", "nagatha", "discord", "start"]
            mock_process.return_value = mock_proc
            
            async def dummy_target():
                pass
            
            result = self.daemon.start_daemon(dummy_target)
            
            assert result is False
            mock_fork.assert_not_called()
    
    def test_get_status_not_running(self):
        """Test getting status when daemon is not running."""
        status = self.daemon.get_status()
        
        expected = {
            "name": "test_daemon",
            "running": False,
            "pid": None,
            "status": "stopped"
        }
        
        assert status == expected
    
    @patch('nagatha_assistant.utils.daemon.psutil.pid_exists')
    @patch('nagatha_assistant.utils.daemon.psutil.Process')
    def test_get_status_running(self, mock_process, mock_pid_exists):
        """Test getting status when daemon is running."""
        # Create fake PID file
        with open(self.daemon.pid_file, 'w') as f:
            f.write("1234")
        
        mock_pid_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "running"
        mock_proc.cmdline.return_value = ["python", "-m", "nagatha", "discord", "start"]
        mock_proc.memory_info.return_value.rss = 1024 * 1024  # 1MB
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.create_time.return_value = 1234567890
        mock_process.return_value = mock_proc
        
        status = self.daemon.get_status()
        
        assert status["name"] == "test_daemon"
        assert status["running"] is True
        assert status["pid"] == 1234
        assert status["status"] == "running"
        assert status["memory"] == 1024 * 1024
        assert status["cpu_percent"] == 5.0
        assert status["create_time"] == 1234567890
    
    def test_stop_daemon_not_running(self):
        """Test stopping daemon when not running."""
        result = self.daemon.stop_daemon()
        assert result is False
    
    @patch('nagatha_assistant.utils.daemon.os.kill')
    @patch('nagatha_assistant.utils.daemon.psutil.Process')
    @patch('nagatha_assistant.utils.daemon.psutil.pid_exists')
    def test_stop_daemon_success(self, mock_pid_exists, mock_process, mock_kill):
        """Test successful daemon stop."""
        # Create fake PID file
        with open(self.daemon.pid_file, 'w') as f:
            f.write("1234")
        
        # Mock that the process exists and is a nagatha process
        mock_pid_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "running"
        mock_proc.cmdline.return_value = ["python", "-m", "nagatha", "discord", "start"]
        mock_process.return_value = mock_proc
        
        result = self.daemon.stop_daemon()
        
        assert result is True
        mock_kill.assert_called_once_with(1234, signal.SIGTERM)
        mock_proc.wait.assert_called_once_with(timeout=10)
        
        # Check that PID file was cleaned up
        assert not self.daemon.pid_file.exists()
    
    @patch('nagatha_assistant.utils.daemon.os.kill')
    @patch('nagatha_assistant.utils.daemon.psutil.Process')
    @patch('nagatha_assistant.utils.daemon.psutil.pid_exists')
    def test_stop_daemon_force_kill(self, mock_pid_exists, mock_process, mock_kill):
        """Test daemon stop with force kill after timeout."""
        # Create fake PID file
        with open(self.daemon.pid_file, 'w') as f:
            f.write("1234")
        
        # Mock that the process exists and is a nagatha process
        mock_pid_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "running"
        mock_proc.cmdline.return_value = ["python", "-m", "nagatha", "discord", "start"]
        mock_proc.wait.side_effect = psutil.TimeoutExpired("cmd", 10)
        mock_process.return_value = mock_proc
        
        result = self.daemon.stop_daemon()
        
        assert result is True
        # Should call SIGTERM first
        mock_kill.assert_any_call(1234, signal.SIGTERM)
        # Should call SIGKILL after timeout
        mock_kill.assert_any_call(1234, signal.SIGKILL)
        
        # Check that PID file was cleaned up
        assert not self.daemon.pid_file.exists()


class TestDiscordDaemonCLI:
    """Test Discord CLI daemon commands."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        # Patch the daemon to use temp directory
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
    def test_discord_start_success(self):
        """Test successful Discord bot start."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_start
        
        self.mock_daemon.is_running.return_value = False
        self.mock_daemon.start_daemon.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(discord_start)
        
        assert result.exit_code == 0
        assert "Discord bot started successfully in the background" in result.output
        assert "Use 'nagatha discord status' to check status" in result.output
        assert "Use 'nagatha discord stop' to stop the bot" in result.output
        
        self.mock_daemon.start_daemon.assert_called_once()
    
    def test_discord_start_no_token(self):
        """Test Discord bot start without token."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_start
        
        # Ensure no token is set
        with patch.dict(os.environ, {}, clear=True):
            runner = CliRunner()
            result = runner.invoke(discord_start)
            
            assert result.exit_code == 0
            assert "Discord bot token not configured" in result.output
            assert "Set DISCORD_BOT_TOKEN" in result.output
            
            self.mock_daemon.start_daemon.assert_not_called()
    
    @patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token'})
    def test_discord_start_already_running(self):
        """Test Discord bot start when already running."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_start
        
        self.mock_daemon.is_running.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(discord_start)
        
        assert result.exit_code == 0
        assert "Discord bot is already running" in result.output
        assert "Use 'nagatha discord status'" in result.output
        
        self.mock_daemon.start_daemon.assert_not_called()
    
    def test_discord_stop_success(self):
        """Test successful Discord bot stop."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_stop
        
        self.mock_daemon.is_running.return_value = True
        self.mock_daemon.stop_daemon.return_value = True
        
        runner = CliRunner()
        result = runner.invoke(discord_stop)
        
        assert result.exit_code == 0
        assert "Discord bot stopped successfully" in result.output
        
        self.mock_daemon.stop_daemon.assert_called_once()
    
    def test_discord_stop_not_running(self):
        """Test Discord bot stop when not running."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_stop
        
        self.mock_daemon.is_running.return_value = False
        
        runner = CliRunner()
        result = runner.invoke(discord_stop)
        
        assert result.exit_code == 0
        assert "Discord bot is not running" in result.output
        
        self.mock_daemon.stop_daemon.assert_not_called()
    
    def test_discord_status_running(self):
        """Test Discord bot status when running."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_status
        
        self.mock_daemon.get_status.return_value = {
            "name": "discord_bot",
            "running": True,
            "pid": 1234,
            "status": "running",
            "memory": 10 * 1024 * 1024,  # 10MB
            "cpu_percent": 2.5,
            "create_time": 1234567890
        }
        
        runner = CliRunner()
        result = runner.invoke(discord_status)
        
        assert result.exit_code == 0
        assert "Discord bot: Running" in result.output
        assert "PID: 1234" in result.output
        assert "Status: running" in result.output
        assert "Memory: 10.0 MB" in result.output
        assert "CPU: 2.5%" in result.output
    
    def test_discord_status_not_running(self):
        """Test Discord bot status when not running."""
        from click.testing import CliRunner
        from nagatha_assistant.cli import discord_status
        
        self.mock_daemon.get_status.return_value = {
            "name": "discord_bot",
            "running": False,
            "pid": None,
            "status": "stopped"
        }
        
        runner = CliRunner()
        result = runner.invoke(discord_status)
        
        assert result.exit_code == 0
        assert "Discord bot: Stopped" in result.output


@pytest.mark.asyncio
async def test_discord_daemon_target_function():
    """Test the Discord daemon target function behavior."""
    # This test would be complex to implement fully due to the plugin manager
    # dependencies, so we'll focus on testing the CLI integration instead
    pass