"""
Shared MCP Connection Pool for efficient connection management.

This module provides connection pooling for MCP servers to ensure
efficient resource usage across multiple interfaces.
"""

import asyncio
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from nagatha_assistant.utils.logger import get_logger
from nagatha_assistant.core.event_bus import get_event_bus


class ConnectionState(Enum):
    """Connection states."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class ConnectionInfo:
    """Information about an MCP connection."""
    server_name: str
    connection_id: str
    state: ConnectionState
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_used(self):
        """Mark connection as used."""
        self.last_used = datetime.now()
        self.use_count += 1
        self.state = ConnectionState.BUSY
    
    def mark_idle(self):
        """Mark connection as idle."""
        self.state = ConnectionState.IDLE
    
    def mark_error(self, error: str):
        """Mark connection as having an error."""
        self.state = ConnectionState.ERROR
        self.error_count += 1
        self.last_error = error
        self.last_used = datetime.now()
    
    def is_expired(self, max_idle_time: timedelta) -> bool:
        """Check if connection has expired due to inactivity."""
        return datetime.now() - self.last_used > max_idle_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "server_name": self.server_name,
            "connection_id": self.connection_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "use_count": self.use_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "metadata": self.metadata
        }


class SharedMCPConnectionPool:
    """
    Shared connection pool for MCP servers.
    
    This class provides:
    - Connection reuse across interfaces
    - Connection health monitoring
    - Automatic connection cleanup
    - Usage statistics and tracking
    """
    
    def __init__(self, max_connections_per_server: int = 3, max_idle_time: timedelta = timedelta(minutes=30)):
        self.logger = get_logger(__name__)
        self.event_bus = None
        
        # Configuration
        self.max_connections_per_server = max_connections_per_server
        self.max_idle_time = max_idle_time
        
        # Connection storage
        self.connections: Dict[str, List[ConnectionInfo]] = {}  # server_name -> [connections]
        self.active_connections: Dict[str, ConnectionInfo] = {}  # connection_id -> connection
        
        # Statistics
        self.usage_stats: Dict[str, Dict[str, Any]] = {}  # session_id -> stats
        
        # Background tasks
        self._cleanup_task = None
        self._running = False
    
    async def start(self):
        """Start the connection pool."""
        self.logger.info("Starting Shared MCP Connection Pool")
        
        self.event_bus = get_event_bus()
        
        # Start background cleanup task
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Shared MCP Connection Pool started")
    
    async def stop(self):
        """Stop the connection pool."""
        self.logger.info("Stopping Shared MCP Connection Pool")
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        await self._close_all_connections()
        
        self.logger.info("Shared MCP Connection Pool stopped")
    
    async def get_connection(self, server_name: str, session_id: str) -> Optional[str]:
        """
        Get an available connection for a server.
        
        Args:
            server_name: Name of the MCP server
            session_id: Session ID for tracking usage
            
        Returns:
            Connection ID if available, None otherwise
        """
        # Check for available connections
        available_connections = self._get_available_connections(server_name)
        
        if available_connections:
            # Use existing connection
            connection = available_connections[0]
            connection.mark_used()
            
            self.logger.debug(f"Reusing connection {connection.connection_id} for server {server_name}")
            
            # Track usage
            await self._track_usage(session_id, server_name, "reused")
            
            return connection.connection_id
        
        # Check if we can create a new connection
        if self._can_create_connection(server_name):
            connection_id = await self._create_connection(server_name, session_id)
            if connection_id:
                return connection_id
        
        # No connections available
        self.logger.warning(f"No connections available for server {server_name}")
        await self._track_usage(session_id, server_name, "unavailable")
        
        return None
    
    async def release_connection(self, connection_id: str, session_id: str, success: bool = True):
        """
        Release a connection back to the pool.
        
        Args:
            connection_id: Connection ID to release
            session_id: Session ID for tracking
            success: Whether the connection was used successfully
        """
        connection = self.active_connections.get(connection_id)
        if not connection:
            return
        
        if success:
            connection.mark_idle()
            self.logger.debug(f"Released connection {connection_id} for server {connection.server_name}")
        else:
            connection.mark_error("Usage failed")
            self.logger.warning(f"Connection {connection_id} marked as error")
        
        # Track usage
        await self._track_usage(session_id, connection.server_name, "released", success)
    
    async def call_tool_shared(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        session_id: str
    ) -> Any:
        """
        Call an MCP tool using shared connection.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            session_id: Session ID for tracking
            
        Returns:
            Tool result
        """
        connection_id = None
        try:
            # Get connection
            connection_id = await self.get_connection(server_name, session_id)
            if not connection_id:
                raise Exception(f"No connections available for server {server_name}")
            
            # Call tool (this would integrate with the actual MCP manager)
            # For now, we'll simulate the call
            result = await self._call_tool_via_connection(connection_id, tool_name, arguments)
            
            # Track successful usage
            await self._track_tool_usage(session_id, server_name, tool_name, "success")
            
            # Emit event
            await self._emit_tool_event("mcp.tool.called", {
                "server_name": server_name,
                "tool_name": tool_name,
                "session_id": session_id,
                "connection_id": connection_id,
                "success": True
            })
            
            return result
            
        except Exception as e:
            # Track failed usage
            await self._track_tool_usage(session_id, server_name, tool_name, "error", str(e))
            
            # Emit error event
            await self._emit_tool_event("mcp.tool.error", {
                "server_name": server_name,
                "tool_name": tool_name,
                "session_id": session_id,
                "connection_id": connection_id,
                "error": str(e)
            })
            
            raise
            
        finally:
            # Release connection
            if connection_id:
                await self.release_connection(connection_id, session_id, success=True)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        total_connections = sum(len(conns) for conns in self.connections.values())
        active_connections = len([c for c in self.active_connections.values() if c.state == ConnectionState.BUSY])
        idle_connections = len([c for c in self.active_connections.values() if c.state == ConnectionState.IDLE])
        error_connections = len([c for c in self.active_connections.values() if c.state == ConnectionState.ERROR])
        
        # Per-server breakdown
        server_stats = {}
        for server_name, connections in self.connections.items():
            server_stats[server_name] = {
                "total": len(connections),
                "active": len([c for c in connections if c.state == ConnectionState.BUSY]),
                "idle": len([c for c in connections if c.state == ConnectionState.IDLE]),
                "error": len([c for c in connections if c.state == ConnectionState.ERROR])
            }
        
        return {
            "total_connections": total_connections,
            "active_connections": active_connections,
            "idle_connections": idle_connections,
            "error_connections": error_connections,
            "server_breakdown": server_stats,
            "max_connections_per_server": self.max_connections_per_server,
            "max_idle_time_minutes": self.max_idle_time.total_seconds() / 60
        }
    
    def get_usage_stats(self, session_id: str = None) -> Dict[str, Any]:
        """Get usage statistics."""
        if session_id:
            return self.usage_stats.get(session_id, {})
        
        # Aggregate stats
        total_usage = {}
        for session_stats in self.usage_stats.values():
            for server_name, stats in session_stats.items():
                if server_name not in total_usage:
                    total_usage[server_name] = {
                        "total_calls": 0,
                        "successful_calls": 0,
                        "failed_calls": 0,
                        "tool_usage": {}
                    }
                
                total_usage[server_name]["total_calls"] += stats.get("total_calls", 0)
                total_usage[server_name]["successful_calls"] += stats.get("successful_calls", 0)
                total_usage[server_name]["failed_calls"] += stats.get("failed_calls", 0)
                
                # Merge tool usage
                for tool_name, tool_stats in stats.get("tool_usage", {}).items():
                    if tool_name not in total_usage[server_name]["tool_usage"]:
                        total_usage[server_name]["tool_usage"][tool_name] = {
                            "calls": 0,
                            "errors": 0
                        }
                    total_usage[server_name]["tool_usage"][tool_name]["calls"] += tool_stats.get("calls", 0)
                    total_usage[server_name]["tool_usage"][tool_name]["errors"] += tool_stats.get("errors", 0)
        
        return total_usage
    
    def _get_available_connections(self, server_name: str) -> List[ConnectionInfo]:
        """Get available connections for a server."""
        connections = self.connections.get(server_name, [])
        return [c for c in connections if c.state == ConnectionState.IDLE]
    
    def _can_create_connection(self, server_name: str) -> bool:
        """Check if we can create a new connection for a server."""
        connections = self.connections.get(server_name, [])
        return len(connections) < self.max_connections_per_server
    
    async def _create_connection(self, server_name: str, session_id: str) -> Optional[str]:
        """Create a new connection for a server."""
        try:
            connection_id = f"conn_{server_name}_{int(time.time())}_{session_id[:8]}"
            
            connection = ConnectionInfo(
                server_name=server_name,
                connection_id=connection_id,
                state=ConnectionState.IDLE,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            
            # Store connection
            if server_name not in self.connections:
                self.connections[server_name] = []
            self.connections[server_name].append(connection)
            self.active_connections[connection_id] = connection
            
            self.logger.info(f"Created new connection {connection_id} for server {server_name}")
            
            # Track usage
            await self._track_usage(session_id, server_name, "created")
            
            return connection_id
            
        except Exception as e:
            self.logger.error(f"Failed to create connection for server {server_name}: {e}")
            return None
    
    async def _call_tool_via_connection(self, connection_id: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool via a specific connection."""
        # This would integrate with the actual MCP manager
        # For now, we'll simulate the call
        connection = self.active_connections.get(connection_id)
        if not connection:
            raise Exception(f"Connection {connection_id} not found")
        
        # Simulate tool call
        await asyncio.sleep(0.1)  # Simulate network delay
        
        return {
            "result": f"Tool {tool_name} called with arguments {arguments}",
            "connection_id": connection_id,
            "server_name": connection.server_name
        }
    
    async def _track_usage(self, session_id: str, server_name: str, action: str, success: bool = True):
        """Track connection usage."""
        if session_id not in self.usage_stats:
            self.usage_stats[session_id] = {}
        
        if server_name not in self.usage_stats[session_id]:
            self.usage_stats[session_id][server_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "tool_usage": {}
            }
        
        stats = self.usage_stats[session_id][server_name]
        stats["total_calls"] += 1
        
        if success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
    
    async def _track_tool_usage(self, session_id: str, server_name: str, tool_name: str, status: str, error: str = None):
        """Track tool usage."""
        if session_id not in self.usage_stats:
            self.usage_stats[session_id] = {}
        
        if server_name not in self.usage_stats[session_id]:
            self.usage_stats[session_id][server_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "tool_usage": {}
            }
        
        if tool_name not in self.usage_stats[session_id][server_name]["tool_usage"]:
            self.usage_stats[session_id][server_name]["tool_usage"][tool_name] = {
                "calls": 0,
                "errors": 0
            }
        
        tool_stats = self.usage_stats[session_id][server_name]["tool_usage"][tool_name]
        tool_stats["calls"] += 1
        
        if status == "error":
            tool_stats["errors"] += 1
    
    async def _emit_tool_event(self, event_type: str, data: Dict[str, Any]):
        """Emit tool event."""
        if self.event_bus:
            await self.event_bus.emit(event_type, data)
    
    async def _cleanup_loop(self):
        """Background task to clean up expired connections."""
        while self._running:
            try:
                await self._cleanup_expired_connections()
                await asyncio.sleep(300)  # Cleanup every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_expired_connections(self):
        """Clean up expired connections."""
        expired_connections = []
        
        for connection in self.active_connections.values():
            if connection.is_expired(self.max_idle_time):
                expired_connections.append(connection.connection_id)
        
        for connection_id in expired_connections:
            await self._close_connection(connection_id)
        
        if expired_connections:
            self.logger.info(f"Cleaned up {len(expired_connections)} expired connections")
    
    async def _close_connection(self, connection_id: str):
        """Close a specific connection."""
        connection = self.active_connections.get(connection_id)
        if not connection:
            return
        
        # Remove from storage
        self.active_connections.pop(connection_id, None)
        
        if connection.server_name in self.connections:
            self.connections[connection.server_name] = [
                c for c in self.connections[connection.server_name] 
                if c.connection_id != connection_id
            ]
        
        connection.state = ConnectionState.CLOSED
        
        self.logger.info(f"Closed connection {connection_id}")
    
    async def _close_all_connections(self):
        """Close all connections."""
        connection_ids = list(self.active_connections.keys())
        
        for connection_id in connection_ids:
            await self._close_connection(connection_id)
        
        self.logger.info(f"Closed all {len(connection_ids)} connections") 