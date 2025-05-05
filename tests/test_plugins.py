import pytest

from nagatha_assistant.core.plugin import Plugin, PluginManager


@pytest.mark.asyncio
async def test_plugin_manager_importable():
    manager = PluginManager()
    assert hasattr(manager, "discover")
    assert hasattr(manager, "setup_all")
    assert hasattr(manager, "teardown_all")


def test_plugin_base_importable():
    # Ensure Plugin abstract base has required attributes
    assert hasattr(Plugin, "name")
    assert hasattr(Plugin, "version")
    assert hasattr(Plugin, "setup")
    assert hasattr(Plugin, "teardown")


# ---------------------------------------------------------------------------
# Echo plugin integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_echo_plugin_discovery_and_call():
    """Echo plugin should be discovered and return the same text."""

    manager = PluginManager()
    await manager.discover()
    await manager.setup_all({})

    # Check that the echo function is advertised
    func_names = [spec["name"] for spec in manager.function_specs()]
    assert "echo" in func_names

    # Call it and verify behaviour
    result = await manager.call_function("echo", {"text": "foobar"})
    assert result == "foobar"