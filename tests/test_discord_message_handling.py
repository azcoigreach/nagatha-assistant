"""
Tests for Discord message handling and session management.

This module tests the complete flow of Discord message processing,
including auto-chat message handling, session creation per channel,
and conversation context preservation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call, PropertyMock
from datetime import datetime
import discord
import pytest_asyncio

from nagatha_assistant.plugins.discord_bot import NagathaDiscordBot, DiscordBotPlugin
from nagatha_assistant.core.plugin import PluginConfig


class MockDiscordMessage:
    """Mock Discord message for testing."""
    
    def __init__(self, content="test message", author_id=12345, channel_id=67890, guild_id=11111):
        self.content = content
        self.id = 999999
        self.type = discord.MessageType.default
        
        # Mock author
        self.author = MagicMock()
        self.author.id = author_id
        self.author.display_name = "TestUser"
        self.author.bot = False
        
        # Mock channel
        self.channel = MagicMock()
        self.channel.id = channel_id
        self.channel.send = AsyncMock()
        
        # Mock guild
        self.guild = MagicMock()
        self.guild.id = guild_id
        
        # Mock Discord internal state
        self._state = MagicMock()


class TestDiscordMessageHandling:
    """Test cases for Discord message handling."""
    
    @pytest.fixture
    def mock_discord_plugin(self):
        """Create a mock Discord plugin."""
        config = PluginConfig(
            name="discord_bot",
            version="1.0.0",
            description="Test Discord bot",
            config={}
        )
        plugin = MagicMock(spec=DiscordBotPlugin)
        plugin.config = config
        plugin.publish_event = AsyncMock()
        return plugin
    
    @pytest.fixture
    def discord_bot(self, mock_discord_plugin):
        """Create a Discord bot instance for testing."""
        intents = discord.Intents.default()
        intents.message_content = True
        
        bot = NagathaDiscordBot(
            mock_discord_plugin,
            command_prefix="!",
            intents=intents
        )
        
        # Mock the user property using PropertyMock
        mock_user = MagicMock()
        mock_user.id = 99999
        mock_user.name = "TestBot"
        
        # Use PropertyMock to replace the user property
        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user_prop:
            mock_user_prop.return_value = mock_user
            yield bot
    
    @pytest.mark.asyncio
    async def test_on_message_ignores_bot_messages(self, discord_bot):
        """Test that the bot ignores messages from other bots."""
        # Create a message from a bot
        message = MockDiscordMessage()
        message.author.bot = True
        
        with patch.object(discord_bot, '_handle_auto_chat_message') as mock_handler:
            await discord_bot.on_message(message)
            
            # Should not call auto-chat handler for bot messages
            mock_handler.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_message_ignores_own_messages(self, discord_bot):
        """Test that the bot ignores its own messages."""
        message = MockDiscordMessage()
        message.author = discord_bot.user  # Message from the bot itself
        
        with patch.object(discord_bot, '_handle_auto_chat_message') as mock_handler:
            await discord_bot.on_message(message)
            
            mock_handler.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_message_ignores_system_messages(self, discord_bot):
        """Test that the bot ignores system messages."""
        message = MockDiscordMessage()
        message.type = discord.MessageType.pins_add  # System message type
        
        with patch.object(discord_bot, '_handle_auto_chat_message') as mock_handler:
            await discord_bot.on_message(message)
            
            mock_handler.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_message_processes_auto_chat_when_enabled(self, discord_bot):
        """Test that messages are processed when auto-chat is enabled."""
        message = MockDiscordMessage(content="Hello bot!")
        
        with patch('nagatha_assistant.plugins.discord_bot.is_auto_chat_enabled', return_value=True), \
             patch('nagatha_assistant.plugins.discord_bot.should_rate_limit', return_value=False), \
             patch.object(discord_bot, '_handle_auto_chat_message') as mock_handler:
            
            await discord_bot.on_message(message)
            
            # Should call auto-chat handler
            mock_handler.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_on_message_skips_when_auto_chat_disabled(self, discord_bot):
        """Test that messages are skipped when auto-chat is disabled."""
        message = MockDiscordMessage()
        
        with patch('nagatha_assistant.plugins.discord_bot.is_auto_chat_enabled', return_value=False), \
             patch.object(discord_bot, '_handle_auto_chat_message') as mock_handler:
            
            await discord_bot.on_message(message)
            
            # Should not call auto-chat handler
            mock_handler.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_message_skips_when_rate_limited(self, discord_bot):
        """Test that messages are skipped when rate limited."""
        message = MockDiscordMessage()
        
        with patch('nagatha_assistant.plugins.discord_bot.is_auto_chat_enabled', return_value=True), \
             patch('nagatha_assistant.plugins.discord_bot.should_rate_limit', return_value=True), \
             patch.object(discord_bot, '_handle_auto_chat_message') as mock_handler:
            
            await discord_bot.on_message(message)
            
            # Should not call auto-chat handler due to rate limiting
            mock_handler.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_auto_chat_message_uses_unified_server(self, discord_bot):
        """Test that auto-chat messages use the unified server for processing."""
        message = MockDiscordMessage(content="What's the weather?", 
                                   channel_id=12345, author_id=67890)
        
        # Mock the unified server
        mock_server = AsyncMock()
        mock_server.process_message.return_value = "It's sunny today!"
        
        with patch('nagatha_assistant.server.core_server.get_unified_server', return_value=mock_server), \
             patch('nagatha_assistant.plugins.discord_bot.update_auto_chat_usage') as mock_usage:
            
            await discord_bot._handle_auto_chat_message(message)
            
            # Verify server was called with correct parameters
            mock_server.process_message.assert_called_once_with(
                message="What's the weather?",
                user_id="discord:67890",
                interface="discord",
                interface_context={
                    "interface": "discord",
                    "channel_id": "12345",
                    "guild_id": "11111",
                    "message_id": "999999",
                    "author": {
                        "id": "67890",
                        "name": "TestUser",
                        "bot": False
                    }
                }
            )
            
            # Verify usage was updated
            mock_usage.assert_called_once_with("12345")
            
            # Verify response was sent to channel
            message.channel.send.assert_called_once_with("It's sunny today!")
    
    @pytest.mark.asyncio
    async def test_handle_auto_chat_message_error_handling(self, discord_bot):
        """Test error handling in auto-chat message processing."""
        message = MockDiscordMessage()
        
        # Mock server to raise an exception
        mock_server = AsyncMock()
        mock_server.process_message.side_effect = Exception("Server error")
        
        with patch('nagatha_assistant.server.core_server.get_unified_server', return_value=mock_server), \
             patch('nagatha_assistant.utils.logger.get_logger') as mock_logger:
            
            await discord_bot._handle_auto_chat_message(message)
            
            # Should send error message to channel
            message.channel.send.assert_called_once_with(
                "❌ Sorry, I encountered an error processing your message."
            )
    
    @pytest.mark.asyncio
    async def test_send_long_message_splits_correctly(self, discord_bot):
        """Test that long messages are split correctly."""
        channel = MagicMock()
        channel.send = AsyncMock()
        
        # Create a message longer than Discord's 2000 character limit
        long_content = "a" * 2500
        
        await discord_bot._send_long_message(channel, long_content)
        
        # Should be called multiple times due to message splitting
        assert channel.send.call_count >= 2
        
        # First call should be the main content
        first_call = channel.send.call_args_list[0][0][0]
        assert len(first_call) <= 1950  # Should respect the margin
        
        # Subsequent calls should have continuation marker
        if len(channel.send.call_args_list) > 1:
            second_call = channel.send.call_args_list[1][0][0]
            assert "**(continued...)**" in second_call
    
    @pytest.mark.asyncio
    async def test_send_short_message_no_split(self, discord_bot):
        """Test that short messages are not split."""
        channel = MagicMock()
        channel.send = AsyncMock()
        
        short_content = "This is a short message"
        
        await discord_bot._send_long_message(channel, short_content)
        
        # Should be called only once
        channel.send.assert_called_once_with(short_content)


class TestDiscordSessionManagement:
    """Test cases for Discord session management."""
    
    @pytest.mark.asyncio
    async def test_channel_based_session_creation(self):
        """Test that sessions are created per Discord channel."""
        from nagatha_assistant.server.core_server import AgentSessionManager
        
        session_manager = AgentSessionManager()
        
        # Mock the start_session function
        with patch('nagatha_assistant.server.core_server.start_session', side_effect=[101, 102, 103]):
            
            # Same channel should reuse session
            session1 = await session_manager.get_or_create_session(
                user_id="discord:user1",
                interface="discord",
                interface_context={"channel_id": "12345"}
            )
            
            session2 = await session_manager.get_or_create_session(
                user_id="discord:user2", 
                interface="discord",
                interface_context={"channel_id": "12345"}  # Same channel
            )
            
            # Different channel should create new session
            session3 = await session_manager.get_or_create_session(
                user_id="discord:user1",
                interface="discord", 
                interface_context={"channel_id": "67890"}  # Different channel
            )
            
            # Same channel should reuse the first session
            assert session1 == session2
            
            # Different channel should have different session
            assert session1 != session3
    
    @pytest.mark.asyncio
    async def test_session_metadata_storage(self):
        """Test that session metadata is properly stored."""
        from nagatha_assistant.server.core_server import AgentSessionManager
        
        session_manager = AgentSessionManager()
        
        interface_context = {
            "channel_id": "12345",
            "guild_id": "67890",
            "message_id": "111111"
        }
        
        with patch('nagatha_assistant.server.core_server.start_session', return_value=101):
            session_id = await session_manager.get_or_create_session(
                user_id="discord:user1",
                interface="discord",
                interface_context=interface_context
            )
            
            # Check that session info was stored
            session_info = session_manager.get_session_info(str(session_id))
            
            assert session_info is not None
            assert session_info["session_id"] == session_id
            assert session_info["user_id"] == "discord:user1"
            assert session_info["interface"] == "discord"
            assert session_info["session_key"] == "discord_channel:12345"
            assert session_info["interface_context"] == interface_context
            assert session_info["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_session_reuse_preserves_context(self):
        """Test that reusing sessions preserves conversation context."""
        from nagatha_assistant.server.core_server import AgentSessionManager
        
        session_manager = AgentSessionManager()
        
        interface_context1 = {"channel_id": "12345", "message_id": "111"}
        interface_context2 = {"channel_id": "12345", "message_id": "222"}
        
        with patch('nagatha_assistant.server.core_server.start_session', return_value=101):
            # First message in channel
            session_id1 = await session_manager.get_or_create_session(
                user_id="discord:user1",
                interface="discord",
                interface_context=interface_context1
            )
            
            # Second message in same channel
            session_id2 = await session_manager.get_or_create_session(
                user_id="discord:user2",
                interface="discord", 
                interface_context=interface_context2
            )
            
            # Should reuse the same session
            assert session_id1 == session_id2
            
            # Session should be updated with latest interface context
            session_info = session_manager.get_session_info(str(session_id1))
            assert session_info["interface_context"] == interface_context2


class TestDiscordIntegrationFlow:
    """Integration tests for the complete Discord message flow."""
    
    @pytest.mark.asyncio
    async def test_complete_discord_message_flow(self):
        """Test the complete flow from Discord message to response."""
        # This test simulates the entire flow:
        # Discord message -> on_message -> auto-chat -> unified server -> response
        
        from nagatha_assistant.plugins.discord_bot import NagathaDiscordBot
        from nagatha_assistant.server.core_server import NagathaUnifiedServer, ServerConfig
        
        # Create mock components
        mock_plugin = MagicMock()
        mock_plugin.publish_event = AsyncMock()
        
        # Create bot
        intents = discord.Intents.default()
        intents.message_content = True
        bot = NagathaDiscordBot(mock_plugin, command_prefix="!", intents=intents)
        
        # Mock the user property
        mock_user = MagicMock()
        mock_user.id = 99999
        
        with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user_prop:
            mock_user_prop.return_value = mock_user
            
            # Create mock unified server
            mock_server = AsyncMock()
            mock_server.process_message.return_value = "I understand your message!"
            
            # Create test message
            message = MockDiscordMessage(
                content="Hello, can you help me?",
                author_id=12345,
                channel_id=67890
            )
            
            with patch('nagatha_assistant.plugins.discord_bot.is_auto_chat_enabled', return_value=True), \
                 patch('nagatha_assistant.plugins.discord_bot.should_rate_limit', return_value=False), \
                 patch('nagatha_assistant.plugins.discord_bot.update_auto_chat_usage'), \
                 patch('nagatha_assistant.server.core_server.get_unified_server', return_value=mock_server):
                
                # Process the message
                await bot.on_message(message)
                
                # Verify the complete flow
                mock_server.process_message.assert_called_once()
                call_args = mock_server.process_message.call_args
                
                assert call_args[1]['message'] == "Hello, can you help me?"
                assert call_args[1]['user_id'] == "discord:12345"
                assert call_args[1]['interface'] == "discord"
                assert call_args[1]['interface_context']['channel_id'] == "67890"
                
                # Verify response was sent
                message.channel.send.assert_called_once_with("I understand your message!")