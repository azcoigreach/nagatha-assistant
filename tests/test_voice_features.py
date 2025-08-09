"""
Tests for Nagatha's voice features.

This module tests the voice handler, voice commands, and voice integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import discord

from nagatha_assistant.core.voice_handler import VoiceHandler
from nagatha_assistant.core.voice_commands import (
    JoinVoiceSlashCommand,
    LeaveVoiceSlashCommand,
    VoiceStatusSlashCommand,
    SpeakSlashCommand
)


class TestVoiceHandler:
    """Test the VoiceHandler class."""
    
    @pytest.fixture
    def voice_handler(self):
        """Create a voice handler instance for testing."""
        discord_plugin = Mock()
        return VoiceHandler(discord_plugin)
    
    @pytest.fixture
    def mock_voice_channel(self):
        """Create a mock voice channel."""
        channel = Mock(spec=discord.VoiceChannel)
        channel.name = "Test Voice Channel"
        channel.id = 123456789
        return channel
    
    @pytest.fixture
    def mock_voice_client(self):
        """Create a mock voice client."""
        client = Mock()
        client.is_connected.return_value = True
        client.channel = Mock()
        client.channel.name = "Test Voice Channel"
        client.channel.id = 123456789
        return client
    
    def test_voice_handler_initialization(self, voice_handler):
        """Test voice handler initialization."""
        assert voice_handler.voice_clients == {}
        assert voice_handler.voice_sessions == {}
        assert voice_handler.text_channel_voice_links == {}
        # Note: whisper_model and openai_client may be None depending on environment
    
    @pytest.mark.asyncio
    async def test_join_voice_channel_success(self, voice_handler, mock_voice_channel):
        """Test successful voice channel join."""
        guild_id = 987654321
        
        # Mock the voice channel connect method
        mock_voice_channel.connect = AsyncMock(return_value=Mock())
        
        # Mock start_session
        with patch('nagatha_assistant.core.voice_handler.start_session', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = "test-session-id"
            
            result = await voice_handler.join_voice_channel(mock_voice_channel, guild_id)
            
            assert result is True
            assert guild_id in voice_handler.voice_clients
            assert guild_id in voice_handler.voice_sessions
            assert voice_handler.voice_sessions[guild_id]['channel_id'] == mock_voice_channel.id
    
    @pytest.mark.asyncio
    async def test_join_voice_channel_with_text_link(self, voice_handler, mock_voice_channel):
        """Test voice channel join with text channel linking."""
        guild_id = 987654321
        text_channel_id = "111222333"
        
        # Mock the voice channel connect method
        mock_voice_channel.connect = AsyncMock(return_value=Mock())
        
        # Mock start_session
        with patch('nagatha_assistant.core.voice_handler.start_session', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = "test-session-id"
            
            result = await voice_handler.join_voice_channel(mock_voice_channel, guild_id, text_channel_id)
            
            assert result is True
            assert guild_id in voice_handler.voice_clients
            assert guild_id in voice_handler.voice_sessions
            assert voice_handler.voice_sessions[guild_id]['text_channel_id'] == text_channel_id
            assert voice_handler.text_channel_voice_links[text_channel_id] == guild_id
    
    @pytest.mark.asyncio
    async def test_speak_text_channel_response_success(self, voice_handler, mock_voice_client):
        """Test successful text channel response speaking."""
        guild_id = 987654321
        text_channel_id = "111222333"
        response_text = "Hello, this is a test response!"
        
        # Set up voice session with text channel link
        voice_handler.voice_clients[guild_id] = mock_voice_client
        voice_handler.voice_sessions[guild_id] = {
            'text_channel_id': text_channel_id,
            'guild_id': guild_id
        }
        voice_handler.text_channel_voice_links[text_channel_id] = guild_id
        
        # Mock speak_in_voice_channel
        voice_handler.speak_in_voice_channel = AsyncMock(return_value=True)
        
        result = await voice_handler.speak_text_channel_response(text_channel_id, response_text)
        
        assert result is True
        voice_handler.speak_in_voice_channel.assert_called_once_with(response_text, guild_id)
    
    @pytest.mark.asyncio
    async def test_speak_text_channel_response_no_link(self, voice_handler):
        """Test text channel response speaking when no link exists."""
        text_channel_id = "111222333"
        response_text = "Hello, this is a test response!"
        
        # No text channel link exists
        result = await voice_handler.speak_text_channel_response(text_channel_id, response_text)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_speak_text_channel_response_voice_disconnected(self, voice_handler):
        """Test text channel response speaking when voice is disconnected."""
        guild_id = 987654321
        text_channel_id = "111222333"
        response_text = "Hello, this is a test response!"
        
        # Set up text channel link but no voice client
        voice_handler.text_channel_voice_links[text_channel_id] = guild_id
        
        result = await voice_handler.speak_text_channel_response(text_channel_id, response_text)
        
        assert result is False
        # Link should be cleaned up
        assert text_channel_id not in voice_handler.text_channel_voice_links
    
    @pytest.mark.asyncio
    async def test_leave_voice_channel_success(self, voice_handler, mock_voice_client):
        """Test successful voice channel leave."""
        guild_id = 987654321
        text_channel_id = "111222333"
        
        # Set up existing voice client with text channel link
        voice_handler.voice_clients[guild_id] = mock_voice_client
        voice_handler.voice_sessions[guild_id] = {
            'test': 'data',
            'text_channel_id': text_channel_id
        }
        voice_handler.text_channel_voice_links[text_channel_id] = guild_id
        
        # Mock disconnect
        mock_voice_client.disconnect = AsyncMock()
        
        result = await voice_handler.leave_voice_channel(guild_id)
        
        assert result is True
        assert guild_id not in voice_handler.voice_clients
        assert guild_id not in voice_handler.voice_sessions
        assert text_channel_id not in voice_handler.text_channel_voice_links
        mock_voice_client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_is_in_voice_channel(self, voice_handler, mock_voice_client):
        """Test voice channel connection check."""
        guild_id = 987654321
        
        # Not connected
        assert await voice_handler.is_in_voice_channel(guild_id) is False
        
        # Connected
        voice_handler.voice_clients[guild_id] = mock_voice_client
        assert await voice_handler.is_in_voice_channel(guild_id) is True
    
    @pytest.mark.asyncio
    async def test_get_voice_channel_info_with_text_link(self, voice_handler, mock_voice_client):
        """Test voice channel info retrieval with text channel link."""
        guild_id = 987654321
        text_channel_id = "111222333"
        
        # Set up voice client and session with proper mocking
        mock_voice_client.channel.members = [Mock(), Mock(), Mock()]  # Mock 3 members
        voice_handler.voice_clients[guild_id] = mock_voice_client
        voice_handler.voice_sessions[guild_id] = {
            'text_channel_id': text_channel_id,
            'joined_at': '2023-01-01T00:00:00'
        }
        
        info = await voice_handler.get_voice_channel_info(guild_id)
        
        assert info is not None
        assert info['channel_name'] == "Test Voice Channel"
        assert info['text_channel_id'] == text_channel_id
    
    @pytest.mark.asyncio
    async def test_get_voice_status(self, voice_handler):
        """Test voice status retrieval."""
        guild_id = 987654321
        
        status = await voice_handler.get_voice_status(guild_id)
        
        assert isinstance(status, dict)
        assert 'is_connected' in status
        assert 'channel_info' in status
        assert 'session_active' in status
        assert 'conversation_count' in status
        assert 'whisper_available' in status
        assert 'tts_available' in status


class TestVoiceCommands:
    """Test the voice slash commands."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = Mock(spec=discord.Interaction)
        interaction.response = Mock()
        interaction.followup = Mock()
        interaction.user = Mock()
        interaction.guild = Mock()
        interaction.guild.id = 987654321
        interaction.channel_id = 111222333
        return interaction
    
    @pytest.fixture
    def mock_discord_plugin(self):
        """Create a mock Discord plugin."""
        plugin = Mock()
        plugin.voice_handler = Mock()
        return plugin
    
    @pytest.mark.asyncio
    async def test_join_voice_command_success(self, mock_interaction, mock_discord_plugin):
        """Test successful join voice command."""
        # Mock user in voice channel
        mock_interaction.user.voice = Mock()
        mock_interaction.user.voice.channel = Mock(spec=discord.VoiceChannel)
        mock_interaction.user.voice.channel.name = "Test Channel"
        
        # Mock permissions
        mock_interaction.guild.me = Mock()
        mock_interaction.user.voice.channel.permissions_for.return_value.connect = True
        
        # Mock voice handler
        mock_discord_plugin.voice_handler.join_voice_channel = AsyncMock(return_value=True)
        mock_discord_plugin.voice_handler.start_voice_listening = AsyncMock()
        
        # Mock plugin manager
        with patch('nagatha_assistant.core.voice_commands.get_plugin_manager') as mock_manager:
            mock_manager.return_value.get_plugin.return_value = mock_discord_plugin
            
            command = JoinVoiceSlashCommand()
            await command.execute(mock_interaction)
            
            # Verify response
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args[0][0]
            assert "Joined voice channel" in call_args
    
    @pytest.mark.asyncio
    async def test_join_voice_command_with_text_linking(self, mock_interaction, mock_discord_plugin):
        """Test join voice command with text channel linking."""
        # Mock user in voice channel
        mock_interaction.user.voice = Mock()
        mock_interaction.user.voice.channel = Mock(spec=discord.VoiceChannel)
        mock_interaction.user.voice.channel.name = "Test Channel"
        
        # Mock permissions
        mock_interaction.guild.me = Mock()
        mock_interaction.user.voice.channel.permissions_for.return_value.connect = True
        
        # Mock voice handler
        mock_discord_plugin.voice_handler.join_voice_channel = AsyncMock(return_value=True)
        mock_discord_plugin.voice_handler.start_voice_listening = AsyncMock()
        
        # Mock plugin manager
        with patch('nagatha_assistant.core.voice_commands.get_plugin_manager') as mock_manager:
            mock_manager.return_value.get_plugin.return_value = mock_discord_plugin
            
            command = JoinVoiceSlashCommand()
            await command.execute(mock_interaction)
            
            # Verify that join_voice_channel was called with text channel ID
            mock_discord_plugin.voice_handler.join_voice_channel.assert_called_once()
            call_args = mock_discord_plugin.voice_handler.join_voice_channel.call_args
            assert call_args[0][0] == mock_interaction.user.voice.channel  # voice_channel
            assert call_args[0][1] == mock_interaction.guild.id  # guild_id
            assert call_args[0][2] == str(mock_interaction.channel_id)  # text_channel_id
    
    @pytest.mark.asyncio
    async def test_leave_voice_command_success(self, mock_interaction, mock_discord_plugin):
        """Test successful leave voice command."""
        # Mock voice handler
        mock_discord_plugin.voice_handler.is_in_voice_channel = AsyncMock(return_value=True)
        mock_discord_plugin.voice_handler.leave_voice_channel = AsyncMock(return_value=True)
        
        # Mock plugin manager
        with patch('nagatha_assistant.core.voice_commands.get_plugin_manager') as mock_manager:
            mock_manager.return_value.get_plugin.return_value = mock_discord_plugin
            
            command = LeaveVoiceSlashCommand()
            await command.execute(mock_interaction)
            
            # Verify response
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args[0][0]
            assert "Left voice channel" in call_args
    
    @pytest.mark.asyncio
    async def test_voice_status_command(self, mock_interaction, mock_discord_plugin):
        """Test voice status command."""
        # Mock voice handler status
        mock_status = {
            'is_connected': True,
            'channel_info': {
                'channel_name': 'Test Channel',
                'member_count': 3,
                'text_channel_id': '111222333'
            },
            'conversation_count': 5,
            'whisper_available': True,
            'tts_available': True
        }
        mock_discord_plugin.voice_handler.get_voice_status = AsyncMock(return_value=mock_status)
        
        # Mock plugin manager
        with patch('nagatha_assistant.core.voice_commands.get_plugin_manager') as mock_manager:
            mock_manager.return_value.get_plugin.return_value = mock_discord_plugin
            
            command = VoiceStatusSlashCommand()
            await command.execute(mock_interaction)
            
            # Verify response
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args[0][0]
            assert "Voice Status" in call_args
            assert "Test Channel" in call_args
    
    @pytest.mark.asyncio
    async def test_speak_command_success(self, mock_interaction, mock_discord_plugin):
        """Test successful speak command."""
        # Mock voice handler
        mock_discord_plugin.voice_handler.is_in_voice_channel = AsyncMock(return_value=True)
        mock_discord_plugin.voice_handler.speak_in_voice_channel = AsyncMock(return_value=True)
        
        # Mock plugin manager
        with patch('nagatha_assistant.core.voice_commands.get_plugin_manager') as mock_manager:
            mock_manager.return_value.get_plugin.return_value = mock_discord_plugin
            
            command = SpeakSlashCommand()
            await command.execute(mock_interaction, message="Hello world!")
            
            # Verify response
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args[0][0]
            assert "Speaking" in call_args


