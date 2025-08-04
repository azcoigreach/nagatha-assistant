"""
Conversation Memory Plugin for Nagatha Assistant.

This plugin provides functions for managing conversation context, short-term memory,
and session state that the AI can use to maintain better conversation continuity.
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from nagatha_assistant.core.memory import get_memory_manager, ensure_memory_manager_started
from nagatha_assistant.core.short_term_memory import get_short_term_memory, ensure_short_term_memory_started
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()


class ConversationMemoryPlugin:
    """
    Plugin for managing conversation memory and context.
    
    This plugin provides functions that allow the AI to:
    - Access recent conversation context
    - Search conversation history
    - Manage session state
    - Store and retrieve temporary information
    - Get conversation statistics
    """
    
    def __init__(self):
        self.memory_manager = None
        self.short_term_memory = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the plugin."""
        if self._initialized:
            return
        
        try:
            self.memory_manager = await ensure_memory_manager_started()
            self.short_term_memory = await ensure_short_term_memory_started()
            self._initialized = True
            logger.info("ConversationMemoryPlugin initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ConversationMemoryPlugin: {e}")
    
    async def get_recent_context(self, session_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent conversation context for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
        
        Returns:
            List of recent conversation messages with metadata
        """
        await self.initialize()
        
        try:
            context_entries = await self.memory_manager.get_conversation_context(session_id, limit)
            
            # Format for AI consumption
            formatted_context = []
            for entry in context_entries:
                value = entry.get("value", {})
                formatted_context.append({
                    "role": value.get("role", "user"),
                    "content": value.get("content", ""),
                    "timestamp": value.get("timestamp", ""),
                    "message_id": value.get("message_id"),
                    "metadata": value.get("metadata", {})
                })
            
            return formatted_context
            
        except Exception as e:
            logger.error(f"Error getting recent context: {e}")
            return []
    
    async def search_conversation_history(self, session_id: int, query: str) -> List[Dict[str, Any]]:
        """
        Search conversation history for specific content.
        
        Args:
            session_id: Session identifier
            query: Search query
        
        Returns:
            List of matching conversation entries
        """
        await self.initialize()
        
        try:
            results = await self.memory_manager.search_conversation_context(session_id, query)
            
            # Format for AI consumption
            formatted_results = []
            for result in results:
                value = result.get("value", {})
                formatted_results.append({
                    "role": value.get("role", "user"),
                    "content": value.get("content", ""),
                    "timestamp": value.get("timestamp", ""),
                    "message_id": value.get("message_id"),
                    "relevance_score": result.get("relevance_score", 0.0)
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching conversation history: {e}")
            return []
    
    async def get_session_state(self, session_id: int) -> Dict[str, Any]:
        """
        Get current session state.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Current session state information
        """
        await self.initialize()
        
        try:
            if self.short_term_memory:
                state = await self.short_term_memory.get_session_state(session_id)
                if state:
                    return {
                        "session_id": state.session_id,
                        "current_topic": state.current_topic,
                        "current_task": state.current_task,
                        "user_intent": state.user_intent,
                        "conversation_mode": state.conversation_mode,
                        "last_activity": state.last_activity.isoformat(),
                        "context_window_size": state.context_window_size
                    }
            
            # Fallback to long-term memory
            state_data = {}
            for key in ["current_topic", "current_task", "user_intent", "conversation_mode"]:
                value = await self.memory_manager.get_session_state(session_id, key)
                if value is not None:
                    state_data[key] = value
            
            return state_data
            
        except Exception as e:
            logger.error(f"Error getting session state: {e}")
            return {}
    
    async def update_session_state(self, session_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update session state.
        
        Args:
            session_id: Session identifier
            updates: Dictionary of state updates
        
        Returns:
            True if successful, False otherwise
        """
        await self.initialize()
        
        try:
            # Update in both short-term and long-term memory
            if self.short_term_memory:
                await self.short_term_memory.update_session_state(session_id, updates)
            
            # Update in long-term memory
            for key, value in updates.items():
                await self.memory_manager.set_session_state(session_id, key, value)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating session state: {e}")
            return False
    
    async def store_temporary_info(self, session_id: int, key: str, value: Any, 
                                 ttl_seconds: int = 3600) -> bool:
        """
        Store temporary information for the session.
        
        Args:
            session_id: Session identifier
            key: Information key
            value: Information value
            ttl_seconds: Time to live in seconds
        
        Returns:
            True if successful, False otherwise
        """
        await self.initialize()
        
        try:
            # Store in both short-term and long-term memory
            if self.short_term_memory:
                await self.short_term_memory.set_temporary_data(
                    f"session_{session_id}_{key}", value, ttl_seconds
                )
            
            await self.memory_manager.set_temporary(
                f"session_{session_id}_{key}", value, ttl_seconds
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing temporary info: {e}")
            return False
    
    async def get_temporary_info(self, session_id: int, key: str) -> Any:
        """
        Get temporary information for the session.
        
        Args:
            session_id: Session identifier
            key: Information key
        
        Returns:
            Stored value or None if not found
        """
        await self.initialize()
        
        try:
            # Try short-term memory first
            if self.short_term_memory:
                value = await self.short_term_memory.get_temporary_data(f"session_{session_id}_{key}")
                if value is not None:
                    return value
            
            # Fallback to long-term memory
            return await self.memory_manager.get_temporary(f"session_{session_id}_{key}")
            
        except Exception as e:
            logger.error(f"Error getting temporary info: {e}")
            return None
    
    async def get_conversation_stats(self, session_id: int) -> Dict[str, Any]:
        """
        Get conversation statistics for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Conversation statistics
        """
        await self.initialize()
        
        try:
            # Get recent context to analyze
            context = await self.get_recent_context(session_id, limit=50)
            
            stats = {
                "total_messages": len(context),
                "user_messages": len([msg for msg in context if msg["role"] == "user"]),
                "assistant_messages": len([msg for msg in context if msg["role"] == "assistant"]),
                "average_message_length": 0,
                "conversation_duration": 0,
                "topics_discussed": [],
                "session_active": False
            }
            
            if context:
                # Calculate average message length
                total_length = sum(len(msg["content"]) for msg in context)
                stats["average_message_length"] = total_length / len(context)
                
                # Calculate conversation duration
                if len(context) >= 2:
                    first_msg = context[-1]
                    last_msg = context[0]
                    
                    try:
                        first_time = datetime.fromisoformat(first_msg["timestamp"].replace('Z', '+00:00'))
                        last_time = datetime.fromisoformat(last_msg["timestamp"].replace('Z', '+00:00'))
                        duration = (last_time - first_time).total_seconds()
                        stats["conversation_duration"] = duration
                    except (ValueError, TypeError):
                        pass
                
                # Check if session is active (last message within last hour)
                if context:
                    try:
                        last_time = datetime.fromisoformat(context[0]["timestamp"].replace('Z', '+00:00'))
                        time_diff = (datetime.now(timezone.utc) - last_time).total_seconds()
                        stats["session_active"] = time_diff < 3600  # 1 hour
                    except (ValueError, TypeError):
                        pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {}
    
    async def clear_session_context(self, session_id: int) -> bool:
        """
        Clear all conversation context for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if successful, False otherwise
        """
        await self.initialize()
        
        try:
            # Clear from both short-term and long-term memory
            if self.short_term_memory:
                await self.short_term_memory.clear_session_context(session_id)
            
            await self.memory_manager.clear_section("conversation_context", session_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing session context: {e}")
            return False
    
    async def get_active_sessions(self) -> List[int]:
        """
        Get list of active session IDs.
        
        Returns:
            List of active session IDs
        """
        await self.initialize()
        
        try:
            if self.short_term_memory:
                return await self.short_term_memory.get_active_sessions()
            return []
            
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def remember_number(self, session_id: int, number: Any, context: str = "") -> bool:
        """
        Remember a number mentioned in the conversation.
        
        Args:
            session_id: Session identifier
            number: The number to remember
            context: Context about the number
        
        Returns:
            True if successful, False otherwise
        """
        await self.initialize()
        
        try:
            memory_key = f"remembered_number_{session_id}"
            memory_data = {
                "number": number,
                "context": context,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id
            }
            
            await self.memory_manager.set("temporary", memory_key, memory_data, session_id=session_id, ttl_seconds=7200)
            
            return True
            
        except Exception as e:
            logger.error(f"Error remembering number: {e}")
            return False
    
    async def recall_number(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Recall the most recently mentioned number in the conversation.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Number information or None if not found
        """
        await self.initialize()
        
        try:
            memory_key = f"remembered_number_{session_id}"
            return await self.memory_manager.get("temporary", memory_key, session_id=session_id)
            
        except Exception as e:
            logger.error(f"Error recalling number: {e}")
            return None
    
    async def remember_fact(self, session_id: int, fact: str, category: str = "general") -> bool:
        """
        Remember a fact mentioned in the conversation.
        
        Args:
            session_id: Session identifier
            fact: The fact to remember
            category: Category of the fact
        
        Returns:
            True if successful, False otherwise
        """
        await self.initialize()
        
        try:
            fact_data = {
                "fact": fact,
                "category": category,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Store in both temporary and facts sections
            await self.memory_manager.set("temporary", f"fact_{session_id}_{hash(fact)}", fact_data, session_id=session_id, ttl_seconds=7200)
            await self.memory_manager.store_fact(f"session_{session_id}_{category}_{hash(fact)}", fact, f"conversation_session_{session_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error remembering fact: {e}")
            return False
    
    async def search_remembered_facts(self, session_id: int, query: str = "") -> List[Dict[str, Any]]:
        """
        Search for remembered facts in the session.
        
        Args:
            session_id: Session identifier
            query: Search query
        
        Returns:
            List of matching facts
        """
        await self.initialize()
        
        try:
            # Search in temporary facts
            temp_facts = await self.memory_manager.search("temporary", query, session_id)
            
            # Search in permanent facts
            permanent_facts = await self.memory_manager.search_facts(query)
            
            # Combine and format results
            all_facts = []
            
            for fact in temp_facts:
                if "fact" in str(fact.get("value", {})):
                    all_facts.append({
                        "fact": fact["value"].get("fact", ""),
                        "category": fact["value"].get("category", "general"),
                        "timestamp": fact["value"].get("timestamp", ""),
                        "source": "temporary"
                    })
            
            for fact in permanent_facts:
                if "fact" in str(fact.get("value", {})):
                    all_facts.append({
                        "fact": fact["value"].get("fact", ""),
                        "category": fact["value"].get("category", "general"),
                        "timestamp": fact["value"].get("timestamp", ""),
                        "source": "permanent"
                    })
            
            return all_facts
            
        except Exception as e:
            logger.error(f"Error searching remembered facts: {e}")
            return []


# Global plugin instance
_conversation_memory_plugin: Optional[ConversationMemoryPlugin] = None


def get_conversation_memory_plugin() -> ConversationMemoryPlugin:
    """Get the global conversation memory plugin instance."""
    global _conversation_memory_plugin
    
    if _conversation_memory_plugin is None:
        _conversation_memory_plugin = ConversationMemoryPlugin()
    
    return _conversation_memory_plugin


# Plugin registration functions
async def get_recent_context(session_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent conversation context for a session."""
    plugin = get_conversation_memory_plugin()
    return await plugin.get_recent_context(session_id, limit)


async def search_conversation_history(session_id: int, query: str) -> List[Dict[str, Any]]:
    """Search conversation history for specific content."""
    plugin = get_conversation_memory_plugin()
    return await plugin.search_conversation_history(session_id, query)


async def get_session_state(session_id: int) -> Dict[str, Any]:
    """Get current session state."""
    plugin = get_conversation_memory_plugin()
    return await plugin.get_session_state(session_id)


async def update_session_state(session_id: int, updates: Dict[str, Any]) -> bool:
    """Update session state."""
    plugin = get_conversation_memory_plugin()
    return await plugin.update_session_state(session_id, updates)


async def store_temporary_info(session_id: int, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Store temporary information for the session."""
    plugin = get_conversation_memory_plugin()
    return await plugin.store_temporary_info(session_id, key, value, ttl_seconds)


async def get_temporary_info(session_id: int, key: str) -> Any:
    """Get temporary information for the session."""
    plugin = get_conversation_memory_plugin()
    return await plugin.get_temporary_info(session_id, key)


async def get_conversation_stats(session_id: int) -> Dict[str, Any]:
    """Get conversation statistics for a session."""
    plugin = get_conversation_memory_plugin()
    return await plugin.get_conversation_stats(session_id)


async def clear_session_context(session_id: int) -> bool:
    """Clear all conversation context for a session."""
    plugin = get_conversation_memory_plugin()
    return await plugin.clear_session_context(session_id)


async def get_active_sessions() -> List[int]:
    """Get list of active session IDs."""
    plugin = get_conversation_memory_plugin()
    return await plugin.get_active_sessions()


async def remember_number(session_id: int, number: Any, context: str = "") -> bool:
    """Remember a number mentioned in the conversation."""
    plugin = get_conversation_memory_plugin()
    return await plugin.remember_number(session_id, number, context)


async def recall_number(session_id: int) -> Optional[Dict[str, Any]]:
    """Recall the most recently mentioned number in the conversation."""
    plugin = get_conversation_memory_plugin()
    return await plugin.recall_number(session_id)


async def remember_fact(session_id: int, fact: str, category: str = "general") -> bool:
    """Remember a fact mentioned in the conversation."""
    plugin = get_conversation_memory_plugin()
    return await plugin.remember_fact(session_id, fact, category)


async def search_remembered_facts(session_id: int, query: str = "") -> List[Dict[str, Any]]:
    """Search for remembered facts in the session."""
    plugin = get_conversation_memory_plugin()
    return await plugin.search_remembered_facts(session_id, query) 