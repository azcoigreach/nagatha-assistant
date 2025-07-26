#!/usr/bin/env python3
"""
Pytest tests for the personality module functionality.
"""

import pytest
from nagatha_assistant.core.personality import get_system_prompt


class TestPersonality:
    """Test cases for the personality module."""

    def test_get_system_prompt_no_tools(self):
        """Test system prompt generation with no tools."""
        tools = []
        prompt = get_system_prompt(tools)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Nagatha" in prompt
        assert "communications ai" in prompt.lower()
        # Should contain message about no specialized tools being available
        assert "without specialized tools" in prompt.lower()

    def test_get_system_prompt_with_tools(self):
        """Test system prompt generation with tools."""
        tools = [
            {
                'name': 'test_tool',
                'description': 'A test tool for testing',
                'server': 'test_server'
            },
            {
                'name': 'another_tool',
                'description': 'Another tool for testing',
                'server': 'test_server'
            }
        ]
        
        prompt = get_system_prompt(tools)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Nagatha" in prompt
        assert "test_tool" in prompt
        assert "another_tool" in prompt
        assert "A test tool for testing" in prompt
        assert "Another tool for testing" in prompt

    def test_get_system_prompt_tool_formatting(self):
        """Test that tools are properly formatted in the system prompt."""
        tools = [
            {
                'name': 'format_test_tool',
                'description': 'Tool with special characters: @#$%',
                'server': 'special_server'
            }
        ]
        
        prompt = get_system_prompt(tools)
        
        assert "format_test_tool" in prompt
        assert "Tool with special characters: @#$%" in prompt
        assert "special_server" in prompt

    def test_get_system_prompt_empty_tool_fields(self):
        """Test system prompt with tools that have empty fields."""
        tools = [
            {
                'name': 'empty_desc_tool',
                'description': '',
                'server': 'test_server'
            },
            {
                'name': '',
                'description': 'Tool with empty name',
                'server': 'test_server'
            }
        ]
        
        prompt = get_system_prompt(tools)
        
        # Should handle empty fields gracefully
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_system_prompt_consistency(self):
        """Test that system prompt is consistent across calls."""
        tools = [
            {
                'name': 'consistent_tool',
                'description': 'A consistent tool',
                'server': 'test_server'
            }
        ]
        
        prompt1 = get_system_prompt(tools)
        prompt2 = get_system_prompt(tools)
        
        assert prompt1 == prompt2

    def test_get_system_prompt_large_tool_list(self):
        """Test system prompt with a large number of tools."""
        tools = []
        for i in range(50):
            tools.append({
                'name': f'tool_{i}',
                'description': f'Description for tool {i}',
                'server': f'server_{i % 5}'  # 5 different servers
            })
        
        prompt = get_system_prompt(tools)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should contain some of the tools
        assert 'tool_0' in prompt
        assert 'tool_49' in prompt 