class TestVoiceIntegration:
    """Test voice integration with Discord bot."""
    
    @pytest.mark.asyncio
    async def test_voice_handler_integration(self):
        """Test that voice handler integrates properly with Discord bot."""
        # This test would verify that the voice handler is properly
        # integrated into the Discord bot plugin
        from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
        from nagatha_assistant.core.plugin import PluginConfig
        
        # Create a minimal config
        config = PluginConfig(
            name="test_discord",
            config={},
            enabled=True
        )
        
        # Create plugin instance
        plugin = DiscordBotPlugin(config)
        
        # Verify voice handler is initialized (when bot starts)
        assert hasattr(plugin, 'voice_handler')
        # Note: voice_handler will be None until bot starts


class TestTextToVoiceFeatures:
    """Test the new text-to-voice functionality."""
    
    @pytest.mark.asyncio
    async def test_text_channel_linking(self):
        """Test that text channels are properly linked to voice sessions."""
        from nagatha_assistant.core.voice_handler import VoiceHandler
        
        discord_plugin = Mock()
        voice_handler = VoiceHandler(discord_plugin)
        
        # Test that text channel links are tracked
        assert voice_handler.text_channel_voice_links == {}
        
        # Simulate joining with text channel link
        guild_id = 123
        text_channel_id = "456"
        voice_channel = Mock()
        voice_channel.connect = AsyncMock(return_value=Mock())
        
        with patch('nagatha_assistant.core.voice_handler.start_session', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = "test-session"
            
            await voice_handler.join_voice_channel(voice_channel, guild_id, text_channel_id)
            
            assert text_channel_id in voice_handler.text_channel_voice_links
            assert voice_handler.text_channel_voice_links[text_channel_id] == guild_id
    
    @pytest.mark.asyncio
    async def test_text_channel_response_speaking(self):
        """Test that text channel responses are spoken in voice channels."""
        from nagatha_assistant.core.voice_handler import VoiceHandler
        
        discord_plugin = Mock()
        voice_handler = VoiceHandler(discord_plugin)
        
        # Set up a linked text channel
        guild_id = 123
        text_channel_id = "456"
        voice_handler.text_channel_voice_links[text_channel_id] = guild_id
        
        # Mock voice client
        voice_client = Mock()
        voice_client.is_connected.return_value = True
        voice_handler.voice_clients[guild_id] = voice_client
        
        # Mock speak method
        voice_handler.speak_in_voice_channel = AsyncMock(return_value=True)

        # Test speaking a response
        response_text = "This is a test response"
        result = await voice_handler.speak_text_channel_response(text_channel_id, response_text)

        assert result is True
        voice_handler.speak_in_voice_channel.assert_called_once_with(response_text, guild_id)

    @pytest.mark.asyncio
    async def test_voice_packet_processing(self, voice_handler):
        """Test that buffered voice packets are transcribed and spoken."""
        guild_id = 1
        user_id = 2

        await voice_handler.start_voice_listening(guild_id)

        voice_handler.handle_voice_message = AsyncMock(return_value="hi there")
        voice_handler.speak_in_voice_channel = AsyncMock(return_value=True)

        # Simulate speaking event with buffered audio
        await voice_handler.handle_voice_activity(user_id, guild_id, True)
        await voice_handler.handle_voice_packet(user_id, b"audio-bytes", guild_id)
        await voice_handler.handle_voice_activity(user_id, guild_id, False)

        voice_handler.handle_voice_message.assert_awaited_once()
        voice_handler.speak_in_voice_channel.assert_awaited_once_with("hi there", guild_id)


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"]) 