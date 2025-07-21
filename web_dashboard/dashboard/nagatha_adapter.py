"""
Adapter to interface between Django and the existing Nagatha Assistant core.

This module provides an async interface to the Nagatha Assistant functionality
for use within the Django web application.
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Add the src directory to Python path to import Nagatha components
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

logger = logging.getLogger(__name__)


class NagathaAdapter:
    """
    Adapter class to interface with Nagatha Assistant core functionality.
    
    This provides a bridge between the Django web application and the
    existing Nagatha Assistant infrastructure.
    """
    
    def __init__(self):
        self._agent = None
        self._mcp_manager = None
        self._event_bus = None
    
    async def _ensure_initialized(self):
        """Ensure Nagatha components are initialized."""
        if self._agent is None:
            try:
                # Import Nagatha components
                from nagatha_assistant.core import agent
                from nagatha_assistant.core.mcp_manager import get_mcp_manager
                from nagatha_assistant.core.event_bus import ensure_event_bus_started
                
                # Initialize components
                await ensure_event_bus_started()
                self._mcp_manager = await get_mcp_manager()
                self._agent = agent
                
                logger.info("Nagatha components initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize Nagatha components: {e}")
                raise
    
    async def send_message(self, session_id: Optional[int], message: str) -> str:
        """
        Send a message to Nagatha Assistant.
        
        Args:
            session_id: Nagatha session ID (if None, will create new session)
            message: User message to send
            
        Returns:
            Assistant response string
        """
        await self._ensure_initialized()
        
        try:
            # Create session if needed
            if session_id is None:
                session_id = await self._agent.start_session()
                logger.info(f"Created new Nagatha session: {session_id}")
            
            # Send message and get response
            response = await self._agent.send_message(session_id, message)
            
            logger.info(f"Processed message in session {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error sending message to Nagatha: {e}")
            raise
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status from Nagatha.
        
        Returns:
            Dictionary with system status information
        """
        await self._ensure_initialized()
        
        try:
            # Get MCP status
            mcp_status = await self._agent.get_mcp_status()
            summary = mcp_status.get('summary', {})
            
            # Get system metrics (if available)
            try:
                import psutil
                cpu_usage = psutil.cpu_percent()
                memory_usage = psutil.virtual_memory().percent
                disk_usage = psutil.disk_usage('/').percent
            except ImportError:
                cpu_usage = None
                memory_usage = None
                disk_usage = None
            
            # Count active sessions (approximate)
            # This would need to be implemented in the core if needed
            active_sessions = 1  # Placeholder
            
            status = {
                'mcp_servers_connected': summary.get('connected', 0),
                'total_tools_available': summary.get('total_tools', 0),
                'active_sessions': active_sessions,
                'system_health': 'healthy' if summary.get('connected', 0) > 0 else 'degraded',
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': disk_usage,
                'additional_metrics': {
                    'mcp_summary': summary,
                    'nagatha_version': '1.0.0'  # Would get from nagatha_assistant.__version__
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'mcp_servers_connected': 0,
                'total_tools_available': 0,
                'active_sessions': 0,
                'system_health': 'error',
                'cpu_usage': None,
                'memory_usage': None,
                'disk_usage': None,
                'additional_metrics': {'error': str(e)}
            }
    
    async def start_session(self) -> int:
        """
        Start a new Nagatha session.
        
        Returns:
            New session ID
        """
        await self._ensure_initialized()
        
        try:
            session_id = await self._agent.start_session()
            logger.info(f"Started new Nagatha session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error starting Nagatha session: {e}")
            raise
    
    async def get_session_messages(self, session_id: int) -> list:
        """
        Get messages from a Nagatha session.
        
        Args:
            session_id: Nagatha session ID
            
        Returns:
            List of message dictionaries
        """
        await self._ensure_initialized()
        
        try:
            # This would need to be implemented in the core
            # For now, return empty list
            messages = []
            
            logger.info(f"Retrieved messages for session {session_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Error getting session messages: {e}")
            raise
    
    async def get_available_tools(self) -> Dict[str, Any]:
        """
        Get available MCP tools.
        
        Returns:
            Dictionary with tool information
        """
        await self._ensure_initialized()
        
        try:
            mcp_status = await self._agent.get_mcp_status()
            tools_info = mcp_status.get('servers', {})
            
            return {
                'tools': tools_info,
                'total_count': sum(len(server.get('tools', [])) for server in tools_info.values())
            }
            
        except Exception as e:
            logger.error(f"Error getting available tools: {e}")
            return {'tools': {}, 'total_count': 0}