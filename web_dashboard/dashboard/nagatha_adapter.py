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
from django.conf import settings

# Add the src directory to Python path to import Nagatha components
# Try multiple possible paths for the Nagatha source
possible_src_paths = [
    Path(__file__).parent.parent.parent / "src",
    Path(__file__).parent.parent.parent.parent / "src",
    Path("/app/nagatha_src"),  # Docker container path
    Path("/app/src"),  # Alternative Docker path
]

src_path = None
for path in possible_src_paths:
    if path.exists() and (path / "nagatha_assistant").exists():
        src_path = path
        break

if src_path:
    sys.path.insert(0, str(src_path))
    logger = logging.getLogger(__name__)
    logger.info(f"Added Nagatha source path: {src_path}")
else:
    logger = logging.getLogger(__name__)
    logger.warning("Could not find Nagatha source directory. Core functionality will be limited.")

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
        self._initialized = False
        self._initialization_error = None
    
    async def _ensure_initialized(self):
        """Ensure Nagatha components are initialized."""
        if self._initialized:
            return
            
        if self._initialization_error:
            raise Exception(f"Previous initialization failed: {self._initialization_error}")
            
        try:
            # Set the database URL from Django settings
            nagatha_db_url = getattr(settings, 'NAGATHA_DATABASE_URL', 'sqlite:///nagatha.db')
            if nagatha_db_url.startswith("sqlite:///") and not nagatha_db_url.startswith("sqlite+aiosqlite:///"):
                nagatha_db_url = nagatha_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
            
            # Set the environment variable for Nagatha to use
            os.environ['DATABASE_URL'] = nagatha_db_url
            
            # Check if we can import Nagatha components
            try:
                from nagatha_assistant.core import agent
                from nagatha_assistant.core.mcp_manager import get_mcp_manager
                from nagatha_assistant.core.event_bus import ensure_event_bus_started
                from nagatha_assistant.db import ensure_schema
            except ImportError as e:
                logger.error(f"Failed to import Nagatha components: {e}")
                self._initialization_error = f"Import error: {e}"
                raise Exception(f"Nagatha core components not available: {e}")
            
            # Ensure database schema is set up first
            try:
                await ensure_schema()
                logger.info("Database schema ensured")
            except Exception as e:
                logger.warning(f"Database schema setup warning: {e}")
                # Continue anyway, the database might already be set up
            
            # Initialize components
            try:
                await ensure_event_bus_started()
                self._mcp_manager = await get_mcp_manager()
                self._agent = agent
                self._initialized = True
                
                logger.info("Nagatha components initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize Nagatha components: {e}")
                self._initialization_error = f"Initialization error: {e}"
                raise
                
        except Exception as e:
            logger.error(f"Failed to initialize Nagatha components: {e}")
            self._initialization_error = str(e)
            raise
    
    async def send_message(self, session_id: Optional[int], message: str) -> str:
        """Send a message to Nagatha Assistant and get a response."""
        try:
            await self._ensure_initialized()
            
            # Ensure we have a proper event loop context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = True
            else:
                should_close_loop = False
            
            try:
                # Create a new session if none provided
                if session_id is None:
                    session_id = await self.start_session()
                
                # Send message through the agent
                response = await self._agent.send_message(session_id, message)
                
                return response
                
            finally:
                if should_close_loop and loop and not loop.is_closed():
                    loop.close()
                    
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Check if this is a greenlet error
            if "greenlet_spawn" in str(e) or "await_only" in str(e):
                # Provide a helpful response for greenlet errors
                return self._get_fallback_response(message)
            else:
                # Return a user-friendly error message for other errors
                return f"I'm sorry, I encountered an error while processing your message: {str(e)}"
    
    def _get_fallback_response(self, message: str) -> str:
        """Provide a fallback response when the core is not available."""
        message_lower = message.lower()
        
        # Simple keyword-based responses
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            return "Hello! I'm Nagatha Assistant. I'm currently running in a limited mode due to some technical configuration issues, but I'm here to help with basic questions. How can I assist you today?"
        
        elif any(word in message_lower for word in ['help', 'assist', 'support']):
            return "I'm here to help! I can assist with basic questions and provide information. While my full capabilities are currently limited due to technical configuration, I'm working to get everything fully operational. What would you like to know?"
        
        elif any(word in message_lower for word in ['what', 'how', 'why', 'when', 'where']):
            return "That's an interesting question! I'm currently operating in a limited mode while we resolve some technical configuration issues with my core systems. I'd be happy to help with basic information, but for more complex queries, you might want to try again once the full system is online."
        
        elif any(word in message_lower for word in ['status', 'working', 'broken', 'error']):
            return "I'm currently running in a limited mode. My core systems are partially operational, but there are some technical configuration issues that need to be resolved. The team is working on getting everything fully functional. I can still help with basic questions though!"
        
        elif any(word in message_lower for word in ['thanks', 'thank you', 'appreciate']):
            return "You're welcome! I'm glad I could help, even in this limited mode. Once the technical issues are resolved, I'll be able to provide much more comprehensive assistance."
        
        else:
            return "I understand your message. I'm currently operating in a limited mode while we resolve some technical configuration issues with my core systems. I can help with basic questions and provide general assistance. What would you like to know?"
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status information from Nagatha Assistant."""
        try:
            await self._ensure_initialized()
            
            # Ensure we have a proper event loop context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = True
            else:
                should_close_loop = False
            
            try:
                # Get MCP server status
                mcp_status = await self._mcp_manager.get_status()
                
                # Get basic system metrics
                status_info = {
                    'mcp_servers_connected': mcp_status.get('connected_servers', 0),
                    'total_tools_available': mcp_status.get('total_tools', 0),
                    'active_sessions': 0,  # TODO: Implement session tracking
                    'system_health': 'healthy' if mcp_status.get('connected_servers', 0) > 0 else 'degraded',
                    'cpu_usage': None,  # TODO: Implement system monitoring
                    'memory_usage': None,
                    'disk_usage': None,
                    'additional_metrics': {
                        'mcp_summary': mcp_status,
                        'nagatha_version': '1.0.0'
                    }
                }
                
                return status_info
                
            finally:
                if should_close_loop and loop and not loop.is_closed():
                    loop.close()
                    
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Check if this is a greenlet error
            if "greenlet_spawn" in str(e) or "await_only" in str(e):
                logger.info("Greenlet error detected, using fallback system status")
            
            # Return fallback status
            return {
                'mcp_servers_connected': 0,
                'total_tools_available': 0,
                'active_sessions': 0,
                'system_health': 'degraded',
                'cpu_usage': None,
                'memory_usage': None,
                'disk_usage': None,
                'additional_metrics': {
                    'mcp_summary': {'error': str(e), 'status': 'limited_mode'},
                    'nagatha_version': '1.0.0'
                }
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