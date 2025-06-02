#!/usr/bin/env python3
"""
Pytest tests for the MCP Manager functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nagatha_assistant.core.mcp_manager import MCPManager


@pytest.mark.asyncio
class TestMCPManager:
    """Test cases for the MCP Manager."""

    async def test_mcp_manager_initialization(self):
        """Test the MCP Manager can be initialized."""
        manager = MCPManager()
        assert manager is not None
        assert not manager._initialized

    async def test_mcp_manager_initialize_and_shutdown(self):
        """Test the MCP Manager initialization and shutdown cycle."""
        manager = MCPManager()
        
        try:
            await manager.initialize()
            
            summary = manager.get_initialization_summary()
            assert isinstance(summary, dict)
            assert 'total_configured' in summary
            assert 'connected' in summary
            assert 'failed' in summary
            assert 'total_tools' in summary
            
        finally:
            await manager.shutdown()

    async def test_get_available_tools(self):
        """Test getting available tools from MCP Manager."""
        manager = MCPManager()
        
        try:
            await manager.initialize()
            tools = manager.get_available_tools()
            assert isinstance(tools, list)
            
            # Each tool should have required fields
            for tool in tools:
                assert 'name' in tool
                assert 'server' in tool
                
        finally:
            await manager.shutdown()

    async def test_get_server_info(self):
        """Test getting server information."""
        manager = MCPManager()
        
        try:
            await manager.initialize()
            server_info = manager.get_server_info()
            assert isinstance(server_info, dict)
            
        finally:
            await manager.shutdown()

    @patch('nagatha_assistant.core.mcp_manager.MCPManager.call_tool')
    async def test_tool_calling(self, mock_call_tool):
        """Test calling tools through the MCP Manager."""
        mock_call_tool.return_value = {"result": "test"}
        
        manager = MCPManager()
        
        try:
            await manager.initialize()
            
            # Mock a simple tool call
            result = await manager.call_tool('test_tool', {'param': 'value'})
            assert result == {"result": "test"}
            mock_call_tool.assert_called_once_with('test_tool', {'param': 'value'})
            
        finally:
            await manager.shutdown()

    async def test_graceful_handling_no_config(self):
        """Test that MCP Manager handles missing configuration gracefully."""
        with patch('os.path.exists', return_value=False):
            manager = MCPManager()
            
            try:
                await manager.initialize()
                summary = manager.get_initialization_summary()
                
                # Should handle missing config gracefully
                assert summary['total_configured'] == 0
                assert summary['connected'] == 0
                
            finally:
                await manager.shutdown() 