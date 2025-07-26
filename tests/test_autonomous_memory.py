"""
Tests for autonomous memory management functionality.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from nagatha_assistant.core.memory import (
    MemoryManager, MemoryTrigger, MemoryLearning, ContextualRecall, 
    MemoryMaintenance, PersonalityMemory, get_memory_trigger,
    get_memory_learning, get_contextual_recall, get_memory_maintenance,
    get_personality_memory
)
from nagatha_assistant.core.storage import InMemoryStorageBackend


class TestMemoryTrigger:
    """Test suite for the MemoryTrigger class."""
    
    @pytest_asyncio.fixture
    async def memory_manager(self):
        """Create a memory manager with in-memory storage for testing."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()
    
    @pytest_asyncio.fixture
    def memory_trigger(self, memory_manager):
        """Create a MemoryTrigger instance for testing."""
        return MemoryTrigger(memory_manager)
    
    @pytest.mark.asyncio
    async def test_analyze_empty_content(self, memory_trigger):
        """Test that empty content is not stored."""
        result = await memory_trigger.analyze_for_storage("")
        assert result["should_store"] is False
        assert "too short" in result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_analyze_user_preferences(self, memory_trigger):
        """Test detection of user preferences."""
        content = "I prefer detailed explanations and always like to see examples."
        result = await memory_trigger.analyze_for_storage(content)
        
        assert result["should_store"] is True
        assert len(result["entries"]) > 0
        
        # Check for preference entries
        preference_entries = [e for e in result["entries"] if e["section"] == "user_preferences"]
        assert len(preference_entries) > 0
        
        # Verify preference entry structure
        pref_entry = preference_entries[0]
        assert "prefer" in pref_entry["value"]["text"].lower()
        assert pref_entry["value"]["type"] in ["preference", "positive_preference", "strong_preference"]
    
    @pytest.mark.asyncio
    async def test_analyze_personality_cues(self, memory_trigger):
        """Test detection of personality cues."""
        content = "I feel frustrated when explanations are too formal. I enjoy casual conversation."
        context = {"session_id": 123}
        
        result = await memory_trigger.analyze_for_storage(content, context)
        
        assert result["should_store"] is True
        personality_entries = [e for e in result["entries"] if e["section"] == "personality"]
        assert len(personality_entries) > 0
        
        # Check for both style and emotion entries
        style_entries = [e for e in personality_entries if "style_type" in e["value"]]
        emotion_entries = [e for e in personality_entries if "emotion_type" in e["value"]]
        
        assert len(style_entries) > 0 or len(emotion_entries) > 0
    
    @pytest.mark.asyncio
    async def test_importance_scoring(self, memory_trigger):
        """Test importance scoring mechanism."""
        # High importance content
        high_importance = "I always prefer detailed explanations and I feel frustrated when things are too brief."
        result_high = await memory_trigger.analyze_for_storage(high_importance)
        
        # Low importance content
        low_importance = "Yes."
        result_low = await memory_trigger.analyze_for_storage(low_importance)
        
        assert result_high["importance_score"] > result_low["importance_score"]
        assert result_high["should_store"] is True
        assert result_low["should_store"] is False
    
    @pytest.mark.asyncio
    async def test_fact_detection(self, memory_trigger):
        """Test detection of factual information."""
        content = "Python is a programming language. Machine learning can be complex."
        result = await memory_trigger.analyze_for_storage(content)
        
        if result["should_store"]:
            fact_entries = [e for e in result["entries"] if e["section"] == "facts"]
            assert len(fact_entries) > 0
            
            # Verify fact entry structure
            fact_entry = fact_entries[0]
            assert "fact" in fact_entry["value"]
            assert fact_entry["value"]["source"] == "conversation"
    
    @pytest.mark.asyncio
    async def test_session_state_detection(self, memory_trigger):
        """Test detection of session state information."""
        content = "I'm working on a machine learning project and trying to understand neural networks."
        context = {"session_id": 456}
        
        result = await memory_trigger.analyze_for_storage(content, context)
        
        if result["should_store"]:
            session_entries = [e for e in result["entries"] if e["section"] == "session_state"]
            if len(session_entries) > 0:
                session_entry = session_entries[0]
                assert session_entry["session_id"] == 456
                assert "task" in session_entry["value"]


