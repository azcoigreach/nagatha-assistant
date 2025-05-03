import abc
import logging
from typing import Any, Dict, List

class Plugin(abc.ABC):
    """
    Base Plugin class for Nagatha Assistant.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        Unique plugin name.
        """
        ...

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """
        Plugin version.
        """
        ...

    @abc.abstractmethod
    async def setup(self, config: Dict[str, Any]) -> None:
        """
        Initialize plugin with provided configuration.
        """
        ...

    @abc.abstractmethod
    async def teardown(self) -> None:
        """
        Clean up plugin resources before shutdown.
        """
        ...

    # ------------------------------------------------------------------
    # Function-calling support (OpenAI tools / functions API)
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def function_specs(self) -> List[Dict[str, Any]]:
        """Return JSON-schema specs describing callable plugin functions.

        The structure must conform to the `functions` parameter expected by
        OpenAI chat completions.
        """

    @abc.abstractmethod
    async def call(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute the function *name* with given *arguments* and return a string result."""

class PluginManager:
    """
    Discovers and manages plugins in the nagatha_assistant.plugins package.
    """

    def __init__(self, plugin_package: str = "nagatha_assistant.plugins"):
        self.plugin_package = plugin_package
        self._log = logging.getLogger(__name__)
        self.plugins: List[Plugin] = []

    async def discover(self) -> None:
        """
        Discover and instantiate all Plugin subclasses in the plugin package.
        """
        import importlib
        import pkgutil

        pkg = importlib.import_module(self.plugin_package)
        for finder, name, ispkg in pkgutil.iter_modules(pkg.__path__):
            module_name = f"{self.plugin_package}.{name}"
            module = importlib.import_module(module_name)
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
                    instance = obj()
                    self.plugins.append(instance)
                    self._log.info("Discovered plugin '%s' v%s", instance.name, instance.version)

        # Build lookup table for fast routing
        self._function_map = {}
        for plugin in self.plugins:
            for spec in plugin.function_specs():
                self._function_map[spec["name"]] = plugin

    async def setup_all(self, config: Dict[str, Any]) -> None:
        """
        Run setup on all discovered plugins.
        """
        for plugin in self.plugins:
            await plugin.setup(config)

    async def teardown_all(self) -> None:
        """
        Run teardown on all discovered plugins.
        """
        for plugin in self.plugins:
            await plugin.teardown()

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------

    def function_specs(self) -> List[Dict[str, Any]]:
        """Aggregate all plugin function specs."""

        specs: List[Dict[str, Any]] = []
        for plugin in self.plugins:
            specs.extend(plugin.function_specs())
        return specs

    async def call_function(self, name: str, arguments: Dict[str, Any]) -> str:
        plugin = self._function_map.get(name)
        if not plugin:
            raise ValueError(f"Function '{name}' not found in any plugin")
        self._log.debug("Routing function call '%s' with args=%s", name, arguments)
        result = await plugin.call(name, arguments)
        self._log.info("Plugin '%s' executed function '%s'", plugin.name, name)
        return result