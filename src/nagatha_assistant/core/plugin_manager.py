"""
Plugin Manager for Nagatha Assistant.

This module manages the plugin lifecycle, dependency resolution, discovery,
and command registration for the plugin system.
"""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Callable, Awaitable

from .plugin import (
    BasePlugin, PluginConfig, PluginCommand, PluginState, PluginError, PluginEventTypes
)
from .event import Event, create_system_event, EventPriority
from .event_bus import get_event_bus

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages the plugin system for Nagatha Assistant.
    
    Features:
    - Plugin discovery from multiple sources
    - Dependency resolution and ordering
    - Lifecycle management (load, init, start, stop)
    - Command registration and routing
    - Configuration management
    - Event integration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the plugin manager.
        
        Args:
            config: Plugin manager configuration
        """
        self.config = config or {}
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}
        self._commands: Dict[str, PluginCommand] = {}
        self._dependency_graph: Dict[str, Set[str]] = {}
        self._discovery_paths: List[Path] = []
        self._event_bus = get_event_bus()
        self._lock = threading.RLock()
        self._startup_order: List[str] = []
        self._initialized: bool = False
        
        # Setup default discovery paths
        self._setup_discovery_paths()
        
        # Subscribe to system events
        self._setup_event_handlers()
    
    def _setup_discovery_paths(self) -> None:
        """Setup default plugin discovery paths."""
        # Built-in plugins directory
        builtin_path = Path(__file__).parent.parent / "plugins"
        self._discovery_paths.append(builtin_path)
        
        # User plugins directory from config or environment
        user_plugins_dir = (
            self.config.get("user_plugins_dir") or 
            os.getenv("NAGATHA_PLUGINS_DIR") or 
            "~/.nagatha/plugins"
        )
        user_path = Path(user_plugins_dir).expanduser()
        self._discovery_paths.append(user_path)
        
        # Additional paths from config
        for path in self.config.get("additional_paths", []):
            self._discovery_paths.append(Path(path))
        
        logger.debug(f"Plugin discovery paths: {[str(p) for p in self._discovery_paths]}")
    
    def _setup_event_handlers(self) -> None:
        """Setup event handlers for plugin manager."""
        # Listen for system shutdown to cleanup plugins
        self._event_bus.subscribe(
            "system.shutdown", 
            self._handle_system_shutdown
        )
    
    async def _handle_system_shutdown(self, event: Event) -> None:
        """Handle system shutdown by stopping all plugins."""
        await self.stop_all_plugins()
    
    def add_discovery_path(self, path: Path) -> None:
        """
        Add a plugin discovery path.
        
        Args:
            path: Path to search for plugins
        """
        with self._lock:
            if path not in self._discovery_paths:
                self._discovery_paths.append(path)
                logger.debug(f"Added discovery path: {path}")
    
    def discover_plugins(self) -> Dict[str, PluginConfig]:
        """
        Discover plugins from all configured paths.
        
        Returns:
            Dictionary mapping plugin names to their configurations
        """
        discovered = {}
        
        for search_path in self._discovery_paths:
            if not search_path.exists():
                logger.debug(f"Discovery path does not exist: {search_path}")
                continue
                
            try:
                plugins = self._discover_plugins_in_path(search_path)
                discovered.update(plugins)
                logger.debug(f"Discovered {len(plugins)} plugins in {search_path}")
            except Exception as e:
                logger.exception(f"Error discovering plugins in {search_path}: {e}")
        
        logger.info(f"Total discovered plugins: {len(discovered)}")
        return discovered
    
    def _discover_plugins_in_path(self, path: Path) -> Dict[str, PluginConfig]:
        """
        Discover plugins in a specific path.
        
        Args:
            path: Path to search
            
        Returns:
            Dictionary of discovered plugin configurations
        """
        plugins = {}
        
        # Look for Python files and packages
        for item in path.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                try:
                    config = self._load_plugin_config_from_file(item)
                    if config:
                        plugins[config.name] = config
                except Exception as e:
                    logger.exception(f"Error loading plugin from {item}: {e}")
            
            elif item.is_dir() and not item.name.startswith("_"):
                # Check for __init__.py or plugin.py
                init_file = item / "__init__.py"
                plugin_file = item / "plugin.py"
                
                target_file = init_file if init_file.exists() else plugin_file
                if target_file.exists():
                    try:
                        config = self._load_plugin_config_from_file(target_file)
                        if config:
                            plugins[config.name] = config
                    except Exception as e:
                        logger.exception(f"Error loading plugin from {target_file}: {e}")
        
        return plugins
    
    def _load_plugin_config_from_file(self, file_path: Path) -> Optional[PluginConfig]:
        """
        Load plugin configuration from a Python file.
        
        Args:
            file_path: Path to the plugin file
            
        Returns:
            Plugin configuration if found, None otherwise
        """
        try:
            # Import the module dynamically
            spec = importlib.util.spec_from_file_location("temp_plugin", file_path)
            if not spec or not spec.loader:
                return None
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for plugin configuration
            if hasattr(module, "PLUGIN_CONFIG"):
                config_dict = module.PLUGIN_CONFIG
                return PluginConfig(**config_dict)
            
            # Look for plugin class and extract config
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (inspect.isclass(item) and 
                    issubclass(item, BasePlugin) and 
                    item != BasePlugin):
                    
                    # Create default config from class
                    name = getattr(item, "PLUGIN_NAME", item.__name__.lower())
                    return PluginConfig(
                        name=name,
                        description=item.__doc__ or "",
                        version=getattr(item, "PLUGIN_VERSION", "1.0.0")
                    )
            
        except Exception as e:
            logger.exception(f"Error loading plugin config from {file_path}: {e}")
        
        return None
    
    def register_plugin_class(self, name: str, plugin_class: Type[BasePlugin]) -> None:
        """
        Manually register a plugin class.
        
        Args:
            name: Plugin name
            plugin_class: Plugin class to register
        """
        with self._lock:
            self._plugin_classes[name] = plugin_class
            logger.debug(f"Registered plugin class: {name}")
    
    async def load_plugin(self, config: PluginConfig) -> bool:
        """
        Load and instantiate a plugin.
        
        Args:
            config: Plugin configuration
            
        Returns:
            True if loaded successfully, False otherwise
        """
        with self._lock:
            if config.name in self._plugins:
                logger.warning(f"Plugin {config.name} is already loaded")
                return False
        
        try:
            # Get plugin class
            plugin_class = self._plugin_classes.get(config.name)
            if not plugin_class:
                plugin_class = await self._load_plugin_class(config)
                if not plugin_class:
                    raise PluginError(f"Could not find plugin class for {config.name}")
            
            # Instantiate plugin
            plugin = plugin_class(config)
            
            with self._lock:
                self._plugins[config.name] = plugin
                self._dependency_graph[config.name] = set(config.dependencies)
            
            await plugin._set_state(PluginState.LOADED)
            
            # Publish plugin loaded event
            try:
                event = create_system_event(
                    PluginEventTypes.PLUGIN_LOADED,
                    {"plugin_name": config.name, "plugin_version": config.version},
                    source="plugin_manager"
                )
                await self._event_bus.publish(event)
            except Exception as e:
                logger.debug(f"Could not publish plugin loaded event: {e}")
            
            logger.info(f"Loaded plugin: {config.name} v{config.version}")
            return True
            
        except Exception as e:
            logger.exception(f"Error loading plugin {config.name}: {e}")
            await self._set_plugin_error_state(config.name, str(e))
            return False
    
    async def _load_plugin_class(self, config: PluginConfig) -> Optional[Type[BasePlugin]]:
        """
        Dynamically load a plugin class from discovery paths.
        
        Args:
            config: Plugin configuration
            
        Returns:
            Plugin class if found, None otherwise
        """
        for search_path in self._discovery_paths:
            if not search_path.exists():
                continue
                
            # Try loading from file or package
            plugin_file = search_path / f"{config.name}.py"
            plugin_dir = search_path / config.name
            
            for target_path in [plugin_file, plugin_dir / "__init__.py", plugin_dir / "plugin.py"]:
                if target_path.exists():
                    try:
                        spec = importlib.util.spec_from_file_location(
                            f"nagatha_plugin_{config.name}", 
                            target_path
                        )
                        if not spec or not spec.loader:
                            continue
                            
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Find plugin class
                        for item_name in dir(module):
                            item = getattr(module, item_name)
                            if (inspect.isclass(item) and 
                                issubclass(item, BasePlugin) and 
                                item != BasePlugin):
                                
                                self._plugin_classes[config.name] = item
                                return item
                                
                    except Exception as e:
                        logger.exception(f"Error loading plugin class from {target_path}: {e}")
        
        return None
    
    async def initialize_plugin(self, name: str) -> bool:
        """
        Initialize a loaded plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if initialized successfully, False otherwise
        """
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                logger.error(f"Plugin {name} not found")
                return False
            
            if plugin.state != PluginState.LOADED:
                logger.warning(f"Plugin {name} is not in loaded state (current: {plugin.state})")
                return False
        
        try:
            await plugin.initialize()
            await plugin._set_state(PluginState.INITIALIZED)
            logger.info(f"Initialized plugin: {name}")
            return True
            
        except Exception as e:
            logger.exception(f"Error initializing plugin {name}: {e}")
            await self._set_plugin_error_state(name, str(e))
            return False
    
    async def start_plugin(self, name: str) -> bool:
        """
        Start an initialized plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if started successfully, False otherwise
        """
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                logger.error(f"Plugin {name} not found")
                return False
            
            if plugin.state != PluginState.INITIALIZED:
                logger.warning(f"Plugin {name} is not initialized (current: {plugin.state})")
                return False
        
        try:
            await plugin.start()
            await plugin._set_state(PluginState.STARTED)
            logger.info(f"Started plugin: {name}")
            return True
            
        except Exception as e:
            logger.exception(f"Error starting plugin {name}: {e}")
            await self._set_plugin_error_state(name, str(e))
            return False
    
    async def stop_plugin(self, name: str) -> bool:
        """
        Stop a running plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if stopped successfully, False otherwise
        """
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                logger.error(f"Plugin {name} not found")
                return False
        
        try:
            await plugin.stop()
            await plugin._set_state(PluginState.STOPPED)
            
            # Unregister commands
            commands_to_remove = [
                cmd_name for cmd_name, cmd in self._commands.items() 
                if cmd.plugin_name == name
            ]
            for cmd_name in commands_to_remove:
                del self._commands[cmd_name]
            
            logger.info(f"Stopped plugin: {name}")
            return True
            
        except Exception as e:
            logger.exception(f"Error stopping plugin {name}: {e}")
            await self._set_plugin_error_state(name, str(e))
            return False
    
    async def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin completely.
        
        Args:
            name: Plugin name
            
        Returns:
            True if unloaded successfully, False otherwise
        """
        # Stop plugin first if running
        plugin = self._plugins.get(name)
        if plugin and plugin.state == PluginState.STARTED:
            await self.stop_plugin(name)
        
        with self._lock:
            if name in self._plugins:
                del self._plugins[name]
            if name in self._dependency_graph:
                del self._dependency_graph[name]
        
        logger.info(f"Unloaded plugin: {name}")
        return True
    
    def resolve_dependencies(self, plugins: Dict[str, PluginConfig]) -> List[str]:
        """
        Resolve plugin dependencies and return startup order.
        
        Args:
            plugins: Dictionary of plugin configurations
            
        Returns:
            List of plugin names in dependency order
            
        Raises:
            PluginError: If circular dependencies are detected
        """
        # Build dependency graph
        graph = {}
        for name, config in plugins.items():
            graph[name] = set(config.dependencies)
        
        # Topological sort
        result = []
        visited = set()
        temp_visited = set()
        
        def visit(node: str) -> None:
            if node in temp_visited:
                raise PluginError(f"Circular dependency detected involving {node}")
            if node in visited:
                return
            
            temp_visited.add(node)
            for dependency in graph.get(node, set()):
                if dependency in graph:  # Only visit if dependency is available
                    visit(dependency)
            temp_visited.remove(node)
            visited.add(node)
            result.append(node)
        
        for plugin_name in graph:
            if plugin_name not in visited:
                visit(plugin_name)
        
        return result
    
    async def load_and_start_all(self, configs: Optional[Dict[str, PluginConfig]] = None) -> Dict[str, bool]:
        """
        Load and start all plugins with dependency resolution.
        
        Args:
            configs: Plugin configurations (will discover if None)
            
        Returns:
            Dictionary mapping plugin names to success status
        """
        if configs is None:
            configs = self.discover_plugins()
        
        # Filter enabled plugins
        enabled_configs = {
            name: config for name, config in configs.items() 
            if config.enabled
        }
        
        if not enabled_configs:
            logger.info("No enabled plugins found")
            return {}
        
        # Resolve dependencies
        try:
            startup_order = self.resolve_dependencies(enabled_configs)
            self._startup_order = startup_order
        except PluginError as e:
            logger.error(f"Dependency resolution failed: {e}")
            return {}
        
        results = {}
        
        # Load, initialize, and start plugins in dependency order
        for plugin_name in startup_order:
            config = enabled_configs[plugin_name]
            
            success = (
                await self.load_plugin(config) and
                await self.initialize_plugin(plugin_name) and
                await self.start_plugin(plugin_name)
            )
            
            results[plugin_name] = success
            
            if not success:
                logger.error(f"Failed to start plugin {plugin_name}")
            else:
                logger.info(f"Successfully started plugin {plugin_name}")
        
        started_count = sum(results.values())
        logger.info(f"Started {started_count}/{len(enabled_configs)} plugins")
        
        return results
    
    async def stop_all_plugins(self) -> None:
        """Stop all running plugins in reverse startup order."""
        if not self._startup_order:
            return
        
        # Stop in reverse order to respect dependencies
        for plugin_name in reversed(self._startup_order):
            if plugin_name in self._plugins:
                await self.stop_plugin(plugin_name)
    
    def register_command(self, command: PluginCommand) -> bool:
        """
        Register a command from a plugin.
        
        Args:
            command: Command to register
            
        Returns:
            True if registered successfully, False if name conflict
        """
        with self._lock:
            if command.name in self._commands:
                logger.warning(f"Command {command.name} already registered")
                return False
            
            self._commands[command.name] = command
        
        # Notify plugin of registration
        plugin = self._plugins.get(command.plugin_name)
        if plugin:
            plugin.register_command(command)
        
        logger.debug(f"Registered command: {command.name} from plugin {command.plugin_name}")
        return True
    
    def unregister_command(self, command_name: str) -> bool:
        """
        Unregister a command.
        
        Args:
            command_name: Name of command to unregister
            
        Returns:
            True if unregistered successfully
        """
        with self._lock:
            command = self._commands.pop(command_name, None)
            if not command:
                return False
        
        # Notify plugin of unregistration
        plugin = self._plugins.get(command.plugin_name)
        if plugin:
            plugin.unregister_command(command_name)
        
        logger.debug(f"Unregistered command: {command_name}")
        return True
    
    async def execute_command(self, command_name: str, *args, **kwargs) -> Any:
        """
        Execute a registered command.
        
        Args:
            command_name: Name of command to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Command result
            
        Raises:
            PluginError: If command not found or execution fails
        """
        command = self._commands.get(command_name)
        if not command:
            raise PluginError(f"Command {command_name} not found")
        
        try:
            result = await command.handler(*args, **kwargs)
            return result
        except Exception as e:
            logger.exception(f"Error executing command {command_name}: {e}")
            raise PluginError(f"Command execution failed: {e}")
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """
        Get a plugin instance by name.
        
        Args:
            name: Plugin name to retrieve
            
        Returns:
            Plugin instance if found, None otherwise
        """
        with self._lock:
            return self._plugins.get(name)
    
    async def initialize(self) -> None:
        """
        Initialize the plugin manager by discovering and loading enabled plugins.
        
        This method discovers all available plugins, loads enabled ones,
        and marks the plugin manager as initialized.
        """
        if self._initialized:
            logger.debug("Plugin manager already initialized")
            return
        
        try:
            # Register built-in plugins manually to avoid import issues
            self._register_builtin_plugins()
            
            # Discover and load plugins
            configs = self.discover_plugins()
            
            # Add built-in plugin configs if they weren't discovered
            builtin_configs = self._get_builtin_plugin_configs()
            for name, config in builtin_configs.items():
                if name not in configs:
                    configs[name] = config
            
            results = await self.load_and_start_all(configs)
            
            # Mark as initialized
            self._initialized = True
            
            started_count = sum(results.values())
            total_count = len([c for c in configs.values() if c.enabled])
            logger.info(f"Plugin manager initialized with {started_count}/{total_count} enabled plugins started")
            
        except Exception as e:
            logger.exception(f"Error initializing plugin manager: {e}")
            # Don't set _initialized to True if there was an error
            raise
    
    def _register_builtin_plugins(self) -> None:
        """Register built-in plugin classes to avoid dynamic import issues."""
        try:
            # Import and register Discord bot plugin
            from ..plugins.discord_bot import DiscordBotPlugin
            self.register_plugin_class("discord_bot", DiscordBotPlugin)
            logger.debug("Registered built-in Discord bot plugin")
        except ImportError as e:
            logger.debug(f"Could not import Discord bot plugin: {e}")
        
        try:
            # Import and register other built-in plugins
            from ..plugins.echo_plugin import EchoPlugin
            self.register_plugin_class("echo_plugin", EchoPlugin)
            logger.debug("Registered built-in Echo plugin")
        except ImportError as e:
            logger.debug(f"Could not import Echo plugin: {e}")
        
        try:
            from ..plugins.memory import MemoryPlugin
            self.register_plugin_class("memory", MemoryPlugin)
            logger.debug("Registered built-in Memory plugin")
        except ImportError as e:
            logger.debug(f"Could not import Memory plugin: {e}")
    
    def _get_builtin_plugin_configs(self) -> Dict[str, PluginConfig]:
        """Get configurations for built-in plugins."""
        builtin_configs = {}
        
        # Discord bot plugin config
        builtin_configs["discord_bot"] = PluginConfig(
            name="discord_bot",
            version="1.0.0", 
            description="Discord bot integration for Nagatha Assistant",
            author="Nagatha Assistant",
            enabled=True,
            config={
                "auto_start": False,
                "command_prefix": "!",
            }
        )
        
        return builtin_configs

    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all plugins.
        
        Returns:
            Dictionary mapping plugin names to status info
        """
        with self._lock:
            return {
                name: {
                    "name": plugin.name,
                    "version": plugin.version,
                    "state": plugin.state.value,
                    "config": plugin.config.__dict__,
                    "commands": list(plugin.get_registered_commands())
                }
                for name, plugin in self._plugins.items()
            }
    
    def get_available_commands(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all available commands.
        
        Returns:
            Dictionary mapping command names to command info
        """
        with self._lock:
            return {
                name: {
                    "name": cmd.name,
                    "description": cmd.description,
                    "plugin": cmd.plugin_name,
                    "parameters": cmd.parameters
                }
                for name, cmd in self._commands.items()
            }
    
    async def _set_plugin_error_state(self, name: str, error_message: str) -> None:
        """Set a plugin to error state and publish error event."""
        plugin = self._plugins.get(name)
        if plugin:
            await plugin._set_state(PluginState.ERROR)
            
            try:
                event = create_system_event(
                    PluginEventTypes.PLUGIN_ERROR,
                    {"plugin_name": name, "error": error_message},
                    EventPriority.HIGH,
                    source="plugin_manager"
                )
                await self._event_bus.publish(event)
            except Exception as e:
                logger.debug(f"Could not publish plugin error event: {e}")


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None
_manager_lock = threading.Lock()


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance (singleton pattern)."""
    global _plugin_manager
    
    if _plugin_manager is None:
        with _manager_lock:
            if _plugin_manager is None:
                _plugin_manager = PluginManager()
    
    return _plugin_manager


async def shutdown_plugin_manager() -> None:
    """Shutdown the global plugin manager."""
    global _plugin_manager
    
    if _plugin_manager is not None:
        await _plugin_manager.stop_all_plugins()
        with _manager_lock:
            _plugin_manager = None