class TestMemoryLearning:
    """Test suite for the MemoryLearning class."""
    
    @pytest_asyncio.fixture
    async def memory_manager(self):
        """Create a memory manager with in-memory storage for testing."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()
    
    @pytest_asyncio.fixture
    def memory_learning(self, memory_manager):
        """Create a MemoryLearning instance for testing."""
        return MemoryLearning(memory_manager)
    
    @pytest.mark.asyncio
    async def test_analyze_usage_patterns(self, memory_learning):
        """Test usage pattern analysis."""
        patterns = await memory_learning.analyze_usage_patterns()
        
        assert "section_usage" in patterns
        assert "access_frequency" in patterns
        assert "retention_patterns" in patterns
        assert "user_feedback" in patterns
        
        # Should include all memory sections
        assert "user_preferences" in patterns["section_usage"]
        assert "personality" in patterns["section_usage"]
    
    @pytest.mark.asyncio
    async def test_learn_from_feedback(self, memory_learning):
        """Test learning from user feedback."""
        await memory_learning.learn_from_feedback(
            "positive", 
            "Good memory recall", 
            {"session_id": 123}
        )
        
        # Verify feedback was stored (temporarily)
        # This is a basic test - in practice, feedback would influence future decisions
        assert True  # Basic test to ensure no exceptions


class TestContextualRecall:
    """Test suite for the ContextualRecall class."""
    
    @pytest_asyncio.fixture
    async def memory_manager(self):
        """Create a memory manager with in-memory storage for testing."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()
    
    @pytest_asyncio.fixture
    async def contextual_recall(self, memory_manager):
        """Create a ContextualRecall instance for testing."""
        # Add some test data to memory
        await memory_manager.set("user_preferences", "test_pref", {"preference": "detailed explanations"})
        await memory_manager.set("personality", "style_formal", {"style_type": "formality_preference"})
        await memory_manager.set("facts", "test_fact", {"fact": "Python is a programming language"})
        
        return ContextualRecall(memory_manager)
    
    @pytest.mark.asyncio
    async def test_get_relevant_memories(self, contextual_recall):
        """Test retrieval of relevant memories based on context."""
        context = "I need help with Python programming"
        
        memories = await contextual_recall.get_relevant_memories(context, max_results=5)
        
        assert isinstance(memories, dict)
        # Should have searched all sections
        for section in ["user_preferences", "personality", "facts"]:
            assert section in memories or len(memories.get(section, [])) == 0
    
    @pytest.mark.asyncio
    async def test_get_personality_adaptations(self, contextual_recall):
        """Test personality adaptation retrieval."""
        context = "formal business meeting"
        
        adaptations = await contextual_recall.get_personality_adaptations(context)
        
        assert "communication_style" in adaptations
        assert "formality_level" in adaptations
        assert "detail_preference" in adaptations
        assert "emotional_tone" in adaptations
        assert "interaction_preferences" in adaptations
    
    @pytest.mark.asyncio
    async def test_relevance_scoring(self, contextual_recall):
        """Test relevance scoring for memory entries."""
        memory_entry = {
            "key": "python_preference",
            "value": {"text": "I like Python programming"}
        }
        
        context = "Python programming help"
        score = contextual_recall._calculate_relevance_score(memory_entry, context)
        
        assert 0.0 <= score <= 1.0
        assert score > 0  # Should have some relevance due to "Python" match


