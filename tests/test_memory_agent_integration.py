"""
Integration tests for autonomous memory in the agent system.
"""

import pytest
import pytest_asyncio
import os
from unittest.mock import AsyncMock, patch

from nagatha_assistant.core.memory import get_memory_manager, get_memory_trigger


class TestAgentMemoryIntegration:
    """Integration tests for autonomous memory with agent functionality."""
    
    @pytest.mark.asyncio
    async def test_memory_trigger_analyzes_user_preferences(self):
        """Test that memory trigger correctly identifies user preferences."""
        # Set up memory manager with in-memory backend
        from nagatha_assistant.core.storage import InMemoryStorageBackend
        from nagatha_assistant.core.memory import MemoryManager
        
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            from nagatha_assistant.core.memory import MemoryTrigger
            trigger = MemoryTrigger(manager)
            
            # Test user preference detection
            user_message = "I prefer detailed explanations and always like examples in my responses."
            context = {"session_id": 123}
            
            result = await trigger.analyze_for_storage(user_message, context)
            
            assert result["should_store"] is True
            assert result["importance_score"] > 0.5
            
            # Check that preference entries were identified
            preference_entries = [e for e in result["entries"] if e["section"] == "user_preferences"]
            assert len(preference_entries) > 0
            
            # Verify preference structure
            pref_entry = preference_entries[0]
            assert pref_entry["section"] == "user_preferences"
            assert "prefer" in pref_entry["value"]["text"].lower()
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_memory_trigger_analyzes_personality_cues(self):
        """Test that memory trigger correctly identifies personality cues."""
        from nagatha_assistant.core.storage import InMemoryStorageBackend
        from nagatha_assistant.core.memory import MemoryManager, MemoryTrigger
        
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            trigger = MemoryTrigger(manager)
            
            # Test personality cue detection
            user_message = "I feel frustrated when responses are too formal. I enjoy casual conversation."
            context = {"session_id": 456}
            
            result = await trigger.analyze_for_storage(user_message, context)
            
            assert result["should_store"] is True
            
            # Check for personality entries
            personality_entries = [e for e in result["entries"] if e["section"] == "personality"]
            assert len(personality_entries) > 0
            
            # Verify at least one personality entry
            personality_entry = personality_entries[0]
            assert personality_entry["section"] == "personality"
            assert personality_entry["session_id"] == 456
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio 
    async def test_contextual_recall_with_stored_memories(self):
        """Test contextual recall with pre-stored memories."""
        from nagatha_assistant.core.storage import InMemoryStorageBackend
        from nagatha_assistant.core.memory import MemoryManager, ContextualRecall
        
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Store some test memories
            await manager.set("user_preferences", "detail_pref", {
                "text": "I prefer detailed technical explanations",
                "type": "preference",
                "confidence": 0.8
            })
            
            await manager.set("personality", "style_casual", {
                "style_type": "informality_preference",
                "context": "I like casual conversation",
                "confidence": 0.7
            }, session_id=789)
            
            await manager.set("facts", "python_fact", {
                "fact": "Python is a programming language",
                "source": "conversation",
                "confidence": 0.6
            })
            
            # Test contextual recall
            recall = ContextualRecall(manager)
            
            context = "Python"  # Use simpler search term that should match
            memories = await recall.get_relevant_memories(context, session_id=789, max_results=5)
            
            # Should find relevant memories
            assert isinstance(memories, dict)
            
            # Should find the Python fact
            assert "facts" in memories
            facts_memories = memories["facts"]
            assert len(facts_memories) > 0
            
            # Verify the Python fact was found
            python_fact_found = any("Python" in str(mem.get("value", "")) for mem in facts_memories)
            assert python_fact_found
            
            # Test that contextual recall only returns sections with matches
            # (user_preferences and personality don't contain "Python" so they shouldn't be returned)
            
            # Test personality adaptations
            adaptations = await recall.get_personality_adaptations(context, session_id=789)
            
            assert "communication_style" in adaptations
            assert "formality_level" in adaptations
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_personality_memory_updates(self):
        """Test personality memory updates and adaptations."""
        from nagatha_assistant.core.storage import InMemoryStorageBackend
        from nagatha_assistant.core.memory import MemoryManager, PersonalityMemory
        
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            personality_memory = PersonalityMemory(manager)
            
            # Update personality traits
            await personality_memory.update_personality_trait(
                "communication_style", 
                "technical_detailed", 
                session_id=101,
                confidence=0.9
            )
            
            await personality_memory.update_personality_trait(
                "interaction_preference",
                "direct_answers",
                session_id=101, 
                confidence=0.8
            )
            
            # Get personality profile
            profile = await personality_memory.get_personality_profile(session_id=101)
            
            assert "communication_style" in profile
            assert "learned_traits" in profile
            assert len(profile["learned_traits"]) >= 2
            
            # Test context adaptation
            adaptations = await personality_memory.adapt_to_context(
                "technical programming question", 
                session_id=101
            )
            
            assert "tone" in adaptations
            assert "detail_level" in adaptations
            assert "formality" in adaptations
            assert "response_style" in adaptations
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_memory_maintenance_operations(self):
        """Test memory maintenance operations."""
        from nagatha_assistant.core.storage import InMemoryStorageBackend
        from nagatha_assistant.core.memory import MemoryManager, MemoryMaintenance
        
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        
        try:
            # Add some duplicate entries for testing
            await manager.set("user_preferences", "test1", "duplicate_value")
            await manager.set("user_preferences", "test2", "duplicate_value")
            await manager.set("user_preferences", "test3", "unique_value")
            
            maintenance = MemoryMaintenance(manager)
            
            # Perform maintenance
            results = await maintenance.perform_maintenance()
            
            assert "duplicates_removed" in results
            assert "entries_consolidated" in results
            assert "outdated_removed" in results
            assert "conflicts_resolved" in results
            
            # All results should be non-negative integers
            for key, value in results.items():
                assert isinstance(value, int)
                assert value >= 0
                
            # Should have removed at least one duplicate
            assert results["duplicates_removed"] >= 1
            
        finally:
            await manager.stop()


class TestMemoryIntegrationWithMockedAgent:
    """Test memory integration with mocked agent functions."""
    
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
    async def test_agent_import_with_memory_functions(self):
        """Test that agent module can be imported and memory functions work."""
        # This tests that our changes to agent.py don't break imports
        try:
            from nagatha_assistant.core import agent
            from nagatha_assistant.core.memory import (
                get_memory_trigger, get_contextual_recall, get_personality_memory
            )
            
            # Test that memory functions are accessible
            trigger = get_memory_trigger()
            recall = get_contextual_recall()
            personality = get_personality_memory()
            
            assert trigger is not None
            assert recall is not None
            assert personality is not None
            
            # Test basic functionality without full agent
            test_content = "I prefer concise answers"
            analysis = await trigger.analyze_for_storage(test_content)
            
            assert "should_store" in analysis
            assert "importance_score" in analysis
            
        except Exception as e:
            pytest.fail(f"Agent import or memory integration failed: {e}")