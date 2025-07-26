# Nagatha MCP Integration Guide

Nagatha has been completely refactored to use the **Model Context Protocol (MCP)** standard for tool integration, making it a powerful and extensible AI agent that can connect to multiple MCP servers simultaneously. This guide provides comprehensive documentation for understanding, configuring, and extending Nagatha's MCP capabilities.

## 📋 Table of Contents

- [Overview](#overview)
- [MCP Architecture](#mcp-architecture)
- [Quick Setup](#quick-setup)
- [Configuration Guide](#configuration-guide)
- [Adding New MCP Servers](#adding-new-mcp-servers)
- [Server Management](#server-management)
- [Tool Discovery & Usage](#tool-discovery--usage)
- [Development & Debugging](#development--debugging)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

## 🔍 Overview

### What is MCP?

The **Model Context Protocol (MCP)** is an open standard that enables AI applications to securely connect with external data sources and tools. It provides a standardized way for LLMs to interact with various services while maintaining security and flexibility.

### Nagatha's MCP Implementation

Nagatha functions as an **MCP client** that can:

- 🔗 **Connect to multiple MCP servers** simultaneously
- 🛠️ **Automatically discover tools** from all connected servers
- 🧠 **Intelligently select tools** based on user requests using OpenAI's function calling
- 🚀 **Support multiple transports** (stdio and HTTP)
- 🔄 **Use on-demand connections** for efficient resource management
- 📊 **Provide comprehensive monitoring** of server status and tool availability

### Key Implementation Details

**On-Demand Connection Model**: Unlike traditional persistent connections, Nagatha uses an on-demand connection approach:
- Servers are tested during initialization to verify connectivity and discover tools
- Actual tool calls create fresh connections for each request
- This approach ensures reliability and prevents connection timeouts
- Connections are automatically cleaned up after each tool call

**Tool Naming**: Tools are registered with sanitized names to ensure OpenAI function calling compatibility:
- Original tool names are preserved for internal use
- Sanitized names follow the pattern: `^[a-zA-Z0-9_-]{1,64}$`
- Both full names (`server_tool`) and short names (`tool`) are available when there are no conflicts

### Supported MCP Servers

Nagatha is compatible with any MCP-compliant server, including:

- **firecrawl-mcp**: Web scraping, search, and content extraction
- **nagatha-mastodon-mcp**: Mastodon user analysis and moderation
- **memory-mcp**: Knowledge graph and persistent memory
- **mcp-server-bootstrap**: Template and example server
- **And many more...** (any server implementing the MCP standard)

## 🏗️ MCP Architecture

### Core Components

```
Nagatha MCP Architecture
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    OpenAI API   │    │     Nagatha     │    │   MCP Servers   │
│                 │    │                 │    │                 │
│  Function       │◄──►│  MCPManager     │◄──►│  firecrawl-mcp  │
│  Calling        │    │                 │    │  mastodon-mcp   │
│                 │    │  Tool Registry  │    │  memory-mcp     │
│                 │    │                 │    │  custom-mcp     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Classes

1. **MCPManager** (`src/nagatha_assistant/core/mcp_manager.py`)
   - Manages multiple MCP server configurations
   - Handles tool discovery and registration
   - Provides unified tool calling interface with on-demand connections
   - Manages server lifecycle (test, discover, call)

2. **Agent** (`src/nagatha_assistant/core/agent.py`)
   - Integrates MCP tools with OpenAI function calling
   - Handles intelligent tool selection and execution
   - Manages conversation flow and context

3. **Personality** (`src/nagatha_assistant/core/personality.py`)
   - Generates dynamic system prompts based on available tools
   - Maintains Nagatha's character while leveraging MCP capabilities

### Tool Discovery Flow

```
1. Nagatha starts up
   ↓
2. MCPManager reads mcp.json configuration
   ↓
3. For each server:
   - Test connection (stdio/HTTP) with timeout
   - Call list_tools() to discover available tools
   - Register tools in the global tool registry
   - Store server configuration for later use
   ↓
4. Agent receives user message
   ↓
5. OpenAI determines if tools are needed
   ↓
6. Agent creates fresh connection and calls appropriate MCP tools
   ↓
7. Results integrated into conversation
   ↓
8. Connection automatically cleaned up
```

## 🚀 Quick Setup

### 1. Environment Configuration

Create a `.env` file with essential variables:

```bash
# === Required ===
OPENAI_API_KEY=sk-your-openai-api-key-here

# === MCP Configuration ===
NAGATHA_MCP_CONNECTION_TIMEOUT=10            # Server connection timeout (seconds)
NAGATHA_MCP_DISCOVERY_TIMEOUT=3              # Tool discovery timeout (seconds)

# === OpenAI Settings ===
OPENAI_MODEL=gpt-4o-mini                     # Default model
OPENAI_TIMEOUT=60                            # API timeout

# === Logging ===
LOG_LEVEL=INFO                               # Set to DEBUG for detailed MCP logs
```

### 2. MCP Server Configuration

Create your `mcp.json` from the template:

```bash
cp mcp.json.template mcp.json
```

**⚠️ Security Note**: The `mcp.json` file contains API keys and is excluded from git via `.gitignore`. Never commit this file with real credentials.

### 3. Test the Setup

```bash
# Start Nagatha
nagatha run

# Check MCP status
nagatha mcp status

# Test in conversation
# Type: "Search for recent AI news" (if firecrawl-mcp is configured)
```

## ⚙️ Configuration Guide

### mcp.json Structure

The `mcp.json` file defines all MCP servers and their configurations:

```json
{
  "mcpServers": {
    "server-name": {
      // Server configuration options
    }
  }
}
```

**Configuration Features:**
- **Comments**: You can add string entries for documentation
- **Disabled Servers**: Entries starting with `_` are ignored
- **Environment Variables**: All `env` variables are passed to servers
- **Validation**: Invalid configurations are logged and skipped

### Stdio Transport Configuration

For servers that run as separate processes:

```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "your_api_key_here"
      }
    },
    "python-mcp-server": {
      "command": "python",
      "args": ["/path/to/your/server.py"],
      "env": {
        "CUSTOM_API_KEY": "your_key",
        "DEBUG": "true"
      }
    }
  }
}
```

**Configuration Options:**
- `command`: Executable command (required)
- `args`: Command line arguments (optional, defaults to empty array)
- `env`: Environment variables passed to the server (optional)

### HTTP Transport Configuration

For servers running as HTTP services:

```json
{
  "mcpServers": {
    "nagatha-mastodon-mcp": {
      "transport": "http",
      "url": "http://localhost:8080/mcp",
      "env": {
        "OPENAI_API_KEY": "your_openai_key",
        "MASTODON_ACCESS_TOKEN": "your_mastodon_token",
        "MASTODON_API_BASE": "https://your.mastodon.instance"
      }
    },
    "remote-mcp-server": {
      "transport": "http",
      "url": "https://api.example.com/mcp"
    }
  }
}
```

**Configuration Options:**
- `transport`: Set to "http" (required)
- `url`: MCP server endpoint URL (required)
- `env`: Environment variables (optional, for server configuration)

**Note**: HTTP headers are not currently supported in the configuration. For authentication, use environment variables or include credentials in the URL.

### Complete Example Configuration

```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "fc-your-firecrawl-api-key"
      }
    },
    "nagatha-mastodon-mcp": {
      "transport": "http",
      "url": "http://localhost:8080/mcp",
      "env": {
        "OPENAI_API_KEY": "sk-your-openai-key",
        "MASTODON_ACCESS_TOKEN": "your-mastodon-token",
        "MASTODON_API_BASE": "https://mastodon.social"
      }
    },
    "memory-mcp": {
      "command": "python",
      "args": ["-m", "memory_mcp.server"],
      "env": {
        "MEMORY_DB_PATH": "/path/to/memory.db"
      }
    },
    "mcp-server-bootstrap": {
      "command": "python",
      "args": ["/home/user/mcp-servers/bootstrap/server.py"]
    },
    "_disabled-server": {
      "command": "python",
      "args": ["/path/to/disabled/server.py"]
    },
    "This is a comment": "Documentation for the configuration"
  }
}
```

## 🔧 Adding New MCP Servers

### Step-by-Step Guide

#### 1. Identify the Server Type

**Stdio Server** (most common):
- Runs as a separate process
- Communicates via stdin/stdout
- Examples: npm packages, Python scripts

**HTTP Server**:
- Runs as a web service
- Communicates via HTTP API
- Examples: containerized services, remote APIs

#### 2. Gather Configuration Information

For any MCP server, you need:
- **Server identifier**: A unique name for the server
- **Command/URL**: How to start or reach the server
- **Environment variables**: API keys, configuration options
- **Dependencies**: Required packages or services

#### 3. Add to mcp.json

**For stdio servers:**
```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "command-to-run",
      "args": ["arg1", "arg2"],
      "env": {
        "API_KEY": "your-key",
        "CONFIG_OPTION": "value"
      }
    }
  }
}
```

**For HTTP servers:**
```json
{
  "mcpServers": {
    "your-server-name": {
      "transport": "http",
      "url": "http://localhost:port/mcp",
      "env": {
        "SERVER_CONFIG": "value"
      }
    }
  }
}
```

#### 4. Test the Configuration

```bash
# Reload MCP configuration
nagatha mcp reload

