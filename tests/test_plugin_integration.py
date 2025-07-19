"""
Integration test for plugin system with agent.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock

from nagatha_assistant.core import get_event_bus, initialize_plugin_system
from nagatha_assistant.core.agent import get_available_tools, call_tool_or_command


@pytest.mark.asyncio
async def test_plugin_system_integration():
    """Test that the plugin system integrates with the agent tools."""
    # Start event bus 
    event_bus = get_event_bus()
    await event_bus.start()
    
    try:
        # Initialize plugin system
        await initialize_plugin_system()
        
        # Get available tools (should include echo command)
        tools = await get_available_tools()
        
        # Find the echo command
        echo_tool = None
        for tool in tools:
            if tool["name"] == "echo":
                echo_tool = tool
                break
        
        assert echo_tool is not None, "Echo command should be available"
        assert echo_tool["description"] == "Echo back the provided text"
        assert "plugin:" in echo_tool["server"]
        
        # Test calling the echo command
        result = await call_tool_or_command("echo", {"text": "from plugin"})
        assert result == "from plugin"
        
    finally:
        await event_bus.stop()


@pytest.mark.asyncio
async def test_echo_plugin_matches_existing_test():
    """Test that echo plugin works exactly like the existing test expects."""
    # Start event bus and plugin system
    event_bus = get_event_bus()
    await event_bus.start()
    
    try:
        await initialize_plugin_system()
        
        # Test the exact scenario from test_chat_plugins.py
        result = await call_tool_or_command("echo", {"text": "from plugin"})
        assert result == "from plugin"
        
    finally:
        await event_bus.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_plugin_system_integration())
    asyncio.run(test_echo_plugin_matches_existing_test())
    print("All integration tests passed!")