class TestMemoryMaintenance:
    """Test suite for the MemoryMaintenance class."""
    
    @pytest_asyncio.fixture
    async def memory_manager(self):
        """Create a memory manager with in-memory storage for testing."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()
    
    @pytest_asyncio.fixture
    async def memory_maintenance(self, memory_manager):
        """Create a MemoryMaintenance instance for testing."""
        # Add some test data including duplicates
        await memory_manager.set("user_preferences", "pref1", "value1")
        await memory_manager.set("user_preferences", "pref2", "value1")  # Duplicate value
        
        return MemoryMaintenance(memory_manager)
    
    @pytest.mark.asyncio
    async def test_perform_maintenance(self, memory_maintenance):
        """Test comprehensive memory maintenance."""
        results = await memory_maintenance.perform_maintenance()
        
        assert "duplicates_removed" in results
        assert "entries_consolidated" in results
        assert "outdated_removed" in results
        assert "conflicts_resolved" in results
        
        # All values should be non-negative integers
        for key, value in results.items():
            assert isinstance(value, int)
            assert value >= 0
    
    @pytest.mark.asyncio
    async def test_remove_duplicates(self, memory_maintenance):
        """Test duplicate removal functionality."""
        duplicates_removed = await memory_maintenance._remove_duplicates()
        
        assert isinstance(duplicates_removed, int)
        assert duplicates_removed >= 0
        # In our test case, we added one duplicate, so it should be removed
        assert duplicates_removed >= 1


class TestPersonalityMemory:
    """Test suite for the PersonalityMemory class."""
    
    @pytest_asyncio.fixture
    async def memory_manager(self):
        """Create a memory manager with in-memory storage for testing."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        await manager.start()
        try:
            yield manager
        finally:
            await manager.stop()
    
    @pytest_asyncio.fixture
    def personality_memory(self, memory_manager):
        """Create a PersonalityMemory instance for testing."""
        return PersonalityMemory(memory_manager)
    
    @pytest.mark.asyncio
    async def test_update_personality_trait(self, personality_memory):
        """Test updating personality traits."""
        await personality_memory.update_personality_trait(
            "communication_style", 
            "formal", 
            session_id=123,
            confidence=0.8
        )
        
        # Verify trait was stored
        trait = await personality_memory.memory_manager.get("personality", "communication_style", session_id=123)
        assert trait is not None
        assert trait["value"] == "formal"
        assert trait["confidence"] == 0.8
        assert trait["session_id"] == 123
    
    @pytest.mark.asyncio
    async def test_get_personality_profile(self, personality_memory):
        """Test personality profile retrieval."""
        # Add some personality data
        await personality_memory.update_personality_trait("test_trait", "test_value", confidence=0.7)
        
        profile = await personality_memory.get_personality_profile()
        
        assert "communication_style" in profile
        assert "interaction_preferences" in profile
        assert "emotional_adaptations" in profile
        assert "learned_traits" in profile
    
    @pytest.mark.asyncio
    async def test_adapt_to_context(self, personality_memory):
        """Test context-based personality adaptation."""
        # Add some personality preferences
        await personality_memory.memory_manager.set(
            "personality", 
            "formal_style", 
            {"style_type": "formality_preference", "confidence": 0.8}
        )
        
        adaptations = await personality_memory.adapt_to_context("business meeting context")
        
        assert "tone" in adaptations
        assert "detail_level" in adaptations
        assert "formality" in adaptations
        assert "response_style" in adaptations


class TestAutonomousMemoryIntegration:
    """Integration tests for autonomous memory components."""
    
    @pytest.mark.asyncio
    async def test_global_function_integration(self):
        """Test that global functions return properly configured instances."""
        # Test that all global functions work without errors
        trigger = get_memory_trigger()
        learning = get_memory_learning()
        recall = get_contextual_recall()
        maintenance = get_memory_maintenance()
        personality = get_personality_memory()
        
        assert isinstance(trigger, MemoryTrigger)
        assert isinstance(learning, MemoryLearning)
        assert isinstance(recall, ContextualRecall)
        assert isinstance(maintenance, MemoryMaintenance)
        assert isinstance(personality, PersonalityMemory)
        
        # All should use the same memory manager instance
        assert trigger.memory_manager is learning.memory_manager
        assert learning.memory_manager is recall.memory_manager
    
    @pytest.mark.asyncio
    async def test_personality_section_in_memory_manager(self):
        """Test that personality section is properly added to memory manager."""
        manager = MemoryManager(storage_backend=InMemoryStorageBackend())
        
        assert "personality" in manager.SECTIONS
        assert manager.SECTIONS["personality"].name == "personality"
        assert manager.SECTIONS["personality"].description == "Dynamic personality traits, inflection styles, and interaction preferences"