# Check server status
nagatha mcp status

# Look for your server in the output
```

#### 5. Verify Tool Discovery

```bash
nagatha mcp status
```

Expected output:
```
=== MCP Status ===
Initialized: True

=== Servers ===
✓ your-server-name (stdio/http)
    Command: your-command / URL: your-url
    Tools: tool1, tool2, tool3

=== Available Tools ===
• tool1 (your-server-name): Description of tool1
• tool2 (your-server-name): Description of tool2
```

### Real-World Examples

#### Adding Firecrawl MCP Server

**Prerequisites:**
- Node.js installed
- Firecrawl API key

**Configuration:**
```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "fc-your-firecrawl-api-key-here"
      }
    }
  }
}
```

**Usage in Nagatha:**
```
You: "Scrape the content from https://example.com"
Nagatha: I'll scrape that website for you.
[Uses firecrawl-mcp scrape tool]
[Provides formatted content]
```

#### Adding Custom Python MCP Server

**Prerequisites:**
- Python MCP server script
- Required Python packages

**Server Structure:**
```python
# /path/to/my_server.py
from mcp.server import Server
from mcp.types import Tool

server = Server("my-custom-server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="my_tool",
            description="Does something useful",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "my_tool":
        # Implement your tool logic
        return {"result": f"Processed: {arguments.get('input')}"}

if __name__ == "__main__":
    server.run()
```

**Configuration:**
```json
{
  "mcpServers": {
    "my-custom-server": {
      "command": "python",
      "args": ["/path/to/my_server.py"],
      "env": {
        "DEBUG": "true",
        "API_KEY": "your-api-key"
      }
    }
  }
}
```

#### Adding Docker-based MCP Server

**Prerequisites:**
- Docker installed
- MCP server container

**Start the container:**
```bash
docker run -d -p 8081:8080 \
  -e API_KEY=your-key \
  --name my-mcp-server \
  my-mcp-server:latest
```

**Configuration:**
```json
{
  "mcpServers": {
    "docker-mcp-server": {
      "transport": "http",
      "url": "http://localhost:8081/mcp",
      "env": {
        "API_KEY": "your-key"
      }
    }
  }
}
```

## 🖥️ Server Management

### CLI Commands

#### Check Server Status
```bash
nagatha mcp status
```

**Actual Output Format:**
```
=== MCP Status ===
Initialized: True

=== Servers ===
✓ firecrawl-mcp (stdio)
    Command: npx -y firecrawl-mcp
    Tools: scrape, search, crawl, map, extract

✗ failing-server (stdio)
    Command: python /bad/path.py
    Error: FileNotFoundError: /bad/path.py not found

✓ nagatha-mastodon-mcp (http)
    URL: http://localhost:8080/mcp
    Tools: evaluate_user_profile, analyze_user_activity

✓ memory-mcp (stdio)
    Command: python -m memory_mcp.server
    Tools: create_entities, search_nodes, read_graph

=== Available Tools ===
• scrape (firecrawl-mcp): Scrape content from a single URL
• search (firecrawl-mcp): Search the web and extract content
• crawl (firecrawl-mcp): Crawl website pages recursively
• evaluate_user_profile (nagatha-mastodon-mcp): Evaluate Mastodon user profiles
• create_entities (memory-mcp): Create entities in knowledge graph
• search_nodes (memory-mcp): Search knowledge graph nodes
[... more tools ...]
```

#### Reload Configuration
```bash
nagatha mcp reload
```

This command:
1. Shuts down the current MCP manager
2. Re-reads the `mcp.json` configuration file
3. Tests connections to all configured servers
4. Re-discovers all available tools
5. Reports the results

### Programmatic Management

```python
from nagatha_assistant.core.mcp_manager import get_mcp_manager

async def manage_mcp():
    manager = await get_mcp_manager()
    
    # Get status information
    server_info = manager.get_server_info()
    tools = manager.get_available_tools()
    
    print(f"Servers: {len(server_info)}")
    print(f"Tools: {len(tools)}")
    
    # Reload configuration
    await manager.reload_configuration()
    
    # Check specific server
    server_info = manager.get_server_info()
    firecrawl_info = server_info.get('firecrawl-mcp')
    if firecrawl_info:
        print(f"Firecrawl status: {firecrawl_info['connected']}")
```

## 🛠️ Tool Discovery & Usage

### How Tool Discovery Works

1. **Server Testing**: Nagatha tests each MCP server during initialization
2. **Tool Listing**: Calls `list_tools()` on each server with a timeout
3. **Name Sanitization**: Converts tool names to OpenAI-compatible format
4. **Registration**: Registers tools with both full and short names
5. **Availability**: Tools become available for OpenAI function calling

### Tool Naming Convention

Tools are registered with multiple names for flexibility:

- **Full name**: `server_tool` (e.g., `firecrawl_mcp_scrape`)
- **Short name**: `tool` (e.g., `scrape`) - only if no conflicts

**Name Sanitization Rules:**
- Replace invalid characters with underscores
- Ensure names start with alphanumeric characters
- Limit to 64 characters
- Follow OpenAI function name pattern: `^[a-zA-Z0-9_-]{1,64}$`

### Tool Usage in Conversations

Nagatha automatically selects and uses tools based on user requests:

```
You: "Search for recent news about AI"
Nagatha: I'll search for recent AI news for you.

[Tool Selection Process:]
1. OpenAI analyzes the request
2. Determines "search" tool is appropriate
3. Creates fresh connection to firecrawl-mcp
4. Calls firecrawl-mcp.search with relevant parameters
5. Receives search results
6. Formats and presents results conversationally
7. Closes connection

Nagatha: I found several recent AI news articles:
[Presents formatted search results with sources]
```

### Manual Tool Usage

You can also request specific tools:

```
You: "Use the scrape tool to get content from https://example.com"
Nagatha: I'll use the scrape tool to extract content from that URL.
[Executes firecrawl-mcp.scrape tool]
[Provides scraped content]
```

### Tool Error Handling

Nagatha gracefully handles tool errors:

```python
# Example error handling in MCPManager
try:
    result = await manager.call_tool(tool_name, arguments)
    return result
except Exception as e:
    logger.warning(f"Tool {tool_name} failed: {e}")
    return {
        "error": str(e),
        "tool": tool_name,
        "fallback_message": "The tool encountered an error. Please try again or rephrase your request."
    }
```

## 🐛 Development & Debugging

### Logging Configuration

Enable comprehensive MCP logging:

```bash
# In .env file
LOG_LEVEL=DEBUG
NAGATHA_LOG_LEVEL_FILE=DEBUG

# Run with debug output
nagatha run
```

### Testing MCP Integration

Create a test script to verify MCP functionality:

```python
# test_mcp.py
import asyncio
import logging
from nagatha_assistant.core.mcp_manager import get_mcp_manager

async def test_mcp():
    """Test MCP server connections and tool discovery."""
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Get MCP manager
    manager = await get_mcp_manager()
    
    # Get status
    server_info = manager.get_server_info()
    tools = manager.get_available_tools()
    
    print("=== MCP Test Results ===")
    print(f"Initialized: {manager._initialized}")
    print(f"Servers: {len(server_info)}")
    print(f"Tools: {len(tools)}")
    
    # Test each server
    for server_name, info in server_info.items():
        print(f"\n--- {server_name} ---")
        print(f"Connected: {info['connected']}")
        print(f"Transport: {info['transport']}")
        if info['connected']:
            print(f"Tools: {info['tools_count']}")
        else:
            print(f"Error: {info.get('error', 'Unknown error')}")
    
    # Test tool call (if available)
    if tools:
        tool_name = tools[0]['name']
        print(f"\n=== Testing Tool Call: {tool_name} ===")
        try:
            result = await manager.call_tool(tool_name, {})
            print("Tool call successful!")
            print(f"Result type: {type(result)}")
        except Exception as e:
            print(f"Tool call failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp())
```

### Debugging Server Connections

#### Common Connection Issues

**Stdio Server Won't Start:**
```bash
# Check if command exists
which npx  # For npm servers
which python  # For Python servers

# Test command manually
npx -y firecrawl-mcp  # Should start the server

# Check file permissions
ls -la /path/to/server.py
```

**HTTP Server Not Responding:**
```bash
# Test HTTP endpoint
curl http://localhost:8080/mcp

# Check if server is running
netstat -tulpn | grep 8080

# Check Docker containers (if applicable)
docker ps
docker logs container-name
```

#### Debug Mode for Servers

Many MCP servers support debug mode:

```json
{
  "mcpServers": {
    "debug-server": {
      "command": "python",
      "args": ["/path/to/server.py", "--debug"],
      "env": {
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### Creating Test Servers

#### Minimal Python MCP Server

```python
# minimal_server.py
import asyncio
import json
import sys
from typing import Any, Dict

class MinimalMCPServer:
    def __init__(self):
        self.tools = [
            {
                "name": "echo",
                "description": "Echo back the input",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"}
                    },
                    "required": ["message"]
                }
            }
        ]
    
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        method = message.get("method")
        
        if method == "list_tools":
            return {
                "tools": self.tools
            }
        elif method == "call_tool":
            tool_name = message["params"]["name"]
            arguments = message["params"]["arguments"]
            
            if tool_name == "echo":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Echo: {arguments.get('message', '')}"
                        }
                    ]
                }
        
        return {"error": f"Unknown method: {method}"}
    
    async def run(self):
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            
            try:
                message = json.loads(line.strip())
                response = await self.handle_message(message)
                print(json.dumps(response))
                sys.stdout.flush()
            except Exception as e:
                error_response = {"error": str(e)}
                print(json.dumps(error_response))
                sys.stdout.flush()

if __name__ == "__main__":
    server = MinimalMCPServer()
    asyncio.run(server.run())
```

**Add to mcp.json:**
```json
{
  "mcpServers": {
    "minimal-test": {
      "command": "python",
      "args": ["/path/to/minimal_server.py"]
    }
  }
}
```

## ⚙️ Advanced Configuration

### Custom Tool Schemas

MCP tools use JSON Schema for input validation. Here's how to create comprehensive schemas:

```python
# Complex tool schema example
tool_schema = {
    "name": "advanced_search",
    "description": "Advanced search with multiple parameters",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "filters": {
                "type": "object",
                "properties": {
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "format": "date"},
                            "end": {"type": "string", "format": "date"}
                        }
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "options": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10
                    },
                    "include_content": {
                        "type": "boolean",
                        "default": True
                    }
                }
            }
        },
        "required": ["query"],
        "additionalProperties": False
    }
}
```

### Performance Optimization

#### Timeout Configuration

Adjust timeouts based on your tool requirements:

```bash
# Quick tools (web search, simple queries)
NAGATHA_MCP_CONNECTION_TIMEOUT=5
NAGATHA_MCP_DISCOVERY_TIMEOUT=2

# Heavy tools (web scraping, data processing)
NAGATHA_MCP_CONNECTION_TIMEOUT=30
NAGATHA_MCP_DISCOVERY_TIMEOUT=10

# Very heavy tools (large crawls, AI processing)
NAGATHA_MCP_CONNECTION_TIMEOUT=60
NAGATHA_MCP_DISCOVERY_TIMEOUT=30
```

#### On-Demand Connection Benefits

The on-demand connection model provides several advantages:

- **Reliability**: No persistent connection timeouts
- **Resource Efficiency**: Connections only when needed
- **Error Recovery**: Fresh connections for each request
- **Scalability**: No connection pool management required

### Server Health Monitoring

Implement health checks for MCP servers:

```python
# health_monitor.py
import asyncio
from nagatha_assistant.core.mcp_manager import get_mcp_manager

async def health_check():
    """Monitor MCP server health."""
    manager = await get_mcp_manager()
    
    while True:
        server_info = manager.get_server_info()
        
        for server_name, info in server_info.items():
            if not info['connected']:
                print(f"⚠️  Server {server_name} is unhealthy")
                # The on-demand model will handle reconnection automatically
        
        await asyncio.sleep(60)  # Check every minute

# Run health monitor
asyncio.run(health_check())
```

## 🚨 Troubleshooting

### Common Issues and Solutions

#### Issue: "No MCP servers available"

**Symptoms:**
- `nagatha mcp status` shows no servers
- No tools available in conversations

**Solutions:**
1. Check if `mcp.json` exists:
   ```bash
   ls -la mcp.json
   ```

2. Validate JSON syntax:
   ```bash
   python -m json.tool mcp.json
   ```

3. Check file permissions:
   ```bash
   chmod 644 mcp.json
   ```

#### Issue: "Server failed to connect"

**Symptoms:**
- Server shows as "Failed to connect" in status
- Tool calls fail with connection errors

**Solutions:**

**For stdio servers:**
1. Verify command exists:
   ```bash
   which npx  # For npm servers
   which python  # For Python servers
   ```

2. Test command manually:
   ```bash
   npx -y firecrawl-mcp  # Should start server
   ```

3. Check file paths:
   ```bash
   ls -la /path/to/server.py
   ```

4. Verify dependencies:
   ```bash
   npm list -g firecrawl-mcp  # For npm packages
   pip list | grep mcp  # For Python packages
   ```

**For HTTP servers:**
1. Test endpoint:
   ```bash
   curl http://localhost:8080/mcp
   ```

2. Check if service is running:
   ```bash
   netstat -tulpn | grep 8080
   ```

3. Verify firewall settings:
   ```bash
   sudo ufw status  # Ubuntu/Debian
   sudo firewall-cmd --list-all  # CentOS/RHEL
   ```

#### Issue: "Tool call timeout"

**Symptoms:**
- Tools start but never complete
- Timeout errors in logs

**Solutions:**
1. Increase timeout:
   ```bash
   export NAGATHA_MCP_CONNECTION_TIMEOUT=30
   ```

2. Check server performance:
   ```bash
   # Monitor server process
   top -p $(pgrep -f "firecrawl-mcp")
   ```

3. Reduce request complexity:
   ```bash
   # Use smaller datasets or simpler queries
   ```

#### Issue: "Environment variables not passed"

**Symptoms:**
- Authentication errors
- Server starts but tools fail

**Solutions:**
1. Verify environment variables in `mcp.json`:
   ```json
   {
     "mcpServers": {
       "server": {
         "env": {
           "API_KEY": "verify-this-value"
         }
       }
     }
   }
   ```

2. Check if variables are properly quoted:
   ```json
   {
     "env": {
       "COMPLEX_VALUE": "value with spaces and symbols"
     }
   }
   ```

3. Use environment variable substitution:
   ```json
   {
     "env": {
       "API_KEY": "${FIRECRAWL_API_KEY}"
     }
   }
   ```

### Debug Commands

#### Enable Verbose Logging
```bash
export LOG_LEVEL=DEBUG
export NAGATHA_LOG_LEVEL_FILE=DEBUG
nagatha run
```

#### Test Individual Tools
```python
# test_tool.py
import asyncio
from nagatha_assistant.core.mcp_manager import get_mcp_manager

async def test_tool():
    manager = await get_mcp_manager()
    
    try:
        result = await manager.call_tool(
            'firecrawl-mcp.scrape',
            {'url': 'https://httpbin.org/json'}
        )
        print("Success:", result)
    except Exception as e:
        print("Error:", e)

asyncio.run(test_tool())
```

#### Monitor Server Processes
```bash
# Watch server processes
watch 'ps aux | grep -E "(npx|python.*mcp|firecrawl)"'

# Monitor server logs
tail -f ~/.config/nagatha/mcp_servers.log
```

### Error Recovery

#### Automatic Reconnection

With the on-demand connection model, Nagatha automatically handles reconnection:

```python
# In MCPManager
async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
    # Each tool call creates a fresh connection
    # If connection fails, the error is handled gracefully
    # No persistent connection management needed
```

#### Manual Recovery

```bash
# Reload all servers
nagatha mcp reload

# Restart Nagatha completely
# Ctrl+C to stop
nagatha run
```

## 📚 Examples

### Example 1: Adding Weather MCP Server

**Step 1: Create weather server**
```python
# weather_server.py
import asyncio
import json
import sys
import aiohttp
import os

class WeatherMCPServer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.tools = [
            {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "units": {"type": "string", "enum": ["metric", "imperial"], "default": "metric"}
                    },
                    "required": ["location"]
                }
            }
        ]
    
    async def get_weather(self, location: str, units: str = "metric"):
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": self.api_key,
            "units": units
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if response.status == 200:
                    temp = data["main"]["temp"]
                    desc = data["weather"][0]["description"]
                    return f"Weather in {location}: {temp}°{'C' if units == 'metric' else 'F'}, {desc}"
                else:
                    return f"Error getting weather: {data.get('message', 'Unknown error')}"
    
    async def handle_message(self, message):
        method = message.get("method")
        
        if method == "list_tools":
            return {"tools": self.tools}
        elif method == "call_tool":
            name = message["params"]["name"]
            args = message["params"]["arguments"]
            
            if name == "get_weather":
                result = await self.get_weather(**args)
                return {
                    "content": [{"type": "text", "text": result}]
                }
        
        return {"error": f"Unknown method: {method}"}
    
    async def run(self):
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            
            try:
                message = json.loads(line.strip())
                response = await self.handle_message(message)
                print(json.dumps(response))
                sys.stdout.flush()
            except Exception as e:
                print(json.dumps({"error": str(e)}))
                sys.stdout.flush()

if __name__ == "__main__":
    api_key = os.getenv("OPENWEATHER_API_KEY")
    server = WeatherMCPServer(api_key)
    asyncio.run(server.run())
```

**Step 2: Add to mcp.json**
```json
{
  "mcpServers": {
    "weather-mcp": {
      "command": "python",
      "args": ["/path/to/weather_server.py"],
      "env": {
        "OPENWEATHER_API_KEY": "your-openweather-api-key"
      }
    }
  }
}
```

**Step 3: Test in Nagatha**
```bash
nagatha mcp reload
nagatha run
```

**Usage:**
```
You: "What's the weather like in Paris?"
Nagatha: I'll check the current weather in Paris for you.
[Uses weather-mcp.get_weather tool]
Nagatha: Weather in Paris: 18°C, partly cloudy
```

### Example 2: HTTP-based Database MCP Server

**Step 1: Create FastAPI server**
```python
# database_mcp_server.py
from fastapi import FastAPI
import sqlite3
from typing import Dict, Any

app = FastAPI()

# MCP endpoint
@app.post("/mcp")
async def handle_mcp(message: Dict[str, Any]):
    method = message.get("method")
    
    if method == "list_tools":
        return {
            "tools": [
                {
                    "name": "query_database",
                    "description": "Query the database",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string"},
                            "params": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["sql"]
                    }
                }
            ]
        }
    elif method == "call_tool":
        name = message["params"]["name"]
        args = message["params"]["arguments"]
        
        if name == "query_database":
            try:
                conn = sqlite3.connect("data.db")
                cursor = conn.cursor()
                cursor.execute(args["sql"], args.get("params", []))
                results = cursor.fetchall()
                conn.close()
                
                return {
                    "content": [
                        {"type": "text", "text": f"Query results: {results}"}
                    ]
                }
            except Exception as e:
                return {
                    "content": [
                        {"type": "text", "text": f"Database error: {str(e)}"}
                    ]
                }
    
    return {"error": f"Unknown method: {method}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8081)
```

**Step 2: Start the server**
```bash
python database_mcp_server.py
```

**Step 3: Add to mcp.json**
```json
{
  "mcpServers": {
    "database-mcp": {
      "transport": "http",
      "url": "http://localhost:8081/mcp"
    }
  }
}
```

**Step 4: Test**
```
You: "Query the database for all users"
Nagatha: I'll query the database for user information.
[Uses database-mcp.query_database tool]
Nagatha: Here are all the users in the database: [results]
```

### Example 3: Multi-Server Workflow

Configure multiple servers for complex workflows:

```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "your-key"
      }
    },
    "memory-mcp": {
      "command": "python",
      "args": ["-m", "memory_mcp.server"]
    },
    "analysis-mcp": {
      "transport": "http",
      "url": "http://localhost:8082/mcp"
    }
  }
}
```

**Complex workflow example:**
```
You: "Research AI developments, save the findings, and analyze trends"

Nagatha's workflow:
1. Uses firecrawl-mcp.search to find recent AI articles
2. Uses firecrawl-mcp.scrape to get full content
3. Uses memory-mcp.create_entities to save findings
4. Uses analysis-mcp.analyze_trends to identify patterns
5. Presents comprehensive summary
```

---

## 🎯 Best Practices

### Security
- Never commit `mcp.json` with real API keys
- Use environment variables for sensitive configuration
- Regularly rotate API keys
- Validate all tool inputs
- Implement rate limiting for external APIs

### Performance
- Use appropriate timeouts for different tool types
- Leverage the on-demand connection model for efficiency
- Monitor server resource usage
- Consider caching for frequently used data

### Reliability
- Implement health checks for critical servers
- Use the on-demand connection model for automatic error recovery
- Provide meaningful error messages
- Log all tool calls for debugging

### Development
- Start with simple test servers
- Use comprehensive tool schemas
- Write tests for your MCP servers
- Document all custom tools and their usage

---

**🔗 Useful Resources:**

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Nagatha Mastodon MCP Server](https://github.com/azcoigreach/nagatha-mastodon)
- [Firecrawl MCP Server](https://github.com/mendableai/firecrawl)

**📞 Need Help?**

1. Check the troubleshooting section above
2. Run `nagatha mcp status` for diagnostics
3. Enable debug logging for detailed information
4. Create an issue on GitHub with your configuration and error logs 