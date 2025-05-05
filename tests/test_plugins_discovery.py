import pytest

from nagatha_assistant.core.plugin import PluginManager


def test_plugins_discovered():
    """Ensure Notes, Tasks, and Reminders plugins are discovered."""
    pm = pytest.raises  # placeholder
    manager = pytest.MonkeyPatch().context()  # We'll manually instantiate
    pm = PluginManager()
    # Discover plugins
    import asyncio
    asyncio.run(pm.discover())
    names = {plugin.name for plugin in pm.plugins}
    # Core plugins plus our new ones must be present
    assert 'notes' in names
    assert 'tasks' in names
    assert 'reminders' in names

def test_function_specs_include_core():
    """Ensure function specs include note/task/reminder functions."""
    import asyncio
    pm = PluginManager()
    asyncio.run(pm.discover())
    specs = pm.function_specs()
    names = {spec['name'] for spec in specs}
    # Verify key function names
    for fn in ['create_note', 'list_notes', 'get_note',
               'create_task', 'list_tasks', 'complete_task', 'close_task',
               'create_reminder', 'list_reminders', 'deliver_reminder']:
        assert fn in names