"""
REST API for the unified Nagatha server.
"""

import asyncio
from typing import Dict, Any, Optional
from aiohttp import web
from nagatha_assistant.utils.logger import get_logger

logger = get_logger(__name__)


class RESTAPI:
    """REST API for the unified server."""
    
    def __init__(self, server):
        self.server = server
        self.app = web.Application()
        self.runner = None
        self.site = None
        
    async def start(self):
        """Start the REST API server."""
        logger.info("Starting REST API server")
        
        # Add routes
        self.app.router.add_get('/health', self._health_check)
        self.app.router.add_get('/status', self._get_status)
        self.app.router.add_post('/process_message', self._process_message)
        self.app.router.add_get('/sessions', self._list_sessions)
        self.app.router.add_post('/sessions', self._create_session)
        self.app.router.add_get('/sessions/{session_id}', self._get_session)
        self.app.router.add_post('/sessions/{session_id}/messages', self._send_message)
        
        # Start the server
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Use a different port for the REST API (main server port + 1)
        rest_port = self.server.config.port + 1
        self.site = web.TCPSite(
            self.runner, 
            self.server.config.host, 
            rest_port
        )
        await self.site.start()
        
        logger.info(f"REST API server started on {self.server.config.host}:{rest_port}")
    
    async def stop(self):
        """Stop the REST API server."""
        logger.info("Stopping REST API server")
        
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("REST API server stopped")
    
    async def _health_check(self, request):
        """Health check endpoint."""
        return web.json_response({"status": "healthy", "service": "nagatha_unified_server"})
    
    async def _get_status(self, request):
        """Get server status."""
        try:
            status = await self.server.get_server_status()
            return web.json_response(status)
        except Exception as e:
            logger.exception(f"Error getting status: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _process_message(self, request):
        """Process a message through the unified server."""
        try:
            data = await request.json()
            
            message = data.get('message')
            user_id = data.get('user_id')
            interface = data.get('interface', 'unknown')
            interface_context = data.get('interface_context', {})
            
            print(f"DEBUG: API received message: {message} from user: {user_id}")
            
            if not message or not user_id:
                return web.json_response(
                    {"error": "Missing required fields: message, user_id"}, 
                    status=400
                )
            
            # Process message through unified server
            response = await self.server.process_message(
                message=message,
                user_id=user_id,
                interface=interface,
                interface_context=interface_context
            )
            
            print(f"DEBUG: API response: {response}")
            return web.json_response({"response": response})
            
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _list_sessions(self, request):
        """List active sessions."""
        try:
            sessions = await self.server.list_active_sessions()
            return web.json_response({"sessions": sessions})
        except Exception as e:
            logger.exception(f"Error listing sessions: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _create_session(self, request):
        """Create a new session."""
        try:
            data = await request.json()
            user_id = data.get('user_id', 'anonymous')
            interface = data.get('interface', 'api')
            interface_context = data.get('interface_context', {})
            
            # Create session through unified server
            session_id = await self.server.session_manager.get_or_create_session(
                user_id=user_id,
                interface=interface,
                interface_context=interface_context
            )
            
            return web.json_response({"session_id": session_id})
        except Exception as e:
            logger.exception(f"Error creating session: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _get_session(self, request):
        """Get session information."""
        try:
            session_id = request.match_info['session_id']
            session_info = await self.server.get_session_info(session_id)
            
            if session_info:
                return web.json_response(session_info)
            else:
                return web.json_response({"error": "Session not found"}, status=404)
        except Exception as e:
            logger.exception(f"Error getting session: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _send_message(self, request):
        """Send a message to a specific session."""
        try:
            session_id = request.match_info['session_id']
            data = await request.json()
            message = data.get('message')
            
            if not message:
                return web.json_response(
                    {"error": "Missing required field: message"}, 
                    status=400
                )
            
            # Process message through unified server
            response = await self.server.process_message(
                message=message,
                user_id=f"session:{session_id}",
                interface="api",
                interface_context={"session_id": session_id}
            )
            
            return web.json_response({"response": response})
        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            return web.json_response({"error": str(e)}, status=500) 