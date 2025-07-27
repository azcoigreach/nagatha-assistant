"""
MCP (Model Context Protocol) Manager for Nagatha Assistant.

This module manages connections to MCP servers and provides tools for the AI assistant.
Uses on-demand connections like the working test client approach.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from nagatha_assistant.utils.logger import get_logger

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    transport: str = "stdio"
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None

@dataclass
class MCPTool:
    """Represents an MCP tool with its source server."""
    name: str
    description: str
    server_name: str
    schema: Optional[Dict[str, Any]] = None

@dataclass
class MCPServerStatus:
    """Status information for an MCP server."""
    name: str
    connected: bool = False
    error: Optional[str] = None
    tools_count: int = 0
    connection_time: Optional[float] = None

class MCPManager:
    """Manages MCP server connections and tool execution using on-demand connections."""

    def __init__(self, config_path: str = "mcp.json"):
        self.config_path = config_path
        self.servers: Dict[str, MCPServerConfig] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.server_statuses: Dict[str, MCPServerStatus] = {}
        self._initialized = False
        self.logger = get_logger()

    def _load_config(self) -> Dict[str, MCPServerConfig]:
        """Load MCP server configurations from JSON file."""
        if not os.path.exists(self.config_path):
            self.logger.warning(f"MCP config file not found: {self.config_path}")
            return {}

        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)

            servers = {}
            for name, config in config_data.get("mcpServers", {}).items():
                # Skip comment entries (strings) and entries starting with underscore
                if isinstance(config, str) or name.startswith("_"):
                    self.logger.debug(f"Skipping comment/disabled entry: {name}")
                    continue
                    
                if not isinstance(config, dict):
                    self.logger.warning(f"Invalid config for server {name}: expected dict, got {type(config)}")
                    continue

                # Convert to MCPServerConfig
                env_vars = config.get("env", {})
                servers[name] = MCPServerConfig(
                    name=name,
                    command=config.get("command"),
                    args=config.get("args", []),
                    transport=config.get("transport", "stdio"),
                    url=config.get("url"),
                    env=env_vars
                )

            return servers
        except Exception as e:
            self.logger.error(f"Failed to load MCP config: {e}")
            return {}

    async def _test_and_discover_server(self, config: MCPServerConfig) -> bool:
        """Test connection to a server and discover its tools using the working test client approach."""
        try:
            start_time = time.time()
            connection_timeout = float(os.getenv("NAGATHA_MCP_CONNECTION_TIMEOUT", "10"))
            
            self.logger.info(f"Testing connection to {config.name} ({config.transport})...")
            
            if config.transport == "stdio":
                success = await self._test_stdio_server(config, connection_timeout)
            elif config.transport == "http":
                success = await self._test_http_server(config, connection_timeout)
            else:
                self.server_statuses[config.name] = MCPServerStatus(
                    name=config.name, connected=False, error=f"Unsupported transport: {config.transport}"
                )
                return False
            
            connection_time = time.time() - start_time
            
            if success:
                self.server_statuses[config.name] = MCPServerStatus(
                    name=config.name, connected=True, connection_time=connection_time
                )
                self.logger.info(f"✅ {config.name} connection test successful ({connection_time:.2f}s)")
                return True
            else:
                self.logger.warning(f"✗ {config.name} connection test failed")
                return False
                
        except Exception as e:
            error_msg = f"Error testing {config.name}: {e}"
            self.logger.error(error_msg)
            self.server_statuses[config.name] = MCPServerStatus(
                name=config.name, connected=False, error=str(e)
            )
            return False

    async def _test_stdio_server(self, config: MCPServerConfig, timeout: float) -> bool:
        """Test stdio server using exact test client approach."""
        if not config.command:
            self.server_statuses[config.name] = MCPServerStatus(
                name=config.name, connected=False, error="No command specified"
            )
            return False

        try:
            # Set up environment variables
            env = os.environ.copy()
            if config.env:
                env.update(config.env)

            # Create server parameters
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args or [],
                env=env
            )

            # Use EXACT same pattern as working test client - with ClientSession async context
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Discover tools while connection is active
                    await self._discover_tools_from_session(config.name, session)
                    return True

        except Exception as e:
            error_msg = f"Failed to connect to stdio server {config.name}: {e}"
            self.logger.error(error_msg)
            self.server_statuses[config.name] = MCPServerStatus(
                name=config.name, connected=False, error=str(e)
            )
            return False

    async def _test_http_server(self, config: MCPServerConfig, timeout: float) -> bool:
        """Test HTTP server using exact test client approach."""
        if not config.url:
            self.server_statuses[config.name] = MCPServerStatus(
                name=config.name, connected=False, error="No URL specified"
            )
            return False

        try:
            # Use EXACT same pattern as working test client - with ClientSession async context
            async with streamablehttp_client(config.url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Discover tools while connection is active
                    await self._discover_tools_from_session(config.name, session)
                    return True

        except Exception as e:
            error_msg = f"Failed to connect to HTTP server {config.name}: {e}"
            self.logger.error(error_msg)
            self.server_statuses[config.name] = MCPServerStatus(
                name=config.name, connected=False, error=str(e)
            )
            return False

    async def _discover_tools_from_session(self, server_name: str, session: ClientSession) -> None:
        """Discover tools from an active MCP session."""
        try:
            discovery_timeout = float(os.getenv("NAGATHA_MCP_DISCOVERY_TIMEOUT", "3"))
            tools_result = await asyncio.wait_for(
                session.list_tools(), 
                timeout=discovery_timeout
            )
            tools = tools_result.tools if hasattr(tools_result, 'tools') else []
            
            for tool in tools:
                # Sanitize names to ensure OpenAI function name compatibility
                # OpenAI function names must match pattern ^[a-zA-Z0-9_-]{1,64}$
                sanitized_server_name = _sanitize_function_name(server_name)
                sanitized_tool_name = _sanitize_function_name(tool.name)
                tool_name = f"{sanitized_server_name}_{sanitized_tool_name}"
                
                self.tools[tool_name] = MCPTool(
                    name=tool.name,
                    description=tool.description,
                    server_name=server_name,
                    schema=getattr(tool, 'inputSchema', None)
                )
                
                # Also register with just the sanitized tool name for convenience (if no conflict)
                if sanitized_tool_name not in self.tools:
                    self.tools[sanitized_tool_name] = self.tools[tool_name]
            
            # Update server status with tools count
            if server_name in self.server_statuses:
                self.server_statuses[server_name].tools_count = len(tools)
            
            self.logger.info(f"Discovered {len(tools)} tools from {server_name}: {[tool.name for tool in tools]}")
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout discovering tools from {server_name}")
        except Exception as e:
            self.logger.warning(f"Failed to discover tools from {server_name}: {e}")

    async def initialize(self) -> None:
        """Initialize by testing all MCP server connections."""
        if self._initialized:
            return

        self.servers = self._load_config()
        if not self.servers:
            self.logger.warning("No MCP servers configured")
            self._initialized = True
            return

        successful_connections = 0
        total_servers = len(self.servers)
        
        self.logger.info(f"Testing {total_servers} MCP servers...")

        # Test servers sequentially (like test client)
        for name, config in self.servers.items():
            if await self._test_and_discover_server(config):
                successful_connections += 1

        self._initialized = True
        
        if successful_connections > 0:
            self.logger.info(f"MCP Manager initialized with {successful_connections}/{total_servers} servers and {len(self.tools)} tools")
        else:
            self.logger.warning(f"MCP Manager initialized but no servers connected successfully ({total_servers} configured)")

    async def _create_session(self, config: MCPServerConfig):
        """Create a fresh session for a server using the working test client approach."""
        if config.transport == "stdio":
            if not config.command:
                raise ValueError(f"No command specified for stdio server {config.name}")
                
            # Set up environment variables
            env = os.environ.copy()
            if config.env:
                env.update(config.env)

            # Create server parameters
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args or [],
                env=env
            )

            # Use EXACT same pattern as working test client
            return stdio_client(server_params)
            
        elif config.transport == "http":
            if not config.url:
                raise ValueError(f"No URL specified for HTTP server {config.name}")
            return streamablehttp_client(config.url)
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool by creating a fresh connection (like test client)."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}")

        tool = self.tools[tool_name]
        config = self.servers.get(tool.server_name)
        
        if not config:
            raise RuntimeError(f"No configuration found for server '{tool.server_name}'")

        # Add extra debugging for TaskGroup errors
        self.logger.debug(f"Calling tool '{tool_name}' on server '{tool.server_name}' with args: {arguments}")
        
        try:
            # Create fresh connection using the working test client approach
            if config.transport == "stdio":
                # Set up environment variables (same as working test)
                env = os.environ.copy()
                if config.env:
                    env.update(config.env)

                # Create server parameters (same as working test)
                server_params = StdioServerParameters(
                    command=config.command,
                    args=config.args or [],
                    env=env
                )

                # Use EXACT same pattern as working test client
                async with stdio_client(server_params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        
                        # Call the tool with the original tool name (not the sanitized one)
                        result = await session.call_tool(tool.name, arguments)
                        self.logger.debug(f"Tool '{tool_name}' completed successfully")
                        return result
                        
            elif config.transport == "http":
                async with await self._create_session(config) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool.name, arguments)
                        return result
            else:
                raise ValueError(f"Unsupported transport: {config.transport}")
                
        except ExceptionGroup as eg:
            # Handle TaskGroup/ExceptionGroup errors specifically
            self.logger.error(f"ExceptionGroup in tool '{tool_name}': {eg}")
            # Extract the actual exceptions from the group
            actual_errors = []
            for exc in eg.exceptions:
                actual_errors.append(str(exc))
                self.logger.error(f"  - {type(exc).__name__}: {exc}")
            raise RuntimeError(f"Tool '{tool_name}' failed with multiple errors: {actual_errors}")
            
        except Exception as e:
            # Log full exception details
            self.logger.error(f"Error calling tool '{tool_name}' on server '{tool.server_name}': {e}")
            self.logger.exception("Full exception traceback:")
            raise

    def get_initialization_summary(self) -> Dict[str, Any]:
        """Get a summary of the initialization process."""
        connected_servers = [name for name, status in self.server_statuses.items() if status.connected]
        failed_servers = [(name, status.error) for name, status in self.server_statuses.items() if not status.connected and status.error]
        
        return {
            "total_configured": len(self.servers),
            "connected": len(connected_servers),
            "failed": len(failed_servers),
            "connected_servers": connected_servers,
            "failed_servers": failed_servers,
            "total_tools": len(self.tools)
        }

    async def shutdown(self) -> None:
        """Clean up MCP manager (no persistent connections to clean up)."""
        if not self._initialized:
            return

        self.logger.info("Shutting down MCP manager...")
        
        # No persistent connections to clean up since we use on-demand connections
        self.tools.clear()
        self.server_statuses.clear()
        self._initialized = False
        self.logger.info("MCP manager shutdown complete")

    async def reload_configuration(self) -> None:
        """Reload configuration and reconnect to all servers."""
        self.logger.info("Reloading MCP configuration...")
        
        # Clear existing state
        self.tools.clear()
        self.server_statuses.clear()
        
        # Reload configuration and reinitialize
        self._initialized = False
        await self.initialize()
        
        self.logger.info(f"Configuration reloaded with {len(self.get_available_tools())} tools from {len([s for s in self.server_statuses.values() if s.connected])} servers")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get a list of all available tools with their metadata."""
        tools = []
        for tool_name, tool in self.tools.items():
            tools.append({
                "name": tool_name,
                "description": tool.description,
                "server": tool.server_name,
                "schema": tool.schema
            })
        return tools

    def get_server_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all configured servers."""
        server_info = {}
        for name, status in self.server_statuses.items():
            server_info[name] = {
                "connected": status.connected,
                "error": status.error,
                "tools_count": status.tools_count,
                "connection_time": status.connection_time,
                "transport": self.servers.get(name, MCPServerConfig(name="unknown")).transport
            }
        return server_info

def _sanitize_function_name(name: str) -> str:
    """
    Sanitize a name to comply with OpenAI function name pattern: ^[a-zA-Z0-9_-]{1,64}$
    
    - Replace invalid characters with underscores
    - Ensure it starts with alphanumeric character
    - Limit to 64 characters
    """
    # Replace any character that's not alphanumeric, underscore, or hyphen with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    
    # Ensure it starts with alphanumeric character
    if sanitized and not sanitized[0].isalnum():
        sanitized = 'a' + sanitized
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = 'tool'
    
    # Limit to 64 characters
    if len(sanitized) > 64:
        sanitized = sanitized[:64]
    
    # Remove trailing non-alphanumeric characters if any
    sanitized = sanitized.rstrip('_-')
    
    return sanitized

# Global instance management
_mcp_manager: Optional[MCPManager] = None

async def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager instance, initializing if necessary."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
        await _mcp_manager.initialize()
    return _mcp_manager

async def shutdown_mcp_manager() -> None:
    """Shutdown the global MCP manager instance."""
    global _mcp_manager
    if _mcp_manager is not None:
        await _mcp_manager.shutdown()
        _mcp_manager = None 