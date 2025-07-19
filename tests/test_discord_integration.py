"""
Test Discord bot plugin integration with Nagatha's plugin system.
"""

import pytest
from unittest.mock import patch, MagicMock
import os

def test_discord_plugin_discovery():
    """Test that the Discord plugin can be discovered and loaded."""
    from nagatha_assistant.plugins.discord_bot import PLUGIN_CONFIG, DiscordBotPlugin
    from nagatha_assistant.core.plugin import PluginConfig
    
    # Test plugin config is valid
    assert PLUGIN_CONFIG["name"] == "discord_bot"
    assert PLUGIN_CONFIG["enabled"] is True
    
    # Test plugin can be instantiated
    config = PluginConfig(**PLUGIN_CONFIG)
    
    with patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token'}):
        plugin = DiscordBotPlugin(config)
        assert plugin.name == "discord_bot"
        assert plugin.token == "test_token"

def test_discord_plugin_registration():
    """Test that Discord commands are properly registered."""
    from nagatha_assistant.plugins.discord_bot import DiscordBotPlugin
    from nagatha_assistant.core.plugin import PluginConfig
    
    config = PluginConfig(name="discord_bot", version="1.0.0")
    
    with patch.dict(os.environ, {'DISCORD_BOT_TOKEN': 'test_token'}):
        plugin = DiscordBotPlugin(config)
        
        # Mock plugin manager to capture registered commands
        with patch('nagatha_assistant.core.plugin_manager.get_plugin_manager') as mock_manager:
            mock_manager.return_value.register_command = MagicMock()
            
            # Setup should register commands even without token
            import asyncio
            asyncio.run(plugin.setup())
            
            # Should have registered 3 commands
            assert mock_manager.return_value.register_command.call_count == 3
            
            # Check command names
            registered_commands = [
                call[0][0].name for call in mock_manager.return_value.register_command.call_args_list
            ]
            
            expected_commands = ["discord_start", "discord_stop", "discord_status"]
            for cmd in expected_commands:
                assert cmd in registered_commands

if __name__ == "__main__":
    pytest.main([__file__])