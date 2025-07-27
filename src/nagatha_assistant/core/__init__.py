# Core components for Nagatha Assistant

from .event import (
    Event, 
    EventPriority, 
    StandardEventTypes,
    create_system_event,
    create_agent_event,
    create_mcp_event
)

from .event_bus import (
    EventBus,
    EventBusError,
    get_event_bus,
    ensure_event_bus_started,
    shutdown_event_bus
)

from .plugin_manager import (
    get_plugin_manager,
    shutdown_plugin_manager
)

from .plugin import (
    BasePlugin,
    SimplePlugin,
    PluginConfig,
    PluginCommand,
    PluginState,
    PluginEventTypes
)

from .celery_app import (
    celery_app,
    get_celery_app,
    configure_celery,
    add_periodic_task,
    remove_periodic_task,
    get_beat_schedule,
    clear_beat_schedule
)

from .scheduler import (
    TaskScheduler,
    get_scheduler,
    schedule_task,
    schedule_one_time,
    schedule_recurring,
    cancel_task,
    list_scheduled_tasks
)


async def initialize_plugin_system():
    """Initialize the plugin system with built-in plugins."""
    from ..plugins import BUILTIN_PLUGINS
    
    plugin_manager = get_plugin_manager()
    
    # Register built-in plugin classes
    for name, plugin_class in BUILTIN_PLUGINS.items():
        plugin_manager.register_plugin_class(name, plugin_class)
    
    # Load and start built-in plugins
    configs = {}
    for name, plugin_class in BUILTIN_PLUGINS.items():
        # Get config from plugin class or create default
        if hasattr(plugin_class, 'PLUGIN_CONFIG'):
            config_dict = plugin_class.PLUGIN_CONFIG
        else:
            config_dict = {
                "name": getattr(plugin_class, 'PLUGIN_NAME', name),
                "version": getattr(plugin_class, 'PLUGIN_VERSION', '1.0.0'),
                "description": plugin_class.__doc__ or "",
                "dependencies": [],
                "config": {},
                "enabled": True,
                "priority": 100
            }
        
        configs[name] = PluginConfig(**config_dict)
    
    # Load and start all built-in plugins
    await plugin_manager.load_and_start_all(configs)


__all__ = [
    # Event system
    'Event',
    'EventPriority', 
    'StandardEventTypes',
    'create_system_event',
    'create_agent_event', 
    'create_mcp_event',
    'EventBus',
    'EventBusError',
    'get_event_bus',
    'ensure_event_bus_started',
    'shutdown_event_bus',
    # Plugin system
    'get_plugin_manager',
    'shutdown_plugin_manager',
    'BasePlugin',
    'SimplePlugin',
    'PluginConfig',
    'PluginCommand',
    'PluginState',
    'PluginEventTypes',
    'initialize_plugin_system',
    # Celery system
    'celery_app',
    'get_celery_app',
    'configure_celery',
    'add_periodic_task',
    'remove_periodic_task',
    'get_beat_schedule',
    'clear_beat_schedule',
    'TaskScheduler',
    'get_scheduler',
    'schedule_task',
    'schedule_one_time',
    'schedule_recurring',
    'cancel_task',
    'list_scheduled_tasks'
]