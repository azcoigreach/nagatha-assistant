# Dashboard UI Enhancement

This document describes the enhanced dashboard UI for Nagatha Assistant.

## Overview

The dashboard provides a comprehensive multi-panel interface for interacting with Nagatha Assistant, offering real-time monitoring, enhanced command input, and system management capabilities.

## Features

### Multi-Panel Layout
- **Left Panel**: System status and notifications
- **Center Panel**: Command interface and conversation area  
- **Right Panel**: Resource monitoring and metrics

### Real-Time Updates
- Live system status monitoring
- Event-driven notifications
- Resource usage tracking
- MCP server status updates

### Enhanced Command Interface
- Command history navigation (↑/↓ arrows)
- Auto-suggestions and completions
- System command support (/help, /status, etc.)
- Real-time input validation

### Keyboard Navigation
- `Ctrl+1`: Focus command input
- `Ctrl+2`: Focus status panel
- `Ctrl+3`: Focus notifications
- `Ctrl+4`: Focus resources
- `Ctrl+Q`: Quit application
- `Ctrl+R`: Refresh all data
- `Ctrl+S`: Show sessions
- `Ctrl+T`: Show tools
- `F1`: Show help

## Usage

### Starting the Dashboard

```bash
# Using the CLI
python -m nagatha_assistant.cli dashboard

# Using the standalone script
python dashboard.py
```

### Panels Description

#### Status Panel
- Current session information
- MCP server connection status
- System health indicators
- Recent event activity

#### Command Panel
- Enhanced input with history
- Command mode indicators (chat/tool/system)
- Real-time suggestions
- System command support

#### Notification Panel
- Live event notifications
- Active tasks and reminders
- System alerts and messages
- Actionable items

#### Resource Monitor
- CPU, memory, disk usage
- Database statistics
- MCP performance metrics
- OpenAI token usage and costs

## System Commands

The dashboard supports special system commands:

- `/help` - Show available commands and shortcuts
- `/status` - Display detailed system status
- `/sessions` - Open session selector
- `/tools` - Show available MCP tools
- `/refresh` - Refresh all dashboard data
- `/clear` - Clear conversation area

## Architecture

### Widget Components
- `StatusPanel`: Real-time system monitoring
- `CommandPanel`: Enhanced command input interface
- `NotificationPanel`: Event notification management
- `ResourceMonitor`: System resource tracking

### Event Integration
The dashboard integrates with Nagatha's event bus for real-time updates:
- System events → Status panel updates
- Agent events → Notification creation
- MCP events → Server status changes
- Resource events → Performance monitoring

### Responsive Design
- Collapsible sections for space management
- CSS-based styling for consistent appearance
- Adaptive layout for different terminal sizes

## Configuration

Environment variables:
- `OPENAI_API_KEY`: Required for AI functionality
- `LOG_LEVEL`: Control logging verbosity
- `NAGATHA_MCP_TIMEOUT`: MCP operation timeout
- `NAGATHA_CONVERSATION_TIMEOUT`: Conversation timeout

## Testing

Run the dashboard tests:
```bash
python -m pytest tests/test_dashboard.py -v
```

## Comparison with Original UI

| Feature | Original UI | Dashboard UI |
|---------|-------------|--------------|
| Layout | Single panel | Multi-panel |
| Status | Basic header | Detailed status panel |
| Commands | Simple input | Enhanced with history |
| Monitoring | None | Real-time resource monitoring |
| Notifications | Chat messages only | Dedicated notification panel |
| Shortcuts | Basic | Comprehensive keyboard navigation |
| Events | None | Real-time event integration |

## Future Enhancements

Potential improvements:
- Customizable panel layouts
- Plugin-based widget system
- Advanced resource graphing
- Export/import functionality
- Theme customization
- Advanced filtering and search