"""
Enhanced Dashboard Application for Nagatha Assistant.

This module provides a comprehensive dashboard interface that integrates:
- System status monitoring
- Command input with history
- Notifications and task management
- Resource usage visualization
- Real-time event monitoring
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, Any
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane
from textual.containers import Vertical, Horizontal, Container
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.reactive import reactive

from nagatha_assistant.core.event_bus import ensure_event_bus_started, Event
from nagatha_assistant.core.event import create_agent_event, StandardEventTypes, EventPriority
from nagatha_assistant.core import agent
from nagatha_assistant.utils.logger import setup_logger_with_env_control
from .widgets import StatusPanel, CommandPanel, NotificationPanel, ResourceMonitor

# Directly import needed functions from main ui module to avoid circular imports
import nagatha_assistant.ui as main_ui_module

logger = setup_logger_with_env_control()

# Configuration from environment
MCP_TIMEOUT = float(os.getenv("NAGATHA_MCP_TIMEOUT", "10"))
CONVERSATION_TIMEOUT = float(os.getenv("NAGATHA_CONVERSATION_TIMEOUT", "120"))


class DashboardApp(App):
    """
    Enhanced dashboard application with multi-panel layout and real-time updates.
    """
    
    CSS = """
    /* Global styles */
    Screen {
        layout: vertical;
    }
    
    /* Header styles */
    Header {
        dock: top;
        height: 3;
    }
    
    /* Main content area */
    #main_content {
        height: 1fr;
        layout: horizontal;
    }
    
    /* Left panel - Status and notifications */
    #left_panel {
        width: 30%;
        min-width: 40;
        layout: vertical;
        border-right: solid $accent;
    }
    
    /* Center panel - Command and conversation */
    #center_panel {
        width: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    
    /* Right panel - Resources and tools */
    #right_panel {
        width: 25%;
        min-width: 35;
        layout: vertical;
        border-left: solid $accent;
    }
    
    /* Footer */
    Footer {
        dock: bottom;
    }
    
    /* Widget specific styles */
    .panel-title {
        text-align: center;
        background: $accent 20%;
        padding: 1;
    }
    
    .resource-grid {
        grid-size: 1 3;
        grid-gutter: 1;
        height: auto;
    }
    
    .resource-item {
        height: 8;
        padding: 1;
        border: solid $accent;
        margin: 1 0;
    }
    
    .resource-label {
        text-align: center;
        margin-bottom: 1;
    }
    
    .resource-value {
        text-align: center;
        margin-top: 1;
    }
    
    .resource-details {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    
    .status-ready {
        color: $success;
    }
    
    .status-processing {
        color: $warning;
    }
    
    .status-success {
        color: $success;
    }
    
    .status-error {
        color: $error;
    }
    
    .mode-chat {
        color: $primary;
    }
    
    .mode-tool {
        color: $warning;
    }
    
    .mode-system {
        color: $accent;
    }
    
    .action-bar {
        height: auto;
        layout: horizontal;
    }
    
    .small-btn {
        min-width: 12;
        margin: 0 1;
    }
    
    .counter {
        color: $accent;
        text-style: bold;
    }
    
    .empty-state {
        color: $text-muted;
        text-align: center;
        margin: 1;
    }
    
    .hidden {
        display: none;
    }
    
    .compact {
        height: auto;
        max-height: 10;
    }
    
    .suggestions-header {
        color: $accent;
        text-style: bold;
        margin: 1 0;
    }
    
    .history-header {
        color: $accent;
        text-style: bold;
        margin: 1 0;
    }
    
    /* Section toggle styles */
    .section-hidden {
        display: none;
    }
    
    .section-visible {
        display: block;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+r", "refresh_all", "Refresh All"),
        Binding("ctrl+s", "show_sessions", "Sessions"),
        Binding("ctrl+t", "show_tools", "Tools"),
        Binding("ctrl+1", "toggle_command", "Toggle Command"),
        Binding("ctrl+2", "toggle_status", "Toggle Status"),
        Binding("ctrl+3", "toggle_notifications", "Toggle Notifications"),
        Binding("ctrl+4", "toggle_resources", "Toggle Resources"),
        Binding("f1", "show_help", "Help"),
    ]
    
    # Reactive attributes
    current_session_id: reactive[Optional[int]] = reactive(None)
    startup_status: reactive[dict] = reactive({})
    
    # Section visibility states
    status_visible: reactive[bool] = reactive(True)
    notifications_visible: reactive[bool] = reactive(True)
    resources_visible: reactive[bool] = reactive(True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Nagatha Assistant - Dashboard"
        self.sub_title = "Enhanced AI Assistant Interface"
        
        # Widget references
        self.status_panel: Optional[StatusPanel] = None
        self.command_panel: Optional[CommandPanel] = None
        self.notification_panel: Optional[NotificationPanel] = None
        self.resource_monitor: Optional[ResourceMonitor] = None
    
    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()
        
        with Container(id="main_content"):
            # Left Panel - Status and Notifications
            with Vertical(id="left_panel"):
                # Status Section
                with Vertical(id="status_section"):
                    yield Static("📊 System Status", classes="panel-title")
                    self.status_panel = StatusPanel(id="status_panel")
                    yield self.status_panel
                
                # Notifications Section
                with Vertical(id="notifications_section"):
                    yield Static("📬 Notifications", classes="panel-title")
                    self.notification_panel = NotificationPanel(id="notification_panel")
                    yield self.notification_panel
            
            # Center Panel - Command Interface
            with Vertical(id="center_panel"):
                # Command Section
                with Vertical(id="command_section"):
                    yield Static("💬 Command Interface", classes="panel-title")
                    self.command_panel = CommandPanel(
                        id="command_panel",
                        on_command_submitted=self._handle_command_submission
                    )
                    yield self.command_panel
                
                # Chat history/conversation area could go here
                yield Static("Conversation history and responses will appear here...", 
                           id="conversation_area", 
                           classes="empty-state")
            
            # Right Panel - Resources and Tools
            with Vertical(id="right_panel"):
                # Resources Section
                with Vertical(id="resources_section"):
                    yield Static("⚡ Resources", classes="panel-title")
                    self.resource_monitor = ResourceMonitor(id="resource_monitor")
                    yield self.resource_monitor
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the dashboard when mounted."""
        try:
            logger.info("Starting Nagatha Dashboard...")
            
            # Ensure event bus is running
            await ensure_event_bus_started()
            
            # Initialize with startup information
            self._update_conversation_area("🚀 Initializing Nagatha Dashboard...")
            
            # Start session and get MCP status
            self.current_session_id = await asyncio.wait_for(
                agent.start_session(), 
                timeout=MCP_TIMEOUT
            )
            
            startup_status = await agent.get_mcp_status()
            self.startup_status = startup_status
            
            # Update status panel with session ID
            if self.status_panel:
                self.status_panel.session_id = self.current_session_id
            
            # Update command panel with session ID
            if self.command_panel:
                self.command_panel.set_session_id(self.current_session_id)
            
            # Display initialization status
            summary = startup_status.get('summary', {})
            status_msg = agent.format_mcp_status_for_chat(summary)
            
            self._update_conversation_area(
                f"✅ Dashboard initialized successfully!\n"
                f"📋 Session ID: {self.current_session_id}\n"
                f"{status_msg}\n\n"
                f"Ready for commands. Use Ctrl+1-4 to toggle sections."
            )
            
            # Add startup message to database
            if summary.get('connected', 0) > 0:
                await agent.push_system_message(
                    self.current_session_id,
                    f"Dashboard initialized with {summary['connected']} MCP servers and {summary['total_tools']} tools."
                )
            else:
                await agent.push_system_message(
                    self.current_session_id,
                    "Dashboard initialized without MCP servers. Basic conversation available."
                )
            
            logger.info(f"Dashboard started with session {self.current_session_id}")
            
        except asyncio.TimeoutError:
            logger.error("Timeout while initializing dashboard")
            self._update_conversation_area("❌ Timeout during initialization. Please check system status.")
        except Exception as e:
            logger.exception("Failed to initialize dashboard")
            self._update_conversation_area(f"❌ Initialization failed: {e}")
    
    async def _handle_command_submission(self, command: str, command_type: str) -> None:
        """Handle command submission from the command panel."""
        try:
            self._update_conversation_area(f"👤 You: {command}")
            
            if command_type == "system":
                # Handle system commands locally
                await self._handle_system_command(command)
            else:
                # Send to agent for processing
                logger.info(f"Sending command to agent: {command}")
                
                reply = await asyncio.wait_for(
                    agent.send_message(self.current_session_id, command),
                    timeout=CONVERSATION_TIMEOUT
                )
                
                # Convert markdown to rich text for display
                formatted_reply = main_ui_module.markdown_to_rich(reply)
                self._update_conversation_area(f"🤖 Nagatha: {formatted_reply}")
                
                logger.info("Received reply from agent")
                
        except asyncio.TimeoutError:
            logger.error("Timeout while processing command")
            self._update_conversation_area("❌ Timeout while processing command.")
        except Exception as e:
            logger.exception("Error processing command")
            self._update_conversation_area(f"❌ Error processing command: {e}")
    
    async def _handle_system_command(self, command: str) -> None:
        """Handle system commands locally."""
        command_lower = command.lower().strip()
        
        if command_lower.startswith('/help'):
            help_text = self._get_help_text()
            self._update_conversation_area(f"🔧 System: {help_text}")
        
        elif command_lower.startswith('/status'):
            await self._show_system_status()
        
        elif command_lower.startswith('/sessions'):
            self.action_show_sessions()
        
        elif command_lower.startswith('/tools'):
            self.action_show_tools()
        
        elif command_lower.startswith('/refresh'):
            await self.action_refresh_all()
        
        elif command_lower.startswith('/clear'):
            self._clear_conversation_area()
        
        elif command_lower.startswith('/toggle'):
            await self._handle_toggle_command(command)
        
        else:
            self._update_conversation_area(f"🔧 System: Unknown command '{command}'. Type '/help' for available commands.")
    
    def _get_help_text(self) -> str:
        """Get help text for system commands."""
        return """
Available Commands:
• /help - Show this help message
• /status - Show detailed system status
• /sessions - Open session selector
• /tools - Show available MCP tools
• /refresh - Refresh all dashboard data
• /clear - Clear conversation area
• /toggle <section> - Toggle section visibility (status, notifications, resources, command)

Keyboard Shortcuts:
• Ctrl+1 - Toggle command section
• Ctrl+2 - Toggle status section
• Ctrl+3 - Toggle notifications section
• Ctrl+4 - Toggle resources section
• Ctrl+R - Refresh all data
• Ctrl+S - Show sessions
• Ctrl+T - Show tools
• Ctrl+Q - Quit application
"""
    
    async def _show_system_status(self) -> None:
        """Show detailed system status."""
        try:
            # Get current status from various sources
            mcp_status = await agent.get_mcp_status()
            summary = mcp_status.get('summary', {})
            
            status_text = f"""
🖥️ System Status Report:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Session: {self.current_session_id}
🔗 MCP Servers: {summary.get('connected', 0)}/{summary.get('total_configured', 0)} connected
🔧 Available Tools: {summary.get('total_tools', 0)}
⚡ Dashboard: Running normally

Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            self._update_conversation_area(f"🔧 System: {status_text}")
            
        except Exception as e:
            self._update_conversation_area(f"🔧 System: Error getting status: {e}")
    
    async def _handle_toggle_command(self, command: str) -> None:
        """Handle toggle commands for sections."""
        parts = command.lower().split()
        if len(parts) < 2:
            self._update_conversation_area("🔧 System: Usage: /toggle <section> (sections: status, notifications, resources, command)")
            return
        
        section = parts[1]
        
        if section == "status":
            self.action_toggle_status()
        elif section == "notifications":
            self.action_toggle_notifications()
        elif section == "resources":
            self.action_toggle_resources()
        elif section == "command":
            self.action_toggle_command()
        else:
            self._update_conversation_area(f"🔧 System: Unknown section '{section}'. Available: status, notifications, resources, command")
    
    def _update_conversation_area(self, message: str) -> None:
        """Update the conversation area with a new message."""
        try:
            conversation_area = self.query_one("#conversation_area", Static)
            current_text = conversation_area.renderable
            
            # If this is the first real message, clear the placeholder
            if "will appear here" in str(current_text):
                conversation_area.update(message)
            else:
                # Append new message
                new_text = f"{current_text}\n\n{message}"
                # Limit to last 1000 characters to prevent overflow
                if len(new_text) > 1000:
                    new_text = "...\n" + new_text[-950:]
                conversation_area.update(new_text)
                
        except Exception as e:
            logger.error(f"Error updating conversation area: {e}")
    
    def _clear_conversation_area(self) -> None:
        """Clear the conversation area."""
        try:
            conversation_area = self.query_one("#conversation_area", Static)
            conversation_area.update("Conversation cleared. Ready for new commands.")
        except Exception as e:
            logger.error(f"Error clearing conversation area: {e}")
    
    # Action handlers
    def action_toggle_command(self) -> None:
        """Toggle the command section visibility."""
        try:
            command_section = self.query_one("#command_section")
            if command_section.has_class("section-hidden"):
                command_section.remove_class("section-hidden")
                self._update_conversation_area("🔧 System: Command section shown")
            else:
                command_section.add_class("section-hidden")
                self._update_conversation_area("🔧 System: Command section hidden")
        except Exception as e:
            logger.error(f"Error toggling command section: {e}")
    
    def action_toggle_status(self) -> None:
        """Toggle the status section visibility."""
        try:
            status_section = self.query_one("#status_section")
            if status_section.has_class("section-hidden"):
                status_section.remove_class("section-hidden")
                self.status_visible = True
                self._update_conversation_area("🔧 System: Status section shown")
            else:
                status_section.add_class("section-hidden")
                self.status_visible = False
                self._update_conversation_area("🔧 System: Status section hidden")
        except Exception as e:
            logger.error(f"Error toggling status section: {e}")
    
    def action_toggle_notifications(self) -> None:
        """Toggle the notifications section visibility."""
        try:
            notifications_section = self.query_one("#notifications_section")
            if notifications_section.has_class("section-hidden"):
                notifications_section.remove_class("section-hidden")
                self.notifications_visible = True
                self._update_conversation_area("🔧 System: Notifications section shown")
            else:
                notifications_section.add_class("section-hidden")
                self.notifications_visible = False
                self._update_conversation_area("🔧 System: Notifications section hidden")
        except Exception as e:
            logger.error(f"Error toggling notifications section: {e}")
    
    def action_toggle_resources(self) -> None:
        """Toggle the resources section visibility."""
        try:
            resources_section = self.query_one("#resources_section")
            if resources_section.has_class("section-hidden"):
                resources_section.remove_class("section-hidden")
                self.resources_visible = True
                self._update_conversation_area("🔧 System: Resources section shown")
            else:
                resources_section.add_class("section-hidden")
                self.resources_visible = False
                self._update_conversation_area("🔧 System: Resources section hidden")
        except Exception as e:
            logger.error(f"Error toggling resources section: {e}")
    
    async def action_refresh_all(self) -> None:
        """Refresh all dashboard data."""
        try:
            self._update_conversation_area("🔄 Refreshing all dashboard data...")
            
            # Trigger refresh on all panels
            if self.status_panel:
                await self.status_panel._refresh_status()
            
            if self.notification_panel:
                await self.notification_panel._refresh_all_data()
            
            if self.resource_monitor:
                await self.resource_monitor._update_all_metrics()
            
            self._update_conversation_area("✅ Dashboard refresh completed.")
            
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")
            self._update_conversation_area(f"❌ Error refreshing dashboard: {e}")
    
    def action_show_sessions(self) -> None:
        """Show the session selector modal."""
        def handle_session_selection(session_id: Optional[int]) -> None:
            if session_id is not None:
                self.current_session_id = session_id
                if self.status_panel:
                    self.status_panel.session_id = session_id
                if self.command_panel:
                    self.command_panel.set_session_id(session_id)
                self._update_conversation_area(f"📋 Switched to session {session_id}")
                logger.info(f"Switched to session {session_id}")
        
        try:
            self.push_screen(main_ui_module.SessionSelectorModal(), handle_session_selection)
        except Exception as e:
            logger.exception("Error showing session selector")
            self._update_conversation_area(f"❌ Error showing session selector: {e}")
    
    def action_show_tools(self) -> None:
        """Show the tools information modal."""
        try:
            self.push_screen(main_ui_module.ToolsInfoModal(self.startup_status))
        except Exception as e:
            logger.exception("Error showing tools information")
            self._update_conversation_area(f"❌ Error showing tools information: {e}")
    
    def action_show_help(self) -> None:
        """Show help information."""
        help_text = self._get_help_text()
        self._update_conversation_area(f"🔧 Help: {help_text}")
    
    def watch_current_session_id(self, session_id: Optional[int]) -> None:
        """React to session ID changes."""
        if session_id is not None and self.status_panel:
            self.status_panel.session_id = session_id
    
    def watch_status_visible(self, visible: bool) -> None:
        """React to status section visibility changes."""
        try:
            status_section = self.query_one("#status_section")
            if visible:
                status_section.remove_class("section-hidden")
            else:
                status_section.add_class("section-hidden")
        except Exception as e:
            logger.error(f"Error updating status section visibility: {e}")
    
    def watch_notifications_visible(self, visible: bool) -> None:
        """React to notifications section visibility changes."""
        try:
            notifications_section = self.query_one("#notifications_section")
            if visible:
                notifications_section.remove_class("section-hidden")
            else:
                notifications_section.add_class("section-hidden")
        except Exception as e:
            logger.error(f"Error updating notifications section visibility: {e}")
    
    def watch_resources_visible(self, visible: bool) -> None:
        """React to resources section visibility changes."""
        try:
            resources_section = self.query_one("#resources_section")
            if visible:
                resources_section.remove_class("section-hidden")
            else:
                resources_section.add_class("section-hidden")
        except Exception as e:
            logger.error(f"Error updating resources section visibility: {e}")


async def run_dashboard():
    """Run the dashboard application."""
    app = DashboardApp()
    await app.run_async()


if __name__ == "__main__":
    asyncio.run(run_dashboard())