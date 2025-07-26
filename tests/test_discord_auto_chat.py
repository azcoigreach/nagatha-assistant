"""
Tests for the Discord auto-chat functionality.

This module tests the auto-chat feature that allows Nagatha to automatically
respond to messages in Discord channels without requiring slash commands.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import pytest_asyncio

from nagatha_assistant.plugins.discord_bot import (
    get_auto_chat_setting, 
    set_auto_chat_setting, 
    is_auto_chat_enabled,
    should_rate_limit,
    update_auto_chat_usage
)
from nagatha_assistant.db_models import DiscordAutoChat
from nagatha_assistant.db import SessionLocal


class TestDiscordAutoChat:
    """Test cases for Discord auto-chat functionality."""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_database(self):
        """Set up test database with tables."""
        # Create all tables for testing
        from nagatha_assistant.db import engine, Base
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield
        
        # Clean up after tests
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @pytest.mark.asyncio
    async def test_set_auto_chat_setting_new(self):
        """Test creating a new auto-chat setting."""
        channel_id = "123456789"
        guild_id = "987654321"
        user_id = "111222333"
        
        # Set auto-chat enabled
        setting = await set_auto_chat_setting(channel_id, guild_id, True, user_id)
        
        assert setting is not None
        assert setting.channel_id == channel_id
        assert setting.guild_id == guild_id
        assert setting.enabled is True
        assert setting.enabled_by_user_id == user_id
        assert setting.message_count == 0
    
    @pytest.mark.asyncio
    async def test_set_auto_chat_setting_update(self):
        """Test updating an existing auto-chat setting."""
        channel_id = "123456789"
        guild_id = "987654321"
        user_id = "111222333"
        
        # Create initial setting
        await set_auto_chat_setting(channel_id, guild_id, True, user_id)
        
        # Update to disabled
        updated_setting = await set_auto_chat_setting(channel_id, guild_id, False, user_id)
        
        assert updated_setting.enabled is False
        assert updated_setting.channel_id == channel_id
    
    @pytest.mark.asyncio
    async def test_get_auto_chat_setting(self):
        """Test retrieving auto-chat settings."""
        channel_id = "123456789"
        guild_id = "987654321"
        user_id = "111222333"
        
        # Should return None for non-existent setting
        setting = await get_auto_chat_setting(channel_id)
        assert setting is None
        
        # Create a setting
        await set_auto_chat_setting(channel_id, guild_id, True, user_id)
        
        # Should return the setting
        setting = await get_auto_chat_setting(channel_id)
        assert setting is not None
        assert setting.enabled is True
    
    @pytest.mark.asyncio
    async def test_is_auto_chat_enabled(self):
        """Test checking if auto-chat is enabled."""
        channel_id = "123456789"
        guild_id = "987654321"
        user_id = "111222333"
        
        # Should be disabled initially
        assert await is_auto_chat_enabled(channel_id) is False
        
        # Enable auto-chat
        await set_auto_chat_setting(channel_id, guild_id, True, user_id)
        assert await is_auto_chat_enabled(channel_id) is True
        
        # Disable auto-chat
        await set_auto_chat_setting(channel_id, guild_id, False, user_id)
        assert await is_auto_chat_enabled(channel_id) is False
    
    @pytest.mark.asyncio
    async def test_should_rate_limit(self):
        """Test rate limiting logic."""
        channel_id = "123456789"
        
        # Should rate limit if no setting exists
        assert await should_rate_limit(channel_id) is True
        
        # Create setting
        await set_auto_chat_setting(channel_id, None, True, "user123")
        
        # Should not rate limit initially
        assert await should_rate_limit(channel_id) is False
        
        # Update usage to trigger rate limit
        setting = await get_auto_chat_setting(channel_id)
        setting.message_count = 25  # Over the limit of 20
        setting.last_message_at = datetime.now()
        
        async with SessionLocal() as session:
            session.add(setting)
            await session.commit()
        
        # Should rate limit now
        assert await should_rate_limit(channel_id) is True
    
    @pytest.mark.asyncio
    async def test_update_auto_chat_usage(self):
        """Test updating auto-chat usage statistics."""
        channel_id = "123456789"
        
        # Create setting
        await set_auto_chat_setting(channel_id, None, True, "user123")
        
        # Initial count should be 0
        setting = await get_auto_chat_setting(channel_id)
        assert setting.message_count == 0
        
        # Update usage
        await update_auto_chat_usage(channel_id)
        
        # Count should be incremented
        setting = await get_auto_chat_setting(channel_id)
        assert setting.message_count == 1
        assert setting.last_message_at is not None


class TestDiscordBotAutoChat:
    """Test cases for Discord bot auto-chat integration."""
    
    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord message."""
        message = MagicMock()
        message.author = MagicMock()
        message.author.id = 123456789
        message.author.bot = False
        message.channel = MagicMock()
        message.channel.id = 987654321
        message.guild = MagicMock()
        message.guild.id = 111222333
        message.content = "Hello Nagatha!"
        message.type = 0  # discord.MessageType.default
        return message
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock()
        interaction.channel_id = 987654321
        interaction.guild_id = 111222333
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        interaction.user.guild_permissions = MagicMock()
        interaction.user.guild_permissions.manage_channels = True
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_auto_chat_command_status(self, mock_interaction):
        """Test the /auto-chat status command."""
        from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
        from nagatha_assistant.core.plugin import PluginConfig
        
        # Create plugin instance
        config = PluginConfig(name="discord_bot", version="1.0.0")
        plugin = DiscordBotPlugin(config)
        
        # Test status when disabled
        with patch('nagatha_assistant.plugins.discord_bot.get_auto_chat_setting', return_value=None):
            await plugin._handle_auto_chat_command(mock_interaction, "status")
            
            # Should indicate disabled
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args[0][0]
            assert "DISABLED" in call_args
    
    @pytest.mark.asyncio
    async def test_auto_chat_command_enable(self, mock_interaction):
        """Test the /auto-chat on command."""
        from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
        from nagatha_assistant.core.plugin import PluginConfig
        
        # Create plugin instance
        config = PluginConfig(name="discord_bot", version="1.0.0")
        plugin = DiscordBotPlugin(config)
        
        # Mock the setting function
        mock_setting = MagicMock()
        with patch('nagatha_assistant.plugins.discord_bot.set_auto_chat_setting', return_value=mock_setting):
            await plugin._handle_auto_chat_command(mock_interaction, "on")
            
            # Should indicate enabled
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args[0][0]
            assert "ENABLED" in call_args
    
    @pytest.mark.asyncio
    async def test_auto_chat_command_disable(self, mock_interaction):
        """Test the /auto-chat off command."""
        from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
        from nagatha_assistant.core.plugin import PluginConfig
        
        # Create plugin instance
        config = PluginConfig(name="discord_bot", version="1.0.0")
        plugin = DiscordBotPlugin(config)
        
        # Mock current setting
        mock_current_setting = MagicMock()
        mock_current_setting.enabled = True
        mock_current_setting.enabled_by_user_id = str(mock_interaction.user.id)
        
        with patch('nagatha_assistant.plugins.discord_bot.get_auto_chat_setting', return_value=mock_current_setting):
            with patch('nagatha_assistant.plugins.discord_bot.set_auto_chat_setting'):
                await plugin._handle_auto_chat_command(mock_interaction, "off")
                
                # Should indicate disabled
                mock_interaction.followup.send.assert_called_once()
                call_args = mock_interaction.followup.send.call_args[0][0]
                assert "DISABLED" in call_args
    
    @pytest.mark.asyncio
    async def test_auto_chat_permission_check(self, mock_interaction):
        """Test permission checking for auto-chat commands."""
        from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
        from nagatha_assistant.core.plugin import PluginConfig
        
        # Create plugin instance
        config = PluginConfig(name="discord_bot", version="1.0.0")
        plugin = DiscordBotPlugin(config)
        
        # Remove permissions
        mock_interaction.user.guild_permissions.manage_channels = False
        
        await plugin._handle_auto_chat_command(mock_interaction, "on")
        
        # Should be denied
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert call_args[1]['ephemeral'] is True  # Error should be ephemeral
        assert "permission" in call_args[0][0].lower()