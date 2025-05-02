import abc
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

class PluginManager:
    """
    Discovers and manages plugins in the nagatha_assistant.plugins package.
    """

    def __init__(self, plugin_package: str = "nagatha_assistant.plugins"):
        self.plugin_package = plugin_package
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