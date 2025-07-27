"""
Persistent Memory System for Nagatha Assistant.

This module provides a comprehensive memory system that allows Nagatha to store
and retrieve information across sessions, including:
- Key-value store for simple data
- Structured data storage for complex objects
- Automatic serialization/deserialization
- Memory sections with different persistence levels
- Memory search capabilities
- Event bus integration for change notifications
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from nagatha_assistant.core.storage import StorageBackend, DatabaseStorageBackend, InMemoryStorageBackend
from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import StandardEventTypes, create_memory_event, EventPriority
from nagatha_assistant.utils.logger import setup_logger_with_env_control, get_logger

logger = get_logger()


class PersistenceLevel(Enum):
    """Enumeration of memory persistence levels."""
    TEMPORARY = "temporary"      # Expires automatically, suitable for short-term data
    SESSION = "session"          # Persists for the duration of a session
    PERMANENT = "permanent"      # Persists indefinitely


class MemorySection:
    """Represents a logical section of memory with specific persistence characteristics."""
    
    def __init__(self, name: str, persistence_level: PersistenceLevel = PersistenceLevel.PERMANENT,
                 description: Optional[str] = None):
        self.name = name
        self.persistence_level = persistence_level
        self.description = description


class MemoryManager:
    """
    Central memory management system for Nagatha.
    
    Provides key-value storage with different persistence levels, automatic
    serialization, search capabilities, and event integration.
    """
    
    # Predefined memory sections
    SECTIONS = {
        "user_preferences": MemorySection("user_preferences", PersistenceLevel.PERMANENT,
                                         "User preferences and settings"),
        "session_state": MemorySection("session_state", PersistenceLevel.SESSION,
                                     "Current session state and context"),
        "command_history": MemorySection("command_history", PersistenceLevel.PERMANENT,
                                       "History of user commands and interactions"),
        "facts": MemorySection("facts", PersistenceLevel.PERMANENT,
                              "Long-term facts and knowledge"),
        "temporary": MemorySection("temporary", PersistenceLevel.TEMPORARY,
                                 "Short-term temporary data"),
        "personality": MemorySection("personality", PersistenceLevel.PERMANENT,
                                   "Dynamic personality traits, inflection styles, and interaction preferences"),
    }
    
    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        """
        Initialize the memory manager.
        
        Args:
            storage_backend: Optional storage backend. Defaults to DatabaseStorageBackend.
        """
        self._storage = storage_backend or DatabaseStorageBackend()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the memory manager and cleanup tasks."""
        if self._running:
            return
        
        self._running = True
        # Start cleanup task for expired entries
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Memory manager started")
    
    async def stop(self) -> None:
        """Stop the memory manager and cleanup tasks."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Memory manager stopped")
    
    async def set(self, section: str, key: str, value: Any, session_id: Optional[int] = None,
                  ttl_seconds: Optional[int] = None) -> None:
        """
        Store a value in memory.
        
        Args:
            section: Memory section name
            key: Key to store the value under
            value: Value to store (will be automatically serialized)
            session_id: Optional session ID for session-scoped storage
            ttl_seconds: Time to live in seconds (for temporary data)
        """
        expires_at = None
        if ttl_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        await self._storage.set(section, key, value, session_id, expires_at)
        
        # Publish event
        try:
            event_bus = get_event_bus()
            if event_bus and event_bus._running:
                event = create_memory_event(
                    StandardEventTypes.MEMORY_ENTRY_CREATED,
                    section,
                    key,
                    {
                        "value_type": type(value).__name__,
                        "session_id": session_id,
                        "has_ttl": ttl_seconds is not None
                    }
                )
                await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish memory event: {e}")
        
        logger.debug(f"Stored memory: {section}/{key} (session: {session_id})")
    
    async def get(self, section: str, key: str, session_id: Optional[int] = None,
                  default: Any = None) -> Any:
        """
        Retrieve a value from memory.
        
        Args:
            section: Memory section name
            key: Key to retrieve
            session_id: Optional session ID for session-scoped retrieval
            default: Default value to return if key not found
        
        Returns:
            Stored value or default if not found
        """
        value = await self._storage.get(section, key, session_id)
        if value is None:
            return default
        return value
    
    async def delete(self, section: str, key: str, session_id: Optional[int] = None) -> bool:
        """
        Delete a value from memory.
        
        Args:
            section: Memory section name
            key: Key to delete
            session_id: Optional session ID for session-scoped deletion
        
        Returns:
            True if the key was found and deleted, False otherwise
        """
        deleted = await self._storage.delete(section, key, session_id)
        
        if deleted:
            # Publish event
            try:
                event_bus = get_event_bus()
                if event_bus and event_bus._running:
                    event = create_memory_event(
                        StandardEventTypes.MEMORY_ENTRY_DELETED,
                        section,
                        key,
                        {"session_id": session_id}
                    )
                    await event_bus.publish(event)
            except Exception as e:
                logger.warning(f"Failed to publish memory event: {e}")
            
            logger.debug(f"Deleted memory: {section}/{key} (session: {session_id})")
        
        return deleted
    
    async def list_keys(self, section: str, session_id: Optional[int] = None,
                       pattern: Optional[str] = None) -> List[str]:
        """
        List keys in a memory section.
        
        Args:
            section: Memory section name
            session_id: Optional session ID to filter by
            pattern: Optional pattern to filter keys (supports wildcards)
        
        Returns:
            List of matching keys
        """
        return await self._storage.list_keys(section, session_id, pattern)
    
    async def search(self, section: str, query: str, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for entries in a memory section.
        
        Args:
            section: Memory section name
            query: Search query (searches both keys and values)
            session_id: Optional session ID to filter by
        
        Returns:
            List of matching entries with metadata
        """
        results = await self._storage.search(section, query, session_id)
        
        # Publish search event
        try:
            event_bus = get_event_bus()
            if event_bus and event_bus._running:
                event = create_memory_event(
                    StandardEventTypes.MEMORY_SEARCH_PERFORMED,
                    section,
                    None,
                    {
                        "query": query,
                        "session_id": session_id,
                        "result_count": len(results)
                    }
                )
                await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish memory event: {e}")
        
        return results
    
    async def set_user_preference(self, key: str, value: Any) -> None:
        """Set a user preference (permanent storage)."""
        await self.set("user_preferences", key, value)
    
    async def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return await self.get("user_preferences", key, default=default)
    
    async def set_session_state(self, session_id: int, key: str, value: Any) -> None:
        """Set session-specific state."""
        await self.set("session_state", key, value, session_id=session_id)
    
    async def get_session_state(self, session_id: int, key: str, default: Any = None) -> Any:
        """Get session-specific state."""
        return await self.get("session_state", key, session_id=session_id, default=default)
    
    async def add_command_to_history(self, command: str, response: Optional[str] = None,
                                   session_id: Optional[int] = None) -> None:
        """Add a command to the command history."""
        timestamp = datetime.now(timezone.utc).isoformat()
        history_entry = {
            "command": command,
            "response": response,
            "timestamp": timestamp,
            "session_id": session_id
        }
        
        # Use timestamp as key for ordering
        key = f"{timestamp}_{session_id or 'global'}"
        await self.set("command_history", key, history_entry)
    
    async def get_command_history(self, session_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get command history, optionally filtered by session."""
        # Search for all commands (empty query matches all)
        results = await self.search("command_history", "", session_id)
        
        # Sort by timestamp (most recent first) and limit
        results.sort(key=lambda x: x.get("value", {}).get("timestamp", ""), reverse=True)
        return results[:limit]
    
    async def store_fact(self, key: str, fact: str, source: Optional[str] = None) -> None:
        """Store a long-term fact."""
        fact_data = {
            "fact": fact,
            "source": source,
            "stored_at": datetime.now(timezone.utc).isoformat()
        }
        await self.set("facts", key, fact_data)
    
    async def get_fact(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored fact."""
        return await self.get("facts", key)
    
    async def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search for facts containing the query."""
        return await self.search("facts", query)
    
    async def set_temporary(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Store temporary data with TTL."""
        await self.set("temporary", key, value, ttl_seconds=ttl_seconds)
    
    async def get_temporary(self, key: str, default: Any = None) -> Any:
        """Get temporary data."""
        return await self.get("temporary", key, default=default)
    
    async def clear_section(self, section: str, session_id: Optional[int] = None) -> int:
        """
        Clear all entries in a section.
        
        Args:
            section: Section to clear
            session_id: Optional session ID to filter by
        
        Returns:
            Number of entries deleted
        """
        keys = await self.list_keys(section, session_id)
        deleted_count = 0
        
        for key in keys:
            if await self.delete(section, key, session_id):
                deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} entries from section {section}")
        return deleted_count
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about memory storage."""
        stats = {}
        
        # Check predefined sections
        for section_name in self.SECTIONS.keys():
            keys = await self.list_keys(section_name)
            stats[section_name] = len(keys)
        
        # Also check for any other sections that might have data
        # This is a best-effort attempt for in-memory backend
        if hasattr(self._storage, '_storage'):
            # InMemoryStorageBackend
            for section_name in self._storage._storage.keys():
                if section_name not in stats:
                    keys = await self.list_keys(section_name)
                    stats[section_name] = len(keys)
        
        # Add cleanup info
        stats["cleanup_running"] = self._running
        
        return stats
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired entries."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                if not self._running:
                    break
                
                cleaned_count = await self._storage.cleanup_expired()
                if cleaned_count > 0:
                    logger.debug(f"Cleaned up {cleaned_count} expired memory entries")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in memory cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying


class MemoryTrigger:
    """
    Analyzes content to determine what should be stored autonomously.
    
    Provides importance scoring, section selection, and conflict resolution
    for autonomous memory management.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.importance_threshold = 0.5  # Configurable threshold for storing information
        
    async def analyze_for_storage(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze content to determine what should be stored and where.
        
        Args:
            content: The content to analyze
            context: Additional context (session_id, user_preferences, etc.)
            
        Returns:
            Dictionary with storage recommendations
        """
        if not content or len(content.strip()) < 3:
            return {"should_store": False, "reason": "Content too short"}
            
        context = context or {}
        session_id = context.get("session_id")
        
        recommendations = {
            "should_store": False,
            "entries": [],
            "reason": "",
            "importance_score": 0.0
        }
        
        # Calculate importance score
        importance_score = await self._calculate_importance(content, context)
        recommendations["importance_score"] = importance_score
        
        if importance_score < self.importance_threshold:
            recommendations["reason"] = f"Importance score {importance_score:.2f} below threshold {self.importance_threshold}"
            return recommendations
            
        # Analyze for different types of information
        entries_to_store = []
        
        # User preferences detection
        preference_entries = await self._detect_user_preferences(content, context)
        entries_to_store.extend(preference_entries)
        
        # Personality traits detection
        personality_entries = await self._detect_personality_cues(content, context)
        entries_to_store.extend(personality_entries)
        
        # Facts and knowledge detection
        fact_entries = await self._detect_facts(content, context)
        entries_to_store.extend(fact_entries)
        
        # Session state information
        if session_id:
            session_entries = await self._detect_session_state(content, context)
            entries_to_store.extend(session_entries)
        
        if entries_to_store:
            recommendations["should_store"] = True
            recommendations["entries"] = entries_to_store
            recommendations["reason"] = f"Found {len(entries_to_store)} items to store"
        else:
            recommendations["reason"] = "No significant information detected"
            
        return recommendations
    
    async def _calculate_importance(self, content: str, context: Dict[str, Any]) -> float:
        """Calculate importance score for content."""
        score = 0.0
        content_lower = content.lower()
        
        # Preference indicators
        preference_keywords = ["prefer", "like", "dislike", "want", "need", "always", "never", "usually"]
        score += sum(0.1 for keyword in preference_keywords if keyword in content_lower)
        
        # Personality indicators
        personality_keywords = ["feel", "think", "enjoy", "frustrated", "happy", "style", "approach"]
        score += sum(0.15 for keyword in personality_keywords if keyword in content_lower)
        
        # Factual information indicators
        fact_keywords = ["is", "are", "was", "were", "will", "has", "have", "does", "do"]
        score += sum(0.05 for keyword in fact_keywords if keyword in content_lower)
        
        # Personal information indicators
        personal_keywords = ["my", "mine", "me", "i", "myself"]
        score += sum(0.1 for keyword in personal_keywords if keyword in content_lower)
        
        # Interaction style indicators
        interaction_keywords = ["please", "thank", "help", "explain", "show", "tell"]
        score += sum(0.1 for keyword in interaction_keywords if keyword in content_lower)
        
        # Length factor (longer content generally more important)
        length_factor = min(len(content) / 200, 0.3)
        score += length_factor
        
        return min(score, 1.0)  # Cap at 1.0
    
    async def _detect_user_preferences(self, content: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect user preferences in content."""
        entries = []
        content_lower = content.lower()
        
        # Simple preference detection patterns
        preference_patterns = [
            ("prefer", "preference"),
            ("like", "positive_preference"),
            ("dislike", "negative_preference"),
            ("always", "strong_preference"),
            ("never", "strong_negative_preference"),
            ("usually", "general_preference")
        ]
        
        for pattern, pref_type in preference_patterns:
            if pattern in content_lower:
                # Extract context around the preference
                import re
                matches = re.finditer(rf'\b\w*{pattern}\w*\b[^.!?]*[.!?]', content, re.IGNORECASE)
                for match in matches:
                    preference_text = match.group().strip()
                    if len(preference_text) > 10:  # Meaningful preference
                        key = f"{pref_type}_{hash(preference_text) % 10000}"
                        entries.append({
                            "section": "user_preferences",
                            "key": key,
                            "value": {
                                "text": preference_text,
                                "type": pref_type,
                                "detected_at": datetime.now(timezone.utc).isoformat(),
                                "confidence": 0.7
                            },
                            "session_id": None,  # User preferences are global
                            "ttl_seconds": None
                        })
        
        return entries
    
    async def _detect_personality_cues(self, content: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect personality-related information in content."""
        entries = []
        content_lower = content.lower()
        session_id = context.get("session_id")
        
        # Interaction style cues
        style_patterns = [
            ("formal", "formality_preference"),
            ("casual", "informality_preference"),
            ("detailed", "detail_preference"),
            ("brief", "brevity_preference"),
            ("explain", "explanation_preference"),
            ("humor", "humor_preference"),
            ("serious", "seriousness_preference")
        ]
        
        for pattern, style_type in style_patterns:
            if pattern in content_lower:
                key = f"{style_type}_{session_id or 'global'}"
                entries.append({
                    "section": "personality",
                    "key": key,
                    "value": {
                        "style_type": style_type,
                        "context": content[:200],  # Store context
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "session_id": session_id,
                        "confidence": 0.6
                    },
                    "session_id": session_id,
                    "ttl_seconds": None
                })
        
        # Emotional tone detection
        emotion_patterns = [
            ("happy", "positive_emotion"),
            ("frustrated", "negative_emotion"),
            ("excited", "high_energy"),
            ("calm", "low_energy"),
            ("confused", "confusion_state"),
            ("understand", "comprehension_state")
        ]
        
        for pattern, emotion_type in emotion_patterns:
            if pattern in content_lower:
                key = f"emotion_{emotion_type}_{session_id or 'global'}"
                entries.append({
                    "section": "personality",
                    "key": key,
                    "value": {
                        "emotion_type": emotion_type,
                        "context": content[:150],
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "confidence": 0.5
                    },
                    "session_id": session_id,
                    "ttl_seconds": 7200  # Emotions are temporary (2 hours)
                })
        
        return entries
    
    async def _detect_facts(self, content: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect factual information worth storing."""
        entries = []
        content_lower = content.lower()
        
        # Simple fact detection - statements with declarative structure
        import re
        
        # Look for statements that declare facts
        fact_patterns = [
            r'\b\w+\s+is\s+\w+',
            r'\b\w+\s+are\s+\w+',
            r'\b\w+\s+has\s+\w+',
            r'\b\w+\s+have\s+\w+',
            r'\b\w+\s+does\s+\w+',
            r'\b\w+\s+can\s+\w+'
        ]
        
        for pattern in fact_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                fact_text = match.group().strip()
                if len(fact_text) > 5:  # Meaningful fact
                    # Expand to get full sentence
                    sentence_match = re.search(rf'[^.!?]*{re.escape(fact_text)}[^.!?]*[.!?]', content, re.IGNORECASE)
                    if sentence_match:
                        full_fact = sentence_match.group().strip()
                        key = f"fact_{hash(full_fact) % 10000}"
                        entries.append({
                            "section": "facts",
                            "key": key,
                            "value": {
                                "fact": full_fact,
                                "source": "conversation",
                                "stored_at": datetime.now(timezone.utc).isoformat(),
                                "confidence": 0.4
                            },
                            "session_id": None,  # Facts are global
                            "ttl_seconds": None
                        })
        
        return entries
    
    async def _detect_session_state(self, content: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect session-specific state information."""
        entries = []
        session_id = context.get("session_id")
        
        if not session_id:
            return entries
        
        content_lower = content.lower()
        
        # Current task or topic detection
        task_keywords = ["working on", "task", "project", "goal", "trying to", "need to"]
        for keyword in task_keywords:
            if keyword in content_lower:
                # Extract context around the task
                import re
                matches = re.finditer(rf'[^.!?]*{keyword}[^.!?]*[.!?]', content, re.IGNORECASE)
                for match in matches:
                    task_text = match.group().strip()
                    if len(task_text) > 15:
                        entries.append({
                            "section": "session_state",
                            "key": "current_task",
                            "value": {
                                "task": task_text,
                                "detected_at": datetime.now(timezone.utc).isoformat()
                            },
                            "session_id": session_id,
                            "ttl_seconds": None
                        })
                        break  # Only store one task per analysis
        
        return entries


class MemoryLearning:
    """
    Learns from memory usage patterns and user feedback to improve autonomous decisions.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        
    async def analyze_usage_patterns(self) -> Dict[str, Any]:
        """Analyze how memory is being used to identify patterns."""
        patterns = {
            "section_usage": {},
            "access_frequency": {},
            "retention_patterns": {},
            "user_feedback": {}
        }
        
        # Analyze section usage
        stats = await self.memory_manager.get_storage_stats()
        patterns["section_usage"] = stats
        
        # Track which sections are accessed most frequently
        # This would be enhanced with actual access tracking
        access_data = await self._get_access_statistics()
        patterns["access_frequency"] = access_data
        
        return patterns
    
    async def _get_access_statistics(self) -> Dict[str, int]:
        """Get statistics on memory access patterns."""
        # This is a simplified version - would be enhanced with actual tracking
        stats = {}
        
        for section_name in self.memory_manager.SECTIONS.keys():
            keys = await self.memory_manager.list_keys(section_name)
            stats[section_name] = len(keys)
        
        return stats
    
    async def learn_from_feedback(self, feedback_type: str, content: str, 
                                context: Dict[str, Any] = None) -> None:
        """Learn from user feedback about memory decisions."""
        feedback_entry = {
            "type": feedback_type,  # "positive", "negative", "correction"
            "content": content,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Store feedback for learning
        feedback_key = f"feedback_{int(datetime.now(timezone.utc).timestamp())}"
        await self.memory_manager.set("temporary", feedback_key, feedback_entry, ttl_seconds=86400)  # 24 hours


class ContextualRecall:
    """
    Intelligently surfaces relevant memories and personality traits based on context.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        
    async def get_relevant_memories(self, context: str, session_id: Optional[int] = None,
                                  max_results: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Surface relevant memories based on current context.
        
        Args:
            context: Current conversation context
            session_id: Optional session ID for session-specific memories
            max_results: Maximum number of results per section
            
        Returns:
            Dictionary of relevant memories by section
        """
        relevant_memories = {}
        
        # Search each section for relevant information
        for section_name in self.memory_manager.SECTIONS.keys():
            try:
                results = await self.memory_manager.search(section_name, context, session_id)
                if results:
                    # Sort by relevance (would be enhanced with better scoring)
                    sorted_results = sorted(results, key=lambda x: self._calculate_relevance_score(x, context), reverse=True)
                    relevant_memories[section_name] = sorted_results[:max_results]
            except Exception as e:
                logger.warning(f"Error searching section {section_name}: {e}")
        
        return relevant_memories
    
    async def get_session_startup_memories(self, session_id: Optional[int] = None,
                                         max_results: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get memories that should be loaded when starting a new session.
        This includes user preferences, name, and other important context.
        
        Args:
            session_id: Optional session ID for session-specific memories
            max_results: Maximum number of results per section
            
        Returns:
            Dictionary of startup memories by section
        """
        startup_memories = {}
        
        # Get user preferences (important for session context)
        try:
            user_prefs = await self.memory_manager.search("user_preferences", "", session_id)
            if user_prefs:
                startup_memories["user_preferences"] = user_prefs[:max_results]
        except Exception as e:
            logger.warning(f"Error getting user preferences: {e}")
        
        # Get personality traits (for interaction style)
        try:
            personality = await self.memory_manager.search("personality", "", session_id)
            if personality:
                startup_memories["personality"] = personality[:max_results]
        except Exception as e:
            logger.warning(f"Error getting personality traits: {e}")
        
        # Get recent facts (for context)
        try:
            facts = await self.memory_manager.search("facts", "", session_id)
            if facts:
                # Sort by recency (assuming facts have timestamps)
                sorted_facts = sorted(facts, key=lambda x: self._get_timestamp_score(x), reverse=True)
                startup_memories["facts"] = sorted_facts[:max_results]
        except Exception as e:
            logger.warning(f"Error getting facts: {e}")
        
        return startup_memories
    
    async def get_user_name(self) -> Optional[str]:
        """
        Get the user's name from memory.
        
        Returns:
            User's name if stored, None otherwise
        """
        try:
            # Try to get name from user_preferences
            name = await self.memory_manager.get("user_preferences", "name")
            if name:
                if isinstance(name, dict) and "text" in name:
                    return name["text"]
                elif isinstance(name, str):
                    return name
            
            # Try to get name from facts
            name_fact = await self.memory_manager.get("facts", "user_name")
            if name_fact:
                if isinstance(name_fact, dict) and "fact" in name_fact:
                    return name_fact["fact"]
                elif isinstance(name_fact, str):
                    return name_fact
            
            return None
        except Exception as e:
            logger.warning(f"Error getting user name: {e}")
            return None
    
    def _get_timestamp_score(self, memory_entry: Dict[str, Any]) -> float:
        """Calculate a score based on timestamp for sorting by recency."""
        try:
            value = memory_entry.get("value", {})
            if isinstance(value, dict):
                # Look for various timestamp fields
                for timestamp_field in ["stored_at", "timestamp", "created_at", "updated_at"]:
                    if timestamp_field in value:
                        timestamp_str = value[timestamp_field]
                        if isinstance(timestamp_str, str):
                            # Convert ISO timestamp to float for sorting
                            try:
                                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                return dt.timestamp()
                            except:
                                pass
        except Exception:
            pass
        return 0.0  # Default score for entries without timestamps
    
    def _calculate_relevance_score(self, memory_entry: Dict[str, Any], context: str) -> float:
        """Calculate relevance score for a memory entry."""
        score = 0.0
        context_lower = context.lower()
        
        # Check key relevance
        key = memory_entry.get("key", "").lower()
        if any(word in key for word in context_lower.split()):
            score += 0.3
        
        # Check value relevance
        value = str(memory_entry.get("value", "")).lower()
        common_words = set(context_lower.split()) & set(value.split())
        score += len(common_words) * 0.1
        
        # Boost score for recent entries
        if "detected_at" in str(memory_entry.get("value", {})) or "timestamp" in str(memory_entry.get("value", {})):
            score += 0.2
        
        return min(score, 1.0)
    
    async def get_personality_adaptations(self, context: str, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Get personality adaptations based on context and stored personality data."""
        adaptations = {
            "communication_style": "default",
            "formality_level": "medium",
            "detail_preference": "balanced",
            "emotional_tone": "neutral",
            "interaction_preferences": {}
        }
        
        # Get personality memories
        personality_memories = await self.memory_manager.search("personality", context, session_id)
        
        for memory in personality_memories:
            value = memory.get("value", {})
            
            # Apply style adaptations
            if "style_type" in value:
                style_type = value["style_type"]
                if "formality" in style_type:
                    adaptations["formality_level"] = "high" if "formal" in style_type else "low"
                elif "detail" in style_type:
                    adaptations["detail_preference"] = "high" if "detail" in style_type else "low"
                elif "brevity" in style_type:
                    adaptations["detail_preference"] = "low"
            
            # Apply emotional adaptations
            if "emotion_type" in value:
                emotion_type = value["emotion_type"]
                if "positive" in emotion_type:
                    adaptations["emotional_tone"] = "positive"
                elif "negative" in emotion_type:
                    adaptations["emotional_tone"] = "supportive"
        
        return adaptations


class MemoryMaintenance:
    """
    Handles automated cleanup, consolidation, and organization of memory data.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        
    async def perform_maintenance(self) -> Dict[str, int]:
        """Perform comprehensive memory maintenance."""
        maintenance_results = {
            "duplicates_removed": 0,
            "entries_consolidated": 0,
            "outdated_removed": 0,
            "conflicts_resolved": 0
        }
        
        # Remove duplicates
        duplicates_removed = await self._remove_duplicates()
        maintenance_results["duplicates_removed"] = duplicates_removed
        
        # Consolidate related memories
        consolidated = await self._consolidate_memories()
        maintenance_results["entries_consolidated"] = consolidated
        
        # Remove outdated information
        outdated_removed = await self._remove_outdated()
        maintenance_results["outdated_removed"] = outdated_removed
        
        # Resolve conflicts
        conflicts_resolved = await self._resolve_conflicts()
        maintenance_results["conflicts_resolved"] = conflicts_resolved
        
        return maintenance_results
    
    async def _remove_duplicates(self) -> int:
        """Remove duplicate memory entries."""
        duplicates_removed = 0
        
        for section_name in self.memory_manager.SECTIONS.keys():
            try:
                keys = await self.memory_manager.list_keys(section_name)
                seen_values = {}
                
                for key in keys:
                    value = await self.memory_manager.get(section_name, key)
                    if value is not None:
                        value_str = str(value)
                        if value_str in seen_values:
                            # Duplicate found, remove the newer one (keep the original)
                            await self.memory_manager.delete(section_name, key)
                            duplicates_removed += 1
                        else:
                            seen_values[value_str] = key
            except Exception as e:
                logger.warning(f"Error removing duplicates from {section_name}: {e}")
        
        return duplicates_removed
    
    async def _consolidate_memories(self) -> int:
        """Consolidate related memories."""
        # This is a simplified version - would be enhanced with better similarity detection
        consolidated = 0
        
        # For now, just log that consolidation would happen here
        logger.debug("Memory consolidation would be performed here")
        
        return consolidated
    
    async def _remove_outdated(self) -> int:
        """Remove outdated memory entries."""
        outdated_removed = 0
        
        # Remove old temporary emotions (older than 24 hours)
        try:
            personality_keys = await self.memory_manager.list_keys("personality")
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            for key in personality_keys:
                if key.startswith("emotion_"):
                    value = await self.memory_manager.get("personality", key)
                    if isinstance(value, dict) and "detected_at" in value:
                        try:
                            detected_time = datetime.fromisoformat(value["detected_at"].replace("Z", "+00:00"))
                            if detected_time < cutoff_time:
                                await self.memory_manager.delete("personality", key)
                                outdated_removed += 1
                        except (ValueError, TypeError):
                            pass  # Skip invalid timestamps
        except Exception as e:
            logger.warning(f"Error removing outdated entries: {e}")
        
        return outdated_removed
    
    async def _resolve_conflicts(self) -> int:
        """Resolve conflicting memory entries."""
        # This is a simplified version - would be enhanced with conflict detection logic
        conflicts_resolved = 0
        
        logger.debug("Memory conflict resolution would be performed here")
        
        return conflicts_resolved


class PersonalityMemory:
    """
    Manages dynamic personality traits and adaptations.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        
    async def update_personality_trait(self, trait_name: str, trait_value: Any, 
                                     session_id: Optional[int] = None,
                                     confidence: float = 0.5) -> None:
        """Update a personality trait based on learned behavior."""
        trait_data = {
            "value": trait_value,
            "confidence": confidence,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id
        }
        
        await self.memory_manager.set("personality", trait_name, trait_data, session_id=session_id)
        
    async def get_personality_profile(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current personality profile for adaptation."""
        profile = {
            "communication_style": "default",
            "interaction_preferences": {},
            "emotional_adaptations": {},
            "learned_traits": {}
        }
        
        # Get all personality memories
        personality_keys = await self.memory_manager.list_keys("personality", session_id)
        
        for key in personality_keys:
            value = await self.memory_manager.get("personality", key, session_id)
            if isinstance(value, dict):
                if "style_type" in value:
                    profile["interaction_preferences"][key] = value
                elif "emotion_type" in value:
                    profile["emotional_adaptations"][key] = value
                else:
                    profile["learned_traits"][key] = value
        
        return profile
    
    async def adapt_to_context(self, context: str, session_id: Optional[int] = None) -> Dict[str, str]:
        """Generate personality adaptations for the current context."""
        profile = await self.get_personality_profile(session_id)
        
        adaptations = {
            "tone": "warm and professional",
            "detail_level": "balanced",
            "formality": "casual-professional",
            "response_style": "helpful and engaging"
        }
        
        # Apply learned preferences
        for pref_key, pref_data in profile["interaction_preferences"].items():
            if isinstance(pref_data, dict):
                style_type = pref_data.get("style_type", "")
                if "formal" in style_type:
                    adaptations["formality"] = "formal"
                elif "casual" in style_type:
                    adaptations["formality"] = "casual"
                elif "detail" in style_type:
                    adaptations["detail_level"] = "detailed"
                elif "brief" in style_type:
                    adaptations["detail_level"] = "concise"
        
        # Apply emotional context
        for emotion_key, emotion_data in profile["emotional_adaptations"].items():
            if isinstance(emotion_data, dict):
                emotion_type = emotion_data.get("emotion_type", "")
                if "positive" in emotion_type:
                    adaptations["tone"] = "enthusiastic and warm"
                elif "negative" in emotion_type:
                    adaptations["tone"] = "supportive and understanding"
                elif "confusion" in emotion_type:
                    adaptations["response_style"] = "clear and patient"
        
        return adaptations


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance (singleton pattern)."""
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    
    return _memory_manager


async def ensure_memory_manager_started() -> MemoryManager:
    """Ensure the global memory manager is started and return it."""
    manager = get_memory_manager()
    await manager.start()
    return manager


async def shutdown_memory_manager() -> None:
    """Shutdown the global memory manager."""
    global _memory_manager
    
    if _memory_manager is not None:
        await _memory_manager.stop()
        _memory_manager = None


# Autonomous Memory Management Functions
def get_memory_trigger() -> MemoryTrigger:
    """Get a MemoryTrigger instance using the global memory manager."""
    return MemoryTrigger(get_memory_manager())


def get_memory_learning() -> MemoryLearning:
    """Get a MemoryLearning instance using the global memory manager."""
    return MemoryLearning(get_memory_manager())


def get_contextual_recall() -> ContextualRecall:
    """Get a ContextualRecall instance using the global memory manager."""
    return ContextualRecall(get_memory_manager())


def get_memory_maintenance() -> MemoryMaintenance:
    """Get a MemoryMaintenance instance using the global memory manager."""
    return MemoryMaintenance(get_memory_manager())


def get_personality_memory() -> PersonalityMemory:
    """Get a PersonalityMemory instance using the global memory manager."""
    return PersonalityMemory(get_memory_manager())