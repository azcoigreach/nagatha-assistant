"""
System Status Panel Widget for Nagatha Assistant Dashboard.

This widget displays real-time system status information including:
- Current session information
- MCP server connections and status
- System health indicators
- Event activity metrics
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from textual.app import ComposeResult
from textual.widgets import Static, Collapsible, DataTable, Label
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive

from nagatha_assistant.core.event_bus import get_event_bus, Event
from nagatha_assistant.core.event import StandardEventTypes, EventPriority
from nagatha_assistant.core import agent
from nagatha_assistant.utils.logger import setup_logger_with_env_control, get_logger

logger = get_logger()


class StatusPanel(Vertical):
    """
    Widget that displays system status information and updates in real-time.
    """
    
    # Reactive attributes for status updates
    session_id: reactive[Optional[int]] = reactive(None)
    mcp_status: reactive[Dict[str, Any]] = reactive({})
    last_update: reactive[datetime] = reactive(datetime.now(timezone.utc))
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_subscription_id = None
        self.refresh_interval = 30  # seconds
        
    def compose(self) -> ComposeResult:
        """Compose the status panel with collapsible sections."""
        
        with Collapsible(title="System Overview", collapsed=False, id="system_overview"):
            yield Static("Loading system status...", id="system_summary")
            
        with Collapsible(title="Current Session", collapsed=False, id="session_info"):
            yield Static("No active session", id="session_details")
            
        with Collapsible(title="MCP Servers", collapsed=False, id="mcp_servers"):
            # Table for MCP server status
            mcp_table = DataTable(id="mcp_table")
            mcp_table.add_columns("Server", "Status", "Tools", "Last Seen")
            yield mcp_table
            
        with Collapsible(title="Event Activity", collapsed=True, id="event_activity"):
            yield Static("Monitoring events...", id="event_summary")
            
    async def on_mount(self) -> None:
        """Initialize the status panel when mounted."""
        try:
            # Subscribe to relevant events for real-time updates
            event_bus = get_event_bus()
            self.event_subscription_id = event_bus.subscribe(
                pattern="*",  # Subscribe to all events for activity monitoring
                handler=self._handle_event,
                priority_filter=EventPriority.HIGH
            )
            
            # Start periodic refresh
            self.set_interval(self.refresh_interval, self._refresh_status)
            
            # Initial status load
            await self._refresh_status()
            
        except Exception as e:
            logger.error(f"Error initializing status panel: {e}")
            await self._update_error_state(f"Initialization error: {e}")
    
    async def on_unmount(self) -> None:
        """Clean up when the widget is unmounted."""
        if self.event_subscription_id:
            event_bus = get_event_bus()
            event_bus.unsubscribe(self.event_subscription_id)
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming events for real-time updates."""
        try:
            # Update last activity time
            self.last_update = event.timestamp
            
            # Handle specific event types
            if event.event_type == StandardEventTypes.AGENT_CONVERSATION_STARTED:
                session_id = event.data.get("session_id")
                if session_id:
                    self.session_id = session_id
                    await self._update_session_info()
                    
            elif event.event_type.startswith("mcp."):
                # MCP-related event, refresh MCP status
                await self._update_mcp_status()
                
            # Update event activity summary
            await self._update_event_activity()
            
        except Exception as e:
            logger.error(f"Error handling event in status panel: {e}")
    
    async def _refresh_status(self) -> None:
        """Refresh all status information."""
        try:
            await asyncio.gather(
                self._update_system_summary(),
                self._update_session_info(),
                self._update_mcp_status(),
                self._update_event_activity(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error refreshing status: {e}")
            await self._update_error_state(f"Refresh error: {e}")
    
    async def _update_system_summary(self) -> None:
        """Update the system overview section."""
        try:
            now = datetime.now(timezone.utc)
            uptime_str = f"Updated: {now.strftime('%H:%M:%S')}"
            
            # Get basic system info
            summary_widget = self.query_one("#system_summary", Static)
            summary_widget.update(
                f"🟢 Nagatha Assistant Running\n"
                f"⏰ {uptime_str}\n"
                f"📊 Last Event: {self.last_update.strftime('%H:%M:%S') if self.last_update else 'None'}"
            )
            
        except Exception as e:
            logger.error(f"Error updating system summary: {e}")
    
    async def _update_session_info(self) -> None:
        """Update the current session information."""
        try:
            session_widget = self.query_one("#session_details", Static)
            
            if self.session_id:
                # Try to get session info
                try:
                    sessions = await agent.list_sessions()
                    current_session = None
                    for session in sessions:
                        if session.id == self.session_id:
                            current_session = session
                            break
                    
                    if current_session:
                        created_str = current_session.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        session_widget.update(
                            f"📋 Session ID: {self.session_id}\n"
                            f"📅 Created: {created_str}\n" 
                            f"💬 Active conversation"
                        )
                    else:
                        session_widget.update(f"📋 Session ID: {self.session_id}\n❓ Session details unavailable")
                        
                except Exception as e:
                    session_widget.update(f"📋 Session ID: {self.session_id}\n⚠️ Error loading details: {e}")
            else:
                session_widget.update("📋 No active session")
                
        except Exception as e:
            logger.error(f"Error updating session info: {e}")
    
    async def _update_mcp_status(self) -> None:
        """Update the MCP servers status table."""
        try:
            # Get current MCP status
            mcp_status = await agent.get_mcp_status()
            self.mcp_status = mcp_status
            
            # Update the table
            mcp_table = self.query_one("#mcp_table", DataTable)
            mcp_table.clear()
            
            summary = mcp_status.get('summary', {})
            tools_info = mcp_status.get('tools', [])
            
            # Group tools by server
            servers_data = {}
            for tool in tools_info:
                server_name = tool.get('server', 'unknown')
                if server_name not in servers_data:
                    servers_data[server_name] = {
                        'tool_count': 0,
                        'status': '🟢 Connected',
                        'last_seen': 'Active'
                    }
                servers_data[server_name]['tool_count'] += 1
            
            # Add failed servers
            for server_name, error in summary.get('failed_servers', []):
                servers_data[server_name] = {
                    'tool_count': 0,
                    'status': '🔴 Failed',
                    'last_seen': 'Connection error'
                }
            
            # Populate table
            if servers_data:
                for server_name, data in servers_data.items():
                    mcp_table.add_row(
                        server_name,
                        data['status'],
                        str(data['tool_count']),
                        data['last_seen']
                    )
            else:
                mcp_table.add_row("No servers", "None", "0", "Never")
                
        except Exception as e:
            logger.error(f"Error updating MCP status: {e}")
            # Show error in table
            mcp_table = self.query_one("#mcp_table", DataTable)
            mcp_table.clear()
            mcp_table.add_row("Error", f"Failed to load: {e}", "0", "Error")
    
    async def _update_event_activity(self) -> None:
        """Update the event activity summary."""
        try:
            event_widget = self.query_one("#event_summary", Static)
            
            # Get recent event history
            event_bus = get_event_bus()
            recent_events = event_bus.get_event_history(limit=10)
            
            if recent_events:
                event_count = len(recent_events)
                latest_event = recent_events[0]
                
                # Count events by type
                event_types = {}
                for event in recent_events:
                    event_type = event.event_type.split('.')[0]  # Get first part
                    event_types[event_type] = event_types.get(event_type, 0) + 1
                
                # Format summary
                type_summary = ", ".join([f"{k}: {v}" for k, v in list(event_types.items())[:3]])
                
                event_widget.update(
                    f"📈 Recent Events: {event_count}\n"
                    f"⏱️ Latest: {latest_event.event_type}\n"
                    f"📊 Types: {type_summary}"
                )
            else:
                event_widget.update("📈 No recent events")
                
        except Exception as e:
            logger.error(f"Error updating event activity: {e}")
    
    async def _update_error_state(self, error_message: str) -> None:
        """Update the panel to show an error state."""
        try:
            summary_widget = self.query_one("#system_summary", Static)
            summary_widget.update(f"🔴 Error: {error_message}")
        except Exception as e:
            logger.error(f"Error updating error state: {e}")
            
    def watch_session_id(self, session_id: Optional[int]) -> None:
        """React to session ID changes."""
        if session_id is not None:
            # Schedule async update
            self.call_later(self._update_session_info)
    
    def watch_mcp_status(self, mcp_status: Dict[str, Any]) -> None:
        """React to MCP status changes."""
        # Schedule async update
        self.call_later(self._update_mcp_status)