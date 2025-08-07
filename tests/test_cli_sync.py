"""
Tests for CLI sync command functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open
from click.testing import CliRunner

from nagatha_assistant.cli import cli


class TestCLISyncCommand:
    """Test the CLI sync command functionality."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI runner for testing."""
        return CliRunner()
    
    def test_sync_command_help(self, runner):
        """Test that sync command shows help."""
        result = runner.invoke(cli, ['discord', 'sync', '--help'])
        
        assert result.exit_code == 0
        assert "Sync Discord slash commands" in result.output
        assert "--guild-id" in result.output
    
    def test_sync_command_no_guild_id(self, runner):
        """Test sync command without guild ID."""
        with patch('nagatha_assistant.utils.daemon.DaemonManager') as mock_daemon_class, \
             patch('builtins.open', mock_open(read_data='{"running": true, "auto_discord": true}')) as mock_file:
            # Mock daemon manager
            mock_daemon = Mock()
            mock_daemon_class.return_value = mock_daemon
            
            # Mock status - bot is not running as daemon but is running with server
            mock_daemon.get_status.return_value = {"running": False}
            
            result = runner.invoke(cli, ['discord', 'sync'])
            
            # Should show guidance message
            assert "✅ Discord bot is running (with server)" in result.output
            assert "🔄 Syncing Discord slash commands" in result.output
            assert "To sync commands globally, use the Discord slash command:" in result.output
            assert "/sync" in result.output
    
    def test_sync_command_with_guild_id(self, runner):
        """Test sync command with guild ID."""
        with patch('nagatha_assistant.utils.daemon.DaemonManager') as mock_daemon_class, \
             patch('builtins.open', mock_open(read_data='{"running": true, "auto_discord": true}')) as mock_file:
            # Mock daemon manager
            mock_daemon = Mock()
            mock_daemon_class.return_value = mock_daemon
            
            # Mock status - bot is not running as daemon but is running with server
            mock_daemon.get_status.return_value = {"running": False}
            
            result = runner.invoke(cli, ['discord', 'sync', '--guild-id', '123456789'])
            
            # Should show guidance message with guild ID
            assert "✅ Discord bot is running (with server)" in result.output
            assert "🔄 Syncing Discord slash commands" in result.output
            assert "To sync commands to guild 123456789, use the Discord slash command:" in result.output
            assert "/sync" in result.output
    
    def test_sync_command_invalid_guild_id(self, runner):
        """Test sync command with invalid guild ID."""
        result = runner.invoke(cli, ['discord', 'sync', '--guild-id', 'invalid'])
        
        assert "❌ Invalid guild ID: invalid" in result.output
    
    def test_sync_command_bot_not_running(self, runner):
        """Test sync command when bot is not running."""
        with patch('nagatha_assistant.utils.daemon.DaemonManager') as mock_daemon_class, \
             patch('builtins.open', mock_open(read_data='{"running": false, "auto_discord": false}')) as mock_file:
            # Mock daemon manager
            mock_daemon = Mock()
            mock_daemon_class.return_value = mock_daemon
            
            # Mock status - bot is not running
            mock_daemon.get_status.return_value = {"running": False}
            
            result = runner.invoke(cli, ['discord', 'sync'])
            
            assert "❌ Discord bot is not running" in result.output
            assert "Start the bot with one of these methods:" in result.output


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"]) 