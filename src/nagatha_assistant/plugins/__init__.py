"""
Built-in plugins for Nagatha Assistant.

This package contains the core plugins that ship with Nagatha Assistant.
Plugins provide extended functionality through a well-defined interface.
"""

from .echo_plugin import EchoPlugin

# Plugin registry for built-in plugins
BUILTIN_PLUGINS = {
    "echo": EchoPlugin,
}

__all__ = ["BUILTIN_PLUGINS", "EchoPlugin"]