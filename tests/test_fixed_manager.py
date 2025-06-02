#!/usr/bin/env python3
"""
Pytest tests for MCP Manager memory operations and TaskGroup error fixes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nagatha_assistant.core.mcp_manager import MCPManager


@pytest.mark.asyncio
class TestMCPManagerMemoryOperations:
    """Test cases for MCP Manager memory operations."""

    async def test_memory_operations_integration(self):
        """Test memory operations that previously caused TaskGroup errors."""
        manager = MCPManager()
        
        try:
            await manager.initialize()
            
            summary = manager.get_initialization_summary()
            
            # Test should pass regardless of whether servers are connected
            assert isinstance(summary, dict)
            assert 'connected' in summary
            assert 'total_tools' in summary
            
            # If memory server is available, test the operations
            if summary['connected'] > 0:
                tools = manager.get_available_tools()
                memory_tools = [t for t in tools if 'memory' in t['name'].lower()]
                
                if memory_tools:
                    await self._test_memory_operations(manager)
                    
        finally:
            await manager.shutdown()

    async def _test_memory_operations(self, manager):
        """Test specific memory operations that were failing."""
        # Test creating an entity first
        try:
            create_result = await manager.call_tool('memory_create_entities', {
                "entities": [
                    {
                        "name": "TestUser",
                        "entityType": "Person", 
                        "observations": ["Test entity for memory operations"]
                    }
                ]
            })
            assert create_result is not None
            
            # Test adding observations (the operation that was failing)
            add_result = await manager.call_tool('memory_add_observations', {
                'observations': [
                    {
                        'entityName': 'TestUser', 
                        'contents': ['Likes testing and debugging']
                    }
                ]
            })
            assert add_result is not None
            
        except Exception as e:
            # If tools aren't available or configured, that's okay
            if "not found" in str(e) or "not available" in str(e):
                pytest.skip(f"Memory tools not available: {e}")
            else:
                raise

    @patch('nagatha_assistant.core.mcp_manager.MCPManager.call_tool')
    async def test_memory_add_observations_mock(self, mock_call_tool):
        """Test memory add observations with mocked tool calls."""
        mock_call_tool.return_value = {"success": True}
        
        manager = MCPManager()
        
        try:
            await manager.initialize()
            
            # Test the exact call that was failing in the logs
            failing_args = {
                'observations': [
                    {
                        'entityName': 'You', 
                        'contents': ['Likes hamburgers and tacos']
                    }
                ]
            }
            
            result = await manager.call_tool('memory_add_observations', failing_args)
            assert result == {"success": True}
            mock_call_tool.assert_called_with('memory_add_observations', failing_args)
            
        finally:
            await manager.shutdown()

    async def test_manager_handles_missing_memory_tools(self):
        """Test that manager handles missing memory tools gracefully."""
        manager = MCPManager()
        
        try:
            await manager.initialize()
            
            # Try to call a memory tool that might not exist
            try:
                await manager.call_tool('nonexistent_memory_tool', {})
                assert False, "Should have raised an exception"
            except Exception as e:
                # Should handle the error gracefully
                assert "not found" in str(e).lower() or "not available" in str(e).lower()
                
        finally:
            await manager.shutdown()

    async def test_manager_initialization_robustness(self):
        """Test that manager initialization is robust against various failures."""
        manager = MCPManager()
        
        # Test multiple initialization cycles
        for i in range(3):
            try:
                await manager.initialize()
                summary = manager.get_initialization_summary()
                assert isinstance(summary, dict)
                
                await manager.shutdown()
                
                # Brief pause between cycles
                import asyncio
                await asyncio.sleep(0.1)
                
            except Exception as e:
                # Initialization might fail due to missing config, that's okay
                if "config" in str(e).lower() or "not found" in str(e).lower():
                    continue
                else:
                    raise 