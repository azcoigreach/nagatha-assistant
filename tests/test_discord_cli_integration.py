"""
Test Discord CLI integration with PluginManager.

Tests that the Discord CLI commands can properly interact with the PluginManager
without raising attribute errors.
"""

import pytest
from nagatha_assistant.core.plugin_manager import get_plugin_manager


@pytest.mark.asyncio
async def test_plugin_manager_initialization():
    """Test that plugin manager can be initialized properly."""
    pm = get_plugin_manager()
    
    # Should start uninitialized
    assert not pm._initialized
    
    # Initialize should work without errors
    await pm.initialize()
    
    # Should be marked as initialized
    assert pm._initialized


@pytest.mark.asyncio 
async def test_plugin_manager_get_plugin():
    """Test that plugin manager has get_plugin method."""
    pm = get_plugin_manager()
    
    # Initialize to load plugins
    if not pm._initialized:
        await pm.initialize()
    
    # get_plugin method should exist and be callable
    assert hasattr(pm, 'get_plugin')
    assert callable(pm.get_plugin)
    
    # Should return None for non-existent plugin
    non_existent = pm.get_plugin("non_existent_plugin")
    assert non_existent is None
    
    # Should return Discord bot plugin if loaded
    discord_plugin = pm.get_plugin("discord_bot")
    if discord_plugin:
        assert discord_plugin.name == "discord_bot"


@pytest.mark.asyncio
async def test_discord_plugin_loading():
    """Test that Discord bot plugin can be loaded."""
    pm = get_plugin_manager()
    
    # Initialize to load plugins
    await pm.initialize()
    
    # Discord bot plugin should be loaded
    discord_plugin = pm.get_plugin("discord_bot")
    assert discord_plugin is not None
    assert discord_plugin.name == "discord_bot"
    
    # Plugin should have the expected methods
    assert hasattr(discord_plugin, 'start_discord_bot')
    assert hasattr(discord_plugin, 'stop_discord_bot')
    assert hasattr(discord_plugin, 'get_discord_status')


@pytest.mark.asyncio
async def test_multiple_initializations():
    """Test that multiple initializations don't cause issues."""
    pm = get_plugin_manager()
    
    # First initialization
    await pm.initialize()
    assert pm._initialized
    
    # Second initialization should not cause errors
    await pm.initialize()
    assert pm._initialized
    
    # Should still be able to get plugins
    discord_plugin = pm.get_plugin("discord_bot")
    assert discord_plugin is not None


def test_plugin_manager_has_required_attributes():
    """Test that plugin manager has all required attributes for CLI commands."""
    pm = get_plugin_manager()
    
    # Should have _initialized attribute
    assert hasattr(pm, '_initialized')
    
    # Should have get_plugin method
    assert hasattr(pm, 'get_plugin')
    assert callable(pm.get_plugin)
    
    # Should have initialize method
    assert hasattr(pm, 'initialize')
    assert callable(pm.initialize)