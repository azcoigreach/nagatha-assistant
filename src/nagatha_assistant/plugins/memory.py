"""
Memory Plugin for Nagatha Assistant.

This plugin exposes memory system functionality as commands that can be called
during AI conversations, allowing Nagatha to store and retrieve information
across sessions.
"""

import json
from typing import Any, Dict, List, Optional, Union

from nagatha_assistant.core.plugin import BasePlugin, PluginCommand, PluginConfig
from nagatha_assistant.core.memory import ensure_memory_manager_started
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()


class MemoryPlugin(BasePlugin):
    """Plugin that provides memory functionality to the AI agent."""
    
    PLUGIN_NAME = "memory"
    PLUGIN_VERSION = "1.0.0"
    
    def __init__(self, config: PluginConfig):
        """Initialize the memory plugin."""
        super().__init__(config)
        self._memory_manager = None
    
    async def initialize(self) -> None:
        """Initialize the plugin."""
        await super().initialize()
        # Ensure memory manager is started
        self._memory_manager = await ensure_memory_manager_started()
        logger.info("Memory plugin initialized")
    
    async def start(self) -> None:
        """Start the plugin and register commands."""
        await super().start()
        
        # Register memory commands
        self._register_memory_commands()
        logger.info("Memory plugin started and commands registered")
    
    async def stop(self) -> None:
        """Stop the plugin and clean up resources."""
        await super().stop()
        logger.info("Memory plugin stopped")
    
    def _register_memory_commands(self) -> None:
        """Register all memory-related commands."""
        
        # Get plugin manager for command registration
        from nagatha_assistant.core.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        
        # General memory operations
        plugin_manager.register_command(PluginCommand(
            name="memory_set",
            description="Store a value in memory with optional TTL",
            handler=self._memory_set,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "section": {"type": "string", "description": "Memory section (user_preferences, session_state, facts, temporary, command_history)"},
                    "key": {"type": "string", "description": "Key to store the value under"},
                    "value": {"description": "Value to store (any type)"},
                    "session_id": {"type": "integer", "description": "Optional session ID for session-scoped storage"},
                    "ttl_seconds": {"type": "integer", "description": "Time to live in seconds (for temporary data)"}
                },
                "required": ["section", "key", "value"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_get",
            description="Retrieve a value from memory",
            handler=self._memory_get,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "section": {"type": "string", "description": "Memory section"},
                    "key": {"type": "string", "description": "Key to retrieve"},
                    "session_id": {"type": "integer", "description": "Optional session ID for session-scoped retrieval"},
                    "default": {"description": "Default value if key not found"}
                },
                "required": ["section", "key"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_search",
            description="Search for entries in a memory section",
            handler=self._memory_search,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "section": {"type": "string", "description": "Memory section to search"},
                    "query": {"type": "string", "description": "Search query"},
                    "session_id": {"type": "integer", "description": "Optional session ID to filter by"}
                },
                "required": ["section", "query"]
            }
        ))
        
        # User preferences
        plugin_manager.register_command(PluginCommand(
            name="memory_set_user_preference",
            description="Set a user preference (permanent storage)",
            handler=self._set_user_preference,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference key"},
                    "value": {"description": "Preference value"}
                },
                "required": ["key", "value"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_get_user_preference",
            description="Get a user preference",
            handler=self._get_user_preference,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference key"},
                    "default": {"description": "Default value if not found"}
                },
                "required": ["key"]
            }
        ))
        
        # Session state
        plugin_manager.register_command(PluginCommand(
            name="memory_set_session_state",
            description="Set session-specific state",
            handler=self._set_session_state,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"},
                    "key": {"type": "string", "description": "State key"},
                    "value": {"description": "State value"}
                },
                "required": ["session_id", "key", "value"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_get_session_state",
            description="Get session-specific state",
            handler=self._get_session_state,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"},
                    "key": {"type": "string", "description": "State key"},
                    "default": {"description": "Default value if not found"}
                },
                "required": ["session_id", "key"]
            }
        ))
        
        # Facts storage
        plugin_manager.register_command(PluginCommand(
            name="memory_store_fact",
            description="Store a long-term fact",
            handler=self._store_fact,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Fact key/identifier"},
                    "fact": {"type": "string", "description": "The fact to store"},
                    "source": {"type": "string", "description": "Optional source of the fact"}
                },
                "required": ["key", "fact"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_get_fact",
            description="Retrieve a stored fact",
            handler=self._get_fact,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Fact key/identifier"}
                },
                "required": ["key"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_search_facts",
            description="Search for facts containing a query",
            handler=self._search_facts,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        ))
        
        # Command history
        plugin_manager.register_command(PluginCommand(
            name="memory_add_command_history",
            description="Add a command to the command history",
            handler=self._add_command_history,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command executed"},
                    "response": {"type": "string", "description": "Optional response/result"},
                    "session_id": {"type": "integer", "description": "Optional session ID"}
                },
                "required": ["command"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_get_command_history",
            description="Get command history",
            handler=self._get_command_history,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Optional session ID to filter by"},
                    "limit": {"type": "integer", "description": "Maximum number of entries to return", "default": 100}
                }
            }
        ))
        
        # Temporary data
        plugin_manager.register_command(PluginCommand(
            name="memory_set_temporary",
            description="Store temporary data with TTL",
            handler=self._set_temporary,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key for temporary data"},
                    "value": {"description": "Value to store"},
                    "ttl_seconds": {"type": "integer", "description": "Time to live in seconds", "default": 3600}
                },
                "required": ["key", "value"]
            }
        ))
        
        plugin_manager.register_command(PluginCommand(
            name="memory_get_temporary",
            description="Get temporary data",
            handler=self._get_temporary,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key for temporary data"},
                    "default": {"description": "Default value if not found"}
                },
                "required": ["key"]
            }
        ))
        
        # List operations
        plugin_manager.register_command(PluginCommand(
            name="memory_list_keys",
            description="List keys in a memory section",
            handler=self._list_keys,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {
                    "section": {"type": "string", "description": "Memory section"},
                    "session_id": {"type": "integer", "description": "Optional session ID to filter by"},
                    "pattern": {"type": "string", "description": "Optional pattern to filter keys"}
                },
                "required": ["section"]
            }
        ))
        
        # Stats
        plugin_manager.register_command(PluginCommand(
            name="memory_get_stats",
            description="Get memory usage statistics",
            handler=self._get_stats,
            plugin_name=self.name,
            parameters={
                "type": "object",
                "properties": {}
            }
        ))
    
    # Command handlers
    async def _memory_set(self, section: str, key: str, value: Any, 
                         session_id: Optional[int] = None, ttl_seconds: Optional[int] = None) -> str:
        """Handle memory_set command."""
        await self._memory_manager.set(section, key, value, session_id, ttl_seconds)
        return f"Stored value in {section}/{key}" + (f" (session: {session_id})" if session_id else "")
    
    async def _memory_get(self, section: str, key: str, 
                         session_id: Optional[int] = None, default: Any = None) -> Any:
        """Handle memory_get command."""
        value = await self._memory_manager.get(section, key, session_id, default)
        return value
    
    async def _memory_search(self, section: str, query: str, 
                            session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Handle memory_search command."""
        results = await self._memory_manager.search(section, query, session_id)
        return results
    
    async def _set_user_preference(self, key: str, value: Any) -> str:
        """Handle memory_set_user_preference command."""
        await self._memory_manager.set_user_preference(key, value)
        return f"Set user preference: {key}"
    
    async def _get_user_preference(self, key: str, default: Any = None) -> Any:
        """Handle memory_get_user_preference command."""
        value = await self._memory_manager.get_user_preference(key, default)
        return value
    
    async def _set_session_state(self, session_id: int, key: str, value: Any) -> str:
        """Handle memory_set_session_state command."""
        await self._memory_manager.set_session_state(session_id, key, value)
        return f"Set session state for session {session_id}: {key}"
    
    async def _get_session_state(self, session_id: int, key: str, default: Any = None) -> Any:
        """Handle memory_get_session_state command."""
        value = await self._memory_manager.get_session_state(session_id, key, default)
        return value
    
    async def _store_fact(self, key: str, fact: str, source: Optional[str] = None) -> str:
        """Handle memory_store_fact command."""
        await self._memory_manager.store_fact(key, fact, source)
        return f"Stored fact: {key}"
    
    async def _get_fact(self, key: str) -> Optional[Dict[str, Any]]:
        """Handle memory_get_fact command."""
        fact = await self._memory_manager.get_fact(key)
        return fact
    
    async def _search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Handle memory_search_facts command."""
        results = await self._memory_manager.search_facts(query)
        return results
    
    async def _add_command_history(self, command: str, response: Optional[str] = None, 
                                  session_id: Optional[int] = None) -> str:
        """Handle memory_add_command_history command."""
        await self._memory_manager.add_command_to_history(command, response, session_id)
        return f"Added command to history: {command}"
    
    async def _get_command_history(self, session_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Handle memory_get_command_history command."""
        history = await self._memory_manager.get_command_history(session_id, limit)
        return history
    
    async def _set_temporary(self, key: str, value: Any, ttl_seconds: int = 3600) -> str:
        """Handle memory_set_temporary command."""
        await self._memory_manager.set_temporary(key, value, ttl_seconds)
        return f"Stored temporary data: {key} (TTL: {ttl_seconds}s)"
    
    async def _get_temporary(self, key: str, default: Any = None) -> Any:
        """Handle memory_get_temporary command."""
        value = await self._memory_manager.get_temporary(key, default)
        return value
    
    async def _list_keys(self, section: str, session_id: Optional[int] = None, 
                        pattern: Optional[str] = None) -> List[str]:
        """Handle memory_list_keys command."""
        keys = await self._memory_manager.list_keys(section, session_id, pattern)
        return keys
    
    async def _get_stats(self) -> Dict[str, Any]:
        """Handle memory_get_stats command."""
        stats = await self._memory_manager.get_storage_stats()
        return stats


# Plugin configuration
PLUGIN_CONFIG = {
    "name": "memory",
    "description": "Provides memory system functionality to the AI agent",
    "version": "1.0.0",
    "enabled": True,
    "dependencies": []
}