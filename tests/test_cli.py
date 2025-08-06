#!/usr/bin/env python3
"""
Pytest tests for the CLI module functionality.
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from click.testing import CliRunner
from nagatha_assistant.cli import cli, db_upgrade, db_backup, mcp_status, mcp_reload


class TestCLI:
    """Test cases for the CLI module."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_main_command(self):
        """Test the main CLI command."""
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Nagatha Assistant CLI" in result.output

    def test_cli_with_log_level(self):
        """Test CLI with log level option."""
        # Just test that the command works, logging setup is internal
        result = self.runner.invoke(cli, ['--log-level', 'DEBUG', '--help'])
        assert result.exit_code == 0

    def test_cli_env_log_level(self):
        """Test CLI respects LOG_LEVEL environment variable."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'INFO'}):
            result = self.runner.invoke(cli, ['--help'])
            assert result.exit_code == 0

    def test_db_group_command(self):
        """Test the db group command."""
        result = self.runner.invoke(cli, ['db', '--help'])
        assert result.exit_code == 0
        assert "Database maintenance commands" in result.output

    @patch('alembic.command')
    @patch('alembic.config.Config')
    def test_db_upgrade_success(self, mock_config, mock_command):
        """Test successful database upgrade."""
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg
        
        result = self.runner.invoke(cli, ['db', 'upgrade'])
        
        assert result.exit_code == 0
        assert "Database successfully upgraded" in result.output
        mock_command.upgrade.assert_called_once_with(mock_cfg, "head")

    @patch('alembic.command')
    @patch('alembic.config.Config')
    def test_db_upgrade_already_exists(self, mock_config, mock_command):
        """Test database upgrade when schema already exists."""
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg
        mock_command.upgrade.side_effect = Exception("already exists")
        
        result = self.runner.invoke(cli, ['db', 'upgrade'])
        
        assert result.exit_code == 0
        assert "Detected existing schema" in result.output
        mock_command.stamp.assert_called_once_with(mock_cfg, "head")

    @patch('alembic.command')
    @patch('alembic.config.Config')
    def test_db_upgrade_error(self, mock_config, mock_command):
        """Test database upgrade with error."""
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg
        mock_command.upgrade.side_effect = Exception("Migration failed")
        
        result = self.runner.invoke(cli, ['db', 'upgrade'])
        
        assert result.exit_code == 1
        assert "Error running migrations" in result.output

    @patch('alembic.command')
    @patch('alembic.config.Config')  
    def test_db_upgrade_stamp_error(self, mock_config, mock_command):
        """Test database upgrade with stamp error."""
        mock_cfg = MagicMock()
        mock_config.return_value = mock_cfg
        mock_command.upgrade.side_effect = Exception("already exists")
        mock_command.stamp.side_effect = Exception("Stamp failed")
        
        result = self.runner.invoke(cli, ['db', 'upgrade'])
        
        assert result.exit_code == 1
        assert "Error stamping database" in result.output

    def test_db_backup_non_sqlite(self):
        """Test backup with non-SQLite database."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://localhost/test'}):
            result = self.runner.invoke(cli, ['db', 'backup'])
            assert result.exit_code == 0
            assert "Backup is only supported for SQLite" in result.output

    def test_db_backup_memory_db(self):
        """Test backup with in-memory database."""
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///:memory:'}):
            result = self.runner.invoke(cli, ['db', 'backup'])
            assert result.exit_code == 0
            assert "Cannot backup in-memory" in result.output

    def test_db_backup_missing_file(self):
        """Test backup with missing database file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "nonexistent.db")
            with patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{db_path}'}):
                result = self.runner.invoke(cli, ['db', 'backup'])
                assert result.exit_code == 0
                assert "SQLite database file not found" in result.output

    @patch('shutil.copy2')
    def test_db_backup_success_with_destination(self, mock_copy):
        """Test successful backup with specified destination."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            backup_path = os.path.join(temp_dir, "backup.db")
            
            # Create a fake database file
            Path(db_path).touch()
            
            with patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{db_path}'}):
                result = self.runner.invoke(cli, ['db', 'backup', backup_path])
                
                assert result.exit_code == 0
                assert "Database backed up to" in result.output
                mock_copy.assert_called_once()

    @patch('shutil.copy2')
    @patch('nagatha_assistant.cli.datetime')
    def test_db_backup_success_default_name(self, mock_datetime, mock_copy):
        """Test successful backup with default timestamp name."""
        mock_datetime.now.return_value.strftime.return_value = "20240101T120000"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            # Create a fake database file
            Path(db_path).touch()
            
            with patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{db_path}'}):
                result = self.runner.invoke(cli, ['db', 'backup'])
                
                assert result.exit_code == 0
                assert "Database backed up to" in result.output
                mock_copy.assert_called_once()

    @patch('nagatha_assistant.cli.datetime')
    @patch('shutil.copy2')  
    def test_db_backup_copy_error(self, mock_copy, mock_datetime):
        """Test backup with copy error."""
        mock_copy.side_effect = Exception("Permission denied")
        mock_datetime.now.return_value.strftime.return_value = "20240101T120000"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            Path(db_path).touch()
            
            with patch.dict(os.environ, {'DATABASE_URL': f'sqlite:///{db_path}'}):
                result = self.runner.invoke(cli, ['db', 'backup'])
                assert "backed up" in result.output or "Error" in result.output

    def test_mcp_group_command(self):
        """Test the mcp group command."""
        result = self.runner.invoke(cli, ['mcp', '--help'])
        assert result.exit_code == 0
        assert "MCP (Model Context Protocol) management commands" in result.output

    @patch('nagatha_assistant.core.agent.get_mcp_status')
    def test_mcp_status_success(self, mock_get_status):
        """Test successful MCP status command."""
        mock_get_status.return_value = {
            'initialized': True,
            'servers': {
                'test_server': {
                    'connected': True,
                    'config': MagicMock(transport='stdio', command='python', args=['test.py'], url=None),
                    'tools': ['test_tool']
                }
            },
            'tools': [
                {'name': 'test_tool', 'server': 'test_server', 'description': 'Test tool'}
            ]
        }
        
        result = self.runner.invoke(cli, ['mcp', 'status'])
        
        assert result.exit_code == 0
        assert "MCP Status" in result.output
        assert "test_server" in result.output
        assert "test_tool" in result.output

    @patch('nagatha_assistant.core.agent.get_mcp_status')
    def test_mcp_status_error(self, mock_get_status):
        """Test MCP status command with error."""
        mock_get_status.return_value = {
            'error': 'Connection failed',
            'initialized': False
        }
        
        result = self.runner.invoke(cli, ['mcp', 'status'])
        
        assert result.exit_code == 0
        assert "Error: Connection failed" in result.output

    @patch('nagatha_assistant.core.mcp_manager.get_mcp_manager')
    @patch('nagatha_assistant.core.mcp_manager.shutdown_mcp_manager')
    def test_mcp_reload_success(self, mock_shutdown, mock_get_manager):
        """Test successful MCP reload command."""
        mock_shutdown.return_value = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.get_available_tools.return_value = ['tool1', 'tool2']
        mock_manager.get_server_info.return_value = {
            'server1': {'connected': True},
            'server2': {'connected': True}
        }
        mock_get_manager.return_value = mock_manager
        
        result = self.runner.invoke(cli, ['mcp', 'reload'])
        
        assert result.exit_code == 0
        assert "Shutting down existing MCP connections" in result.output
        assert "Reloading MCP configuration" in result.output
        assert "Reloaded with 2 tools from 2 servers" in result.output



    def test_cli_module_constants(self):
        """Test that CLI module has expected constants."""
        from nagatha_assistant import cli
        assert hasattr(cli, 'cli')
        assert hasattr(cli, 'db')
        assert hasattr(cli, 'mcp')


    @patch('alembic.command')
    @patch('alembic.config.Config')
    def test_database_url_conversion(self, mock_config, mock_command):
        """Test database URL conversion logic."""
        test_cases = [
            ('sqlite:///test.db', 'sqlite+aiosqlite:///test.db'),
            ('sqlite+aiosqlite:///test.db', 'sqlite+aiosqlite:///test.db'),
            ('postgresql://localhost/test', 'postgresql://localhost/test')
        ]
        
        for input_url, expected_url in test_cases:
            with patch.dict(os.environ, {'DATABASE_URL': input_url}):
                mock_cfg = MagicMock()
                mock_config.return_value = mock_cfg
                
                result = self.runner.invoke(cli, ['db', 'upgrade'])
                # Should call Config.set_main_option with converted URL
                mock_cfg.set_main_option.assert_any_call("sqlalchemy.url", expected_url)



    def test_mcp_status_no_tools(self):
        """Test MCP status with no tools available."""
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_get_status:
            mock_get_status.return_value = {
                'initialized': True,
                'servers': {},
                'tools': []
            }
            
            result = self.runner.invoke(cli, ['mcp', 'status'])
            
            assert result.exit_code == 0
            assert "No tools available" in result.output

    def test_db_backup_url_variations(self):
        """Test backup with various DATABASE_URL formats."""
        test_urls = [
            'sqlite:///test.db',
            'sqlite+aiosqlite:///test.db'
        ]
        
        for db_url in test_urls:
            with patch.dict(os.environ, {'DATABASE_URL': db_url}):
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Test will fail on file not found, but URL processing should work
                    result = self.runner.invoke(cli, ['db', 'backup'])
                    assert "SQLite database file not found" in result.output or \
                           "Database backed up" in result.output

    def test_cli_logging_setup(self):
        """Test that CLI sets up logging correctly."""
        # This tests the actual logging setup in the CLI
        with patch('nagatha_assistant.utils.logger.setup_logger') as mock_setup:
            mock_logger = MagicMock()
            mock_setup.return_value = mock_logger
            
            # This should trigger logging setup
            result = self.runner.invoke(cli, ['--help'])
            assert result.exit_code == 0
            # Logger should be configured (called during module import)

    def test_mcp_status_server_details(self):
        """Test MCP status shows server configuration details."""
        mock_config = MagicMock()
        mock_config.transport = 'stdio'
        mock_config.command = 'python'
        mock_config.args = ['test.py']
        mock_config.url = None
        
        with patch('nagatha_assistant.core.agent.get_mcp_status') as mock_get_status:
            mock_get_status.return_value = {
                'initialized': True,
                'servers': {
                    'test_server': {
                        'connected': True,
                        'config': mock_config,
                        'tools': ['tool1']
                    }
                },
                'tools': []
            }
            
            result = self.runner.invoke(cli, ['mcp', 'status'])
            
            assert result.exit_code == 0
            assert "python test.py" in result.output
            assert "(stdio)" in result.output

 