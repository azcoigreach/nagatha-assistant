"""
Tests for the Discord bot plugin.

This module tests the Discord bot integration for Nagatha Assistant.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os

from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin, NagathaDiscordBot, PLUGIN_CONFIG
from nagatha_assistant.core.plugin import PluginConfig


class TestDiscordBotPlugin:
    """Test cases for the Discord bot plugin."""
    
    @pytest.fixture
    def plugin_config(self):
        """Create a test plugin configuration."""
        return PluginConfig(
            name="discord_bot",
            version="1.0.0",
            description="Test Discord bot plugin",
            config={"auto_start": False, "command_prefix": "!"}
        )
    
    @pytest.fixture
    def discord_plugin(self, plugin_config):
        """Create a Discord bot plugin instance for testing."""
        with patch.dict(os.environ, {
            'DISCORD_BOT_TOKEN': 'test_token',
            'DISCORD_COMMAND_PREFIX': '!'
        }):
            return DiscordBotPlugin(plugin_config)
    
    def test_plugin_initialization(self, discord_plugin):
        """Test that the plugin initializes correctly."""
        assert discord_plugin.name == "discord_bot"
        assert discord_plugin.version == "1.0.0"
        assert discord_plugin.token == "test_token"
        assert discord_plugin.command_prefix == "!"
        assert not discord_plugin.is_running
        assert discord_plugin.bot is None
    
    def test_plugin_config_validation(self):
        """Test plugin configuration validation."""
        assert PLUGIN_CONFIG["name"] == "discord_bot"
        assert PLUGIN_CONFIG["version"] == "1.0.0"
        assert PLUGIN_CONFIG["enabled"] is True
        assert "discord.py" in PLUGIN_CONFIG["dependencies"]
    
    @pytest.mark.asyncio
    async def test_setup_without_token(self):
        """Test setup behavior when Discord token is not configured."""
        config = PluginConfig(name="discord_bot", version="1.0.0")
        
        with patch.dict(os.environ, {}, clear=True):
            plugin = DiscordBotPlugin(config)
            
            # Mock the plugin manager
            with patch('nagatha_assistant.core.plugin_manager.get_plugin_manager') as mock_manager:
                mock_manager.return_value.register_command = MagicMock()
                
                await plugin.setup()
                
                # Should still register commands but warn about missing token
                assert mock_manager.return_value.register_command.call_count == 3
    
    @pytest.mark.asyncio
    async def test_setup_with_token(self, discord_plugin):
        """Test setup behavior when Discord token is configured."""
        with patch('nagatha_assistant.core.plugin_manager.get_plugin_manager') as mock_manager:
            mock_manager.return_value.register_command = MagicMock()
            
            await discord_plugin.setup()
            
            # Should register all commands
            assert mock_manager.return_value.register_command.call_count == 3
    
    @pytest.mark.asyncio
    async def test_start_discord_bot_no_token(self):
        """Test starting the bot without a token."""
        config = PluginConfig(name="discord_bot", version="1.0.0")
        
        with patch.dict(os.environ, {}, clear=True):
            plugin = DiscordBotPlugin(config)
            result = await plugin.start_discord_bot()
            
            assert "token not configured" in result
            assert not plugin.is_running
    
    @pytest.mark.asyncio
    async def test_start_discord_bot_already_running(self, discord_plugin):
        """Test starting the bot when it's already running."""
        discord_plugin.is_running = True
        
        result = await discord_plugin.start_discord_bot()
        
        assert "already running" in result
    
    @pytest.mark.asyncio
    async def test_stop_discord_bot_not_running(self, discord_plugin):
        """Test stopping the bot when it's not running."""
        result = await discord_plugin.stop_discord_bot()
        
        assert "not running" in result
    
    @pytest.mark.asyncio 
    async def test_get_discord_status_no_token(self):
        """Test getting status when no token is configured."""
        config = PluginConfig(name="discord_bot", version="1.0.0")
        
        with patch.dict(os.environ, {}, clear=True):
            plugin = DiscordBotPlugin(config)
            result = await plugin.get_discord_status()
            
            assert "Not configured" in result
    
    @pytest.mark.asyncio
    async def test_get_discord_status_stopped(self, discord_plugin):
        """Test getting status when bot is stopped."""
        result = await discord_plugin.get_discord_status()
        
        assert "Stopped" in result
    
    @pytest.mark.asyncio
    async def test_get_discord_status_running(self, discord_plugin):
        """Test getting status when bot is running."""
        discord_plugin.is_running = True
        
        # Mock a bot with user info
        mock_bot = MagicMock()
        mock_bot.user.name = "TestBot"
        mock_bot.guilds = [MagicMock(), MagicMock()]  # 2 guilds
        discord_plugin.bot = mock_bot
        
        result = await discord_plugin.get_discord_status()
        
        assert "Running as TestBot" in result
        assert "2 servers" in result
    
    @pytest.mark.asyncio
    async def test_teardown(self, discord_plugin):
        """Test plugin teardown."""
        discord_plugin.is_running = True
        discord_plugin.stop_discord_bot = AsyncMock(return_value="stopped")
        
        await discord_plugin.teardown()
        
        discord_plugin.stop_discord_bot.assert_called_once()


class TestNagathaDiscordBot:
    """Test cases for the custom Discord bot class."""
    
    @pytest.fixture
    def mock_discord_plugin(self):
        """Create a mock Discord plugin."""
        plugin = MagicMock()
        plugin.publish_event = AsyncMock()
        return plugin
    
    def test_bot_initialization(self, mock_discord_plugin):
        """Test that the Discord bot initializes correctly."""
        with patch('discord.ext.commands.Bot.__init__'):
            bot = NagathaDiscordBot(mock_discord_plugin, command_prefix="!")
            
            assert bot.discord_plugin is mock_discord_plugin
    
    @pytest.mark.asyncio
    async def test_event_publishing_methods(self, mock_discord_plugin):
        """Test that event publishing methods work correctly."""
        with patch('discord.ext.commands.Bot.__init__'):
            bot = NagathaDiscordBot(mock_discord_plugin, command_prefix="!")
            
            # Test on_disconnect
            await bot.on_disconnect()
            mock_discord_plugin.publish_event.assert_called()
            
            # Reset mock for next test
            mock_discord_plugin.publish_event.reset_mock()
            
            # Test on_error  
            await bot.on_error("test_event", "arg1", "arg2")
            mock_discord_plugin.publish_event.assert_called()
            
            # Verify the error event was published correctly
            event = mock_discord_plugin.publish_event.call_args[0][0]
            assert event.event_type == "discord.bot.error"
            assert event.data["event_name"] == "test_event"


class TestDiscordCLIIntegration:
    """Test cases for Discord CLI command integration."""
    
    def test_plugin_config_structure(self):
        """Test that the plugin config follows the expected structure."""
        config = PLUGIN_CONFIG
        
        required_fields = ["name", "version", "description", "author", "dependencies", "config", "enabled", "priority"]
        
        for field in required_fields:
            assert field in config, f"Missing required field: {field}"
        
        assert config["name"] == "discord_bot"
        assert isinstance(config["enabled"], bool)
        assert isinstance(config["priority"], int)
        assert isinstance(config["dependencies"], list)
        assert isinstance(config["config"], dict)