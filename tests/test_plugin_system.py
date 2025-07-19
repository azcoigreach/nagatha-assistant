"""
Tests for the plugin system.
"""

import asyncio
import pytest
import pytest_asyncio
import tempfile
from pathlib import Path

from nagatha_assistant.core.plugin import (
    BasePlugin, SimplePlugin, PluginConfig, PluginCommand, PluginState
)
from nagatha_assistant.core.plugin_manager import PluginManager, get_plugin_manager
from nagatha_assistant.core.event_bus import get_event_bus


class MockTestPlugin(SimplePlugin):
    """Simple test plugin for testing."""
    
    async def setup(self):
        """Setup test plugin."""
        self.test_value = "test_setup_called"
    
    async def teardown(self):
        """Teardown test plugin."""
        self.test_value = "test_teardown_called"


@pytest_asyncio.fixture
async def event_bus():
    """Fixture to provide a started event bus."""
    bus = get_event_bus()
    await bus.start()
    yield bus
    await bus.stop()


@pytest.mark.asyncio
async def test_plugin_config():
    """Test plugin configuration creation."""
    config = PluginConfig(
        name="test_plugin",
        version="1.0.0",
        description="Test plugin",
        dependencies=["dep1"],
        config={"key": "value"}
    )
    
    assert config.name == "test_plugin"
    assert config.version == "1.0.0"
    assert config.dependencies == ["dep1"]
    assert config.config["key"] == "value"
    assert config.enabled is True


@pytest.mark.asyncio
async def test_simple_plugin_lifecycle(event_bus):
    """Test basic plugin lifecycle."""
    config = PluginConfig(name="test", version="1.0.0")
    plugin = MockTestPlugin(config)
    
    assert plugin.state == PluginState.LOADED
    
    # Initialize
    await plugin.initialize()
    assert plugin.state == PluginState.INITIALIZED
    
    # Start
    await plugin.start()
    assert plugin.state == PluginState.STARTED
    assert plugin.test_value == "test_setup_called"
    
    # Stop
    await plugin.stop()
    assert plugin.state == PluginState.STOPPED
    assert plugin.test_value == "test_teardown_called"


@pytest.mark.asyncio
async def test_plugin_manager_basic(event_bus):
    """Test basic plugin manager functionality."""
    manager = PluginManager()
    
    # Test plugin class registration
    manager.register_plugin_class("test", MockTestPlugin)
    
    # Test plugin loading
    config = PluginConfig(name="test", version="1.0.0")
    success = await manager.load_plugin(config)
    assert success is True
    
    # Test plugin initialization
    success = await manager.initialize_plugin("test")
    assert success is True
    
    # Test plugin start
    success = await manager.start_plugin("test")
    assert success is True
    
    # Check status
    status = manager.get_plugin_status()
    assert "test" in status
    assert status["test"]["state"] == "started"
    
    # Test plugin stop
    success = await manager.stop_plugin("test")
    assert success is True
    
    # Test plugin unload
    success = await manager.unload_plugin("test")
    assert success is True


@pytest.mark.asyncio
async def test_dependency_resolution():
    """Test plugin dependency resolution."""
    manager = PluginManager()
    
    plugins = {
        "plugin_a": PluginConfig(name="plugin_a", dependencies=[]),
        "plugin_b": PluginConfig(name="plugin_b", dependencies=["plugin_a"]),
        "plugin_c": PluginConfig(name="plugin_c", dependencies=["plugin_b", "plugin_a"])
    }
    
    order = manager.resolve_dependencies(plugins)
    
    # plugin_a should come before plugin_b
    assert order.index("plugin_a") < order.index("plugin_b")
    # plugin_b should come before plugin_c
    assert order.index("plugin_b") < order.index("plugin_c")


@pytest.mark.asyncio
async def test_circular_dependency_detection():
    """Test circular dependency detection."""
    manager = PluginManager()
    
    plugins = {
        "plugin_a": PluginConfig(name="plugin_a", dependencies=["plugin_b"]),
        "plugin_b": PluginConfig(name="plugin_b", dependencies=["plugin_a"])
    }
    
    with pytest.raises(Exception):  # Should raise PluginError for circular dependency
        manager.resolve_dependencies(plugins)


@pytest.mark.asyncio
async def test_plugin_command_registration(event_bus):
    """Test plugin command registration."""
    manager = PluginManager()
    
    # Register test plugin
    manager.register_plugin_class("test", MockTestPlugin)
    config = PluginConfig(name="test", version="1.0.0")
    
    await manager.load_plugin(config)
    await manager.initialize_plugin("test")
    await manager.start_plugin("test")
    
    # Create and register a command
    async def test_command_handler(text: str) -> str:
        return f"handled: {text}"
    
    command = PluginCommand(
        name="test_command",
        description="Test command",
        handler=test_command_handler,
        plugin_name="test"
    )
    
    success = manager.register_command(command)
    assert success is True
    
    # Test command execution
    result = await manager.execute_command("test_command", "hello")
    assert result == "handled: hello"
    
    # Test command listing
    commands = manager.get_available_commands()
    assert "test_command" in commands
    assert commands["test_command"]["plugin"] == "test"
    
    # Cleanup
    await manager.stop_plugin("test")


@pytest.mark.asyncio
async def test_event_bus_integration(event_bus):
    """Test plugin integration with event bus."""
    # Create plugin
    config = PluginConfig(name="test", version="1.0.0")
    plugin = MockTestPlugin(config)
    
    # Track events
    received_events = []
    
    def event_handler(event):
        received_events.append(event)
    
    # Subscribe to plugin events
    event_bus.subscribe("plugin.*", event_handler)
    
    # Run plugin lifecycle
    await plugin.initialize()
    await plugin.start()
    await plugin.stop()
    
    # Give events time to process
    await asyncio.sleep(0.1)
    
    # Check that state change events were published
    assert len(received_events) >= 3  # initialized, started, stopped
    
    state_events = [e for e in received_events if e.event_type.startswith("plugin.")]
    assert len(state_events) >= 3


@pytest.mark.asyncio
async def test_plugin_discovery():
    """Test plugin discovery from files."""
    manager = PluginManager()
    
    # Create a temporary plugin file
    with tempfile.TemporaryDirectory() as temp_dir:
        plugin_dir = Path(temp_dir)
        
        # Create a simple plugin file
        plugin_content = '''
from nagatha_assistant.core.plugin import SimplePlugin, PluginConfig

class TempPlugin(SimplePlugin):
    pass

PLUGIN_CONFIG = {
    "name": "temp_plugin",
    "version": "1.0.0", 
    "description": "Temporary test plugin"
}
'''
        
        plugin_file = plugin_dir / "temp_plugin.py"
        plugin_file.write_text(plugin_content)
        
        # Add discovery path
        manager.add_discovery_path(plugin_dir)
        
        # Discover plugins
        discovered = manager.discover_plugins()
        
        # Should find our temp plugin
        assert "temp_plugin" in discovered
        assert discovered["temp_plugin"].name == "temp_plugin"
        assert discovered["temp_plugin"].version == "1.0.0"


@pytest.mark.asyncio  
async def test_global_plugin_manager():
    """Test global plugin manager singleton."""
    manager1 = get_plugin_manager()
    manager2 = get_plugin_manager()
    
    # Should be the same instance
    assert manager1 is manager2