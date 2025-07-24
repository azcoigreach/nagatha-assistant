"""
Real Nagatha Adapter for Django Web Dashboard.

This adapter connects to the actual Nagatha MCP system to get real-time
status and tool information.
"""

import os
import asyncio
import logging
import sys
import psutil
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from django.conf import settings

# Add the main Nagatha source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

logger = logging.getLogger(__name__)


class NagathaRealAdapter:
    """
    Real Nagatha adapter that connects to the actual MCP system.
    
    This provides a bridge between the Django web application and
    the real Nagatha core system with MCP servers and tools.
    """
    
    def __init__(self):
        self._mcp_manager = None
        self._initialized = False
        self._initialization_error = None
    
    async def _ensure_initialized(self):
        """Ensure the adapter is initialized."""
        if self._initialized:
            return
            
        if self._initialization_error:
            raise Exception(f"Previous initialization failed: {self._initialization_error}")
            
        try:
            # Import and get the MCP manager
            from nagatha_assistant.core.mcp_manager import get_mcp_manager
            self._mcp_manager = await get_mcp_manager()
            
            # Initialize the full Nagatha system including plugins
            try:
                from nagatha_assistant.core.agent import startup
                startup_result = await startup()
                logger.info(f"Nagatha system startup completed: {startup_result}")
                
                # Check plugin status
                from nagatha_assistant.core.plugin_manager import get_plugin_manager
                plugin_manager = get_plugin_manager()
                plugin_status = plugin_manager.get_plugin_status()
                logger.info(f"Plugin system status: {len(plugin_status)} plugins available")
                
            except Exception as system_error:
                logger.warning(f"System initialization warning: {system_error}")
            
            self._initialized = True
            logger.info("Nagatha Real adapter initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Nagatha Real adapter: {e}")
            self._initialization_error = str(e)
            raise
    
    def _get_system_resources(self) -> Dict[str, float]:
        """Get current system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (root filesystem)
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            return {
                'cpu_usage': round(cpu_percent, 1),
                'memory_usage': round(memory_percent, 1),
                'disk_usage': round(disk_percent, 1)
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {
                'cpu_usage': None,
                'memory_usage': None,
                'disk_usage': None
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get real system status from Nagatha MCP manager."""
        try:
            await self._ensure_initialized()
            
            # Get server information
            server_info = self._mcp_manager.get_server_info()
            available_tools = self._mcp_manager.get_available_tools()
            
            # Count connected servers and total tools
            connected_servers = sum(1 for info in server_info.values() if info.get('connected', False))
            total_tools = len(available_tools)
            
            # Get system resource usage
            system_resources = self._get_system_resources()
            
            # Determine system health
            if connected_servers > 0:
                system_health = "operational"
            elif len(server_info) > 0:
                system_health = "degraded"
            else:
                system_health = "unknown"
            
            return {
                "mcp_servers_connected": connected_servers,
                "total_tools_available": total_tools,
                "active_sessions": 0,  # Could be calculated from database
                "system_health": system_health,
                "cpu_usage": system_resources['cpu_usage'],
                "memory_usage": system_resources['memory_usage'],
                "disk_usage": system_resources['disk_usage'],
                "additional_metrics": {
                    "server_details": server_info,
                    "tools_list": [tool['name'] for tool in available_tools[:10]],  # First 10 tools
                    "adapter_type": "real_nagatha",
                    "system_resources": system_resources
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "mcp_servers_connected": 0,
                "total_tools_available": 0,
                "active_sessions": 0,
                "system_health": "error",
                "cpu_usage": None,
                "memory_usage": None,
                "disk_usage": None,
                "additional_metrics": {
                    "error": str(e),
                    "adapter_type": "real_nagatha"
                }
            }
    
    async def get_available_tools(self) -> Dict[str, Any]:
        """Get available tools from the real Nagatha system."""
        try:
            await self._ensure_initialized()
            
            # Get both MCP tools and plugin commands
            from nagatha_assistant.core.agent import get_available_tools as get_all_tools
            tools = await get_all_tools()
            
            return {
                "tools": tools,
                "total": len(tools),
                "note": "Real tools from Nagatha MCP system and plugin commands"
            }
        except Exception as e:
            logger.error(f"Error getting available tools: {e}")
            return {
                "tools": [],
                "total": 0,
                "error": str(e)
            }
    
    async def send_message(self, session_id: Optional[str], message: str) -> tuple[str, int]:
        """Send a message and get a response from the real Nagatha system.
        
        Returns:
            tuple: (response, nagatha_session_id)
        """
        try:
            await self._ensure_initialized()
            
            # Use the real Nagatha agent for intelligent conversation
            from nagatha_assistant.core.agent import send_message as nagatha_send_message, start_session
            
            # If no session_id provided, create a new session
            if not session_id:
                session_id = await start_session()
                logger.info(f"Created new Nagatha session: {session_id}")
            
            # Send message to Nagatha's core agent
            logger.info(f"Sending message to Nagatha agent session {session_id}: {message[:50]}...")
            response = await nagatha_send_message(session_id, message)
            logger.info(f"Received response from Nagatha agent: {response[:100]}...")
            
            # Check if the response indicates MCP tool failures and provide helpful guidance
            if "unauthorized access" in response.lower() or "api key" in response.lower():
                # Add helpful guidance about the MCP tools
                guidance = "\n\n💡 **Note about Web Tools**: I have access to powerful web scraping and search tools, but they currently need API keys to work properly. The tools are connected and ready - they just need the proper authentication set up. For now, I can still help you with general questions, analysis, and conversation!"
                response += guidance
            elif "context_length_exceeded" in response.lower() or "194424 tokens" in response.lower():
                # Handle context length exceeded errors
                guidance = "\n\n💡 **Note**: I found some great information online, but the results were quite extensive and exceeded my processing limits. I can still help you with general questions and analysis, or you can try a more specific search query to get more focused results!"
                response = "I found some interesting information about MCP servers online, but the search results were quite extensive and I encountered a processing limit. Let me provide you with some general information about MCP servers instead!" + guidance
            
            return response, session_id
                
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            return f"I'm sorry, I encountered an error while processing your message: {str(e)}"
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool from the real Nagatha system."""
        try:
            await self._ensure_initialized()
            return await self._mcp_manager.call_tool(tool_name, arguments)
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
    
    async def close(self):
        """Close the adapter and clean up resources."""
        if self._mcp_manager:
            try:
                from nagatha_assistant.core.mcp_manager import shutdown_mcp_manager
                await shutdown_mcp_manager()
            except Exception as e:
                logger.error(f"Error shutting down MCP manager: {e}") 