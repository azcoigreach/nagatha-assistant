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