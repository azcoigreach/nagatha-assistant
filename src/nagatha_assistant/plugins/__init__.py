"""
Built-in plugins for Nagatha Assistant.

This package contains the core plugins that ship with Nagatha Assistant.
Plugins provide extended functionality through a well-defined interface.
"""

from .echo_plugin import EchoPlugin
from .task_manager import TaskManagerPlugin

# Plugin registry for built-in plugins
BUILTIN_PLUGINS = {
    "echo": EchoPlugin,
    "task_manager": TaskManagerPlugin,
}

__all__ = ["BUILTIN_PLUGINS", "EchoPlugin", "TaskManagerPlugin"]