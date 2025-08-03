"""
Core Unified Server for Nagatha Assistant.

This module provides the main server class that unifies all Nagatha components
into a single consciousness that can be accessed by multiple interfaces.
"""

import asyncio
import signal
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import os

from nagatha_assistant.utils.logger import get_logger

# Import agent functions for real AI processing
from nagatha_assistant.core.agent import send_message, startup, shutdown as agent_shutdown, start_session

# Import API components
from .api.rest import RESTAPI


@dataclass
class ServerConfig:
    """Configuration for the unified server."""
    host: str = "localhost"
    port: int = 8080
    max_connections_per_server: int = 3
    session_timeout_hours: int = 24
    cleanup_interval_minutes: int = 30
    enable_websocket: bool = True
    enable_rest: bool = True
    enable_events: bool = True


class NagathaUnifiedServer:
    """
    Unified server that provides single consciousness across interfaces.
    
    This server:
    - Manages unified sessions across all interfaces
    - Shares MCP connections efficiently
    - Provides single agent instance for all requests
    - Coordinates multi-user interactions
    - Maintains shared memory and state
    """
    
    def __init__(self, config: ServerConfig = None):
        self.logger = get_logger(__name__)
        self.config = config or ServerConfig()
        
        # Core components - will be initialized during startup
        self.memory_manager = None
        self.mcp_manager = None
        self.celery_app = None
        self.event_bus = None
        self.plugin_manager = None
        self._agent_initialized = False
        
        # Unified components
        self.session_manager = AgentSessionManager()
        self.connection_pool = None
        
        # Server state
        self._running = False
        self._start_time = None
        self._shutdown_event = asyncio.Event()
        
        # API components (will be initialized later)
        self.websocket_api = None
        self.rest_api = None
        self.events_api = None
        
        # Statistics
        self.stats = {
            "start_time": None,
            "total_requests": 0,
            "active_sessions": 0,
            "total_users": 0,
            "uptime_seconds": 0
        } 
    
    async def start(self):
        """Start the unified server."""
        self.logger.info("Starting Nagatha Unified Server")
        
        try:
            # Set up signal handlers
            self._setup_signal_handlers()
            
            # Initialize the agent system first
            self.logger.info("Initializing Nagatha agent system...")
            try:
                agent_status = await startup()
                self._agent_initialized = True
                self.logger.info(f"Agent system initialized successfully: {agent_status}")
            except Exception as e:
                self.logger.error(f"Failed to initialize agent system: {e}")
                # Continue anyway - some functionality may work without full agent
                self._agent_initialized = False
            
            # Update server state
            self._running = True
            self._start_time = datetime.now()
            self.stats["start_time"] = self._start_time.isoformat()
            
            # Start API components
            if self.config.enable_rest:
                self.logger.info("Starting REST API")
                self.rest_api = RESTAPI(self)
                await self.rest_api.start()
            
            # Write status to file for CLI status command
            import json
            status_file = "/tmp/nagatha_server_status.json"
            status_data = {
                "running": True,
                "start_time": self._start_time.isoformat(),
                "port": self.config.port,
                "host": self.config.host,
                "pid": os.getpid()
            }
            with open(status_file, 'w') as f:
                json.dump(status_data, f)
            
            self.logger.info("Nagatha Unified Server started successfully")
            self.logger.info(f"Server running on {self.config.host}:{self.config.port}")
            if self.rest_api:
                self.logger.info(f"REST API running on {self.config.host}:{self.config.port + 1}")
            self.logger.info(f"Agent system: {'initialized' if self._agent_initialized else 'failed to initialize'}")
            
            # Keep the server running
            self.logger.info("Server is now running and ready to accept connections")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise
        finally:
            # Only stop if we actually started successfully
            if self._running:
                await self.stop()
    
    async def stop(self):
        """Stop the unified server."""
        if not self._running:
            return
        
        self.logger.info("Stopping Nagatha Unified Server")
        
        try:
            # Stop API components
            if self.rest_api:
                await self.rest_api.stop()
            
            # Shutdown agent system if it was initialized
            if self._agent_initialized:
                self.logger.info("Shutting down agent system...")
                try:
                    await agent_shutdown()
                    self.logger.info("Agent system shutdown complete")
                except Exception as e:
                    self.logger.error(f"Error shutting down agent system: {e}")
            
            # Update server state
            self._running = False
            
            # Remove status file
            import os
            status_file = "/tmp/nagatha_server_status.json"
            if os.path.exists(status_file):
                os.remove(status_file)
            
            # Calculate uptime
            if self._start_time:
                uptime = (datetime.now() - self._start_time).total_seconds()
                self.stats["uptime_seconds"] = uptime
                self.logger.info(f"Server uptime: {uptime:.2f} seconds")
            
            self.logger.info("Nagatha Unified Server stopped")
            
        except Exception as e:
            self.logger.error(f"Error during server shutdown: {e}")
    
    async def process_message(self, message: str, user_id: str, interface: str, interface_context: Dict[str, Any] = None) -> str:
        """Process a message through the unified system."""
        if not self._agent_initialized:
            return "❌ Sorry, the AI agent system is not properly initialized. Please check the server logs."
        
        try:
            # Get or create agent session for this user/interface combination
            session_id = await self.session_manager.get_or_create_session(user_id, interface, interface_context)
            
            # Process message through the real agent system
            response = await send_message(session_id, message)
            
            self.stats["total_requests"] += 1
            return response
            
        except Exception as e:
            self.logger.exception(f"Error processing message: {e}")
            return f"❌ Sorry, I encountered an error while processing your message: {str(e)}"
    
    async def get_server_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        return {
            "server": {
                "running": self._running,
                "start_time": self.stats["start_time"],
                "uptime_seconds": self.stats["uptime_seconds"],
                "total_requests": self.stats["total_requests"],
                "config": {
                    "host": self.config.host,
                    "port": self.config.port,
                    "max_connections_per_server": self.config.max_connections_per_server
                }
            },
            "sessions": {
                "active_sessions": len(self.session_manager.sessions), 
                "total_users": len(set(s["user_id"] for s in self.session_manager.sessions.values()))
            },
            "connections": {"total_connections": 0, "active_connections": 0},
            "components": {
                "agent_system": self._agent_initialized,
                "memory_manager": self._agent_initialized,
                "mcp_manager": self._agent_initialized,
                "celery_app": False,
                "event_bus": self._agent_initialized,
                "plugin_manager": self._agent_initialized,
                "rest_api": self.rest_api is not None
            }
        }
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a session."""
        return self.session_manager.get_session_info(session_id)
    
    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return list(self.session_manager.sessions.values())
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


class AgentSessionManager:
    """Session manager that integrates with the agent system."""
    
    def __init__(self):
        self.sessions = {}
        self.user_sessions = {}  # Map user_id -> agent_session_id
        self.logger = get_logger(__name__)
    
    async def get_or_create_session(self, user_id: str, interface: str, interface_context: Dict[str, Any] = None) -> int:
        """Get or create an agent session for the user."""
        # Use user_id as the key for session persistence across interfaces
        user_key = f"{user_id}_{interface}"
        
        if user_key in self.user_sessions:
            agent_session_id = self.user_sessions[user_key]
            self.logger.debug(f"Reusing existing agent session {agent_session_id} for user {user_id}")
            return agent_session_id
        
        try:
            # Create new agent session
            agent_session_id = await start_session()
            self.user_sessions[user_key] = agent_session_id
            
            # Store session metadata
            self.sessions[str(agent_session_id)] = {
                "session_id": agent_session_id,
                "user_id": user_id,
                "interface": interface,
                "interface_context": interface_context or {},
                "created_at": datetime.now().isoformat(),
                "status": "active"
            }
            
            self.logger.info(f"Created new agent session {agent_session_id} for user {user_id} via {interface}")
            return agent_session_id
            
        except Exception as e:
            self.logger.exception(f"Error creating agent session for user {user_id}: {e}")
            raise
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        return self.sessions.get(session_id)


# Global server instance
_server_instance: Optional[NagathaUnifiedServer] = None


async def get_unified_server(config: ServerConfig = None) -> NagathaUnifiedServer:
    """Get the global unified server instance."""
    global _server_instance
    
    if _server_instance is None:
        _server_instance = NagathaUnifiedServer(config)
    
    return _server_instance


async def start_unified_server(config: ServerConfig = None):
    """Start the unified server."""
    server = await get_unified_server(config)
    await server.start()


async def stop_unified_server():
    """Stop the unified server."""
    global _server_instance
    
    if _server_instance:
        await _server_instance.stop()
        _server_instance = None 