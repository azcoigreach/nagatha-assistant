"""
Tests for Discord sync command functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord

from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
from nagatha_assistant.core.plugin import PluginConfig


class TestSyncCommand:
    """Test the sync command functionality."""
    
    @pytest.fixture
    def discord_plugin(self):
        """Create a Discord plugin instance for testing."""
        config = PluginConfig(
            name="test_discord",
            config={},
            enabled=True
        )
        return DiscordBotPlugin(config)
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        bot = Mock()
        bot.user = Mock()
        bot.user.name = "TestBot"
        bot.guilds = [Mock(), Mock()]  # 2 guilds
        return bot
    
    def test_sync_command_plugin_registration(self, discord_plugin):
        """Test that sync command is properly registered."""
        # Check that the sync command is registered in setup
        # This would be tested by checking the plugin manager
        assert hasattr(discord_plugin, 'sync_discord_commands')
    
    @pytest.mark.asyncio
    async def test_sync_command_not_running(self, discord_plugin):
        """Test sync command when bot is not running."""
        result = await discord_plugin.sync_discord_commands()
        
        assert "not running" in result
        assert "Start it first" in result
    
    @pytest.mark.asyncio
    async def test_sync_command_no_bot(self, discord_plugin):
        """Test sync command when bot is not initialized."""
        discord_plugin.is_running = True
        discord_plugin.bot = None
        
        result = await discord_plugin.sync_discord_commands()
        
        assert "not initialized" in result
    
    @pytest.mark.asyncio
    async def test_sync_command_invalid_guild_id(self, discord_plugin, mock_bot):
        """Test sync command with invalid guild ID."""
        discord_plugin.is_running = True
        discord_plugin.bot = mock_bot
        
        result = await discord_plugin.sync_discord_commands(guild_id="invalid")
        
        assert "Invalid guild ID" in result
    
    @pytest.mark.asyncio
    async def test_sync_command_success_global(self, discord_plugin, mock_bot):
        """Test successful global sync."""
        discord_plugin.is_running = True
        discord_plugin.bot = mock_bot
        
        # Mock the sync_slash_commands method
        discord_plugin.sync_slash_commands = AsyncMock(return_value=5)
        
        result = await discord_plugin.sync_discord_commands()
        
        assert "✅ Synced 5 slash commands globally" in result
        discord_plugin.sync_slash_commands.assert_called_once_with(None)
    
    @pytest.mark.asyncio
    async def test_sync_command_success_guild(self, discord_plugin, mock_bot):
        """Test successful guild-specific sync."""
        discord_plugin.is_running = True
        discord_plugin.bot = mock_bot
        
        # Mock guild
        mock_guild = Mock()
        mock_guild.name = "Test Guild"
        mock_bot.get_guild.return_value = mock_guild
        
        # Mock the sync_slash_commands method
        discord_plugin.sync_slash_commands = AsyncMock(return_value=5)
        
        result = await discord_plugin.sync_discord_commands(guild_id="123456789")
        
        assert "✅ Synced 5 slash commands to guild: Test Guild" in result
        discord_plugin.sync_slash_commands.assert_called_once_with(123456789)
    
    @pytest.mark.asyncio
    async def test_sync_command_guild_not_found(self, discord_plugin, mock_bot):
        """Test sync command when guild is not found."""
        discord_plugin.is_running = True
        discord_plugin.bot = mock_bot
        
        # Mock guild not found
        mock_bot.get_guild.return_value = None
        
        # Mock the sync_slash_commands method
        discord_plugin.sync_slash_commands = AsyncMock(return_value=5)
        
        result = await discord_plugin.sync_discord_commands(guild_id="123456789")
        
        assert "✅ Synced 5 slash commands to guild: Guild 123456789" in result
    
    @pytest.mark.asyncio
    async def test_sync_command_exception(self, discord_plugin, mock_bot):
        """Test sync command when an exception occurs."""
        discord_plugin.is_running = True
        discord_plugin.bot = mock_bot
        
        # Mock the sync_slash_commands method to raise an exception
        discord_plugin.sync_slash_commands = AsyncMock(side_effect=Exception("Test error"))
        
        result = await discord_plugin.sync_discord_commands()
        
        assert "❌ Error syncing commands" in result
        assert "Test error" in result


class TestSyncSlashCommand:
    """Test the /sync slash command."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = Mock(spec=discord.Interaction)
        interaction.response = Mock()
        interaction.followup = Mock()
        interaction.user = Mock()
        interaction.guild = Mock()
        interaction.guild.id = 123456789
        return interaction
    
    @pytest.fixture
    def discord_plugin(self):
        """Create a Discord plugin instance for testing."""
        config = PluginConfig(
            name="test_discord",
            config={},
            enabled=True
        )
        plugin = DiscordBotPlugin(config)
        plugin.is_running = True
        plugin.bot = Mock()
        return plugin
    
    @pytest.mark.asyncio
    async def test_sync_slash_command_success_guild(self, discord_plugin, mock_interaction):
        """Test successful /sync command in a guild."""
        # Mock admin permissions
        mock_interaction.user.guild_permissions.administrator = True
        
        # Mock sync method
        discord_plugin.sync_slash_commands = AsyncMock(return_value=5)
        
        await discord_plugin._handle_sync_command(mock_interaction)
        
        # Verify response
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "✅ Synced 5 slash commands to this server!" in call_args
    
    @pytest.mark.asyncio
    async def test_sync_slash_command_success_dm(self, discord_plugin, mock_interaction):
        """Test successful /sync command in DM."""
        # Mock DM (no guild)
        mock_interaction.guild = None
        
        # Mock sync method
        discord_plugin.sync_slash_commands = AsyncMock(return_value=5)
        
        await discord_plugin._handle_sync_command(mock_interaction)
        
        # Verify response
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "✅ Synced 5 slash commands globally!" in call_args
    
    @pytest.mark.asyncio
    async def test_sync_slash_command_no_permission(self, discord_plugin, mock_interaction):
        """Test /sync command without admin permission."""
        # Mock non-admin permissions
        mock_interaction.user.guild_permissions.administrator = False
        
        await discord_plugin._handle_sync_command(mock_interaction)
        
        # Verify response
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args
    
    @pytest.mark.asyncio
    async def test_sync_slash_command_exception(self, discord_plugin, mock_interaction):
        """Test /sync command when an exception occurs."""
        # Mock admin permissions
        mock_interaction.user.guild_permissions.administrator = True
        
        # Mock sync method to raise exception
        discord_plugin.sync_slash_commands = AsyncMock(side_effect=Exception("Test error"))
        
        await discord_plugin._handle_sync_command(mock_interaction)
        
        # Verify response
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ Error syncing commands" in call_args


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"]) 