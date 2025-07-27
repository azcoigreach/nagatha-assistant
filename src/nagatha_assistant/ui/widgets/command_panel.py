"""
Command Input Panel Widget for Nagatha Assistant Dashboard.

This widget provides an enhanced command input interface with:
- Command history navigation
- Auto-completion suggestions
- Real-time command validation
- Support for different command modes
"""

import asyncio
from typing import List, Optional, Callable, Any
from textual.app import ComposeResult
from textual.widgets import Input, Static, ListView, ListItem, Label
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.binding import Binding

from nagatha_assistant.core.event_bus import get_event_bus, Event
from nagatha_assistant.core.event import create_agent_event, StandardEventTypes, EventPriority
from nagatha_assistant.core import agent
from nagatha_assistant.utils.logger import setup_logger_with_env_control, get_logger

logger = get_logger()


class CommandPanel(Vertical):
    """
    Enhanced command input panel with history and suggestions.
    """
    
    BINDINGS = [
        Binding("up", "history_previous", "Previous command", show=False),
        Binding("down", "history_next", "Next command", show=False),
        Binding("ctrl+r", "clear_input", "Clear input", show=False),
        Binding("tab", "show_suggestions", "Show suggestions", show=False),
    ]
    
    # Reactive attributes
    current_session_id: reactive[Optional[int]] = reactive(None)
    command_mode: reactive[str] = reactive("chat")  # chat, tool, system
    
    def __init__(self, 
                 on_command_submitted: Optional[Callable[[str, str], Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.on_command_submitted = on_command_submitted
        self.command_history: List[str] = []
        self.history_index = 0
        self.max_history = 100
        self.suggestions_visible = False
        
    def compose(self) -> ComposeResult:
        """Compose the command panel interface."""
        
        # Command mode selector
        with Horizontal(id="command_mode_bar"):
            yield Static("Mode:", classes="mode-label")
            yield Static("💬 Chat", id="mode_indicator", classes="mode-chat")
            
        # Command input area
        with Vertical(id="command_input_area"):
            yield Input(
                placeholder="Type your message or command...",
                id="command_input"
            )
            yield Static("Ready", id="command_status", classes="status-ready")
            
        # Command suggestions (initially hidden)
        with Vertical(id="suggestions_area", classes="hidden"):
            yield Static("Suggestions:", classes="suggestions-header")
            yield ListView(id="suggestions_list")
            
        # Command history (collapsible)
        with Vertical(id="history_area", classes="compact"):
            yield Static("Recent Commands (↑/↓ to navigate):", classes="history-header")
            yield ListView(id="history_list")
    
    async def on_mount(self) -> None:
        """Initialize the command panel when mounted."""
        try:
            # Focus on input by default
            input_widget = self.query_one("#command_input", Input)
            input_widget.focus()
            
            # Load command history if available
            await self._load_command_history()
            
            # Update suggestions
            await self._update_suggestions()
            
        except Exception as e:
            logger.error(f"Error initializing command panel: {e}")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        if event.input.id != "command_input":
            return
            
        command = event.value.strip()
        if not command:
            return
            
        try:
            # Add to history
            self._add_to_history(command)
            
            # Clear input
            event.input.value = ""
            
            # Update status
            status_widget = self.query_one("#command_status", Static)
            status_widget.update("Processing...")
            status_widget.remove_class("status-ready")
            status_widget.add_class("status-processing")
            
            # Determine command type and execute
            command_type = self._determine_command_type(command)
            
            # Call the command handler if provided
            if self.on_command_submitted:
                try:
                    await self.on_command_submitted(command, command_type)
                    status_widget.update("✓ Command sent")
                    status_widget.remove_class("status-processing")
                    status_widget.add_class("status-success")
                except Exception as e:
                    status_widget.update(f"✗ Error: {str(e)[:50]}...")
                    status_widget.remove_class("status-processing")
                    status_widget.add_class("status-error")
            else:
                # Default handling - just publish event
                event_bus = get_event_bus()
                command_event = create_agent_event(
                    StandardEventTypes.UI_USER_ACTION,
                    self.current_session_id or 0,
                    {
                        "action": "command_submitted",
                        "command": command,
                        "command_type": command_type
                    }
                )
                await event_bus.publish(command_event)
                
                status_widget.update("✓ Command logged")
                status_widget.remove_class("status-processing")
                status_widget.add_class("status-success")
            
            # Reset status after a delay
            self.set_timer(3.0, lambda: self._reset_status())
            
            # Update history display
            await self._update_history_display()
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            status_widget = self.query_one("#command_status", Static)
            status_widget.update(f"✗ Error: {e}")
            status_widget.remove_class("status-processing")
            status_widget.add_class("status-error")
    
    def action_history_previous(self) -> None:
        """Navigate to previous command in history."""
        if not self.command_history:
            return
            
        input_widget = self.query_one("#command_input", Input)
        
        if self.history_index < len(self.command_history):
            self.history_index += 1
            if self.history_index <= len(self.command_history):
                command = self.command_history[-self.history_index] if self.history_index <= len(self.command_history) else ""
                input_widget.value = command
    
    def action_history_next(self) -> None:
        """Navigate to next command in history."""
        if not self.command_history:
            return
            
        input_widget = self.query_one("#command_input", Input)
        
        if self.history_index > 1:
            self.history_index -= 1
            command = self.command_history[-self.history_index]
            input_widget.value = command
        elif self.history_index == 1:
            self.history_index = 0
            input_widget.value = ""
    
    def action_clear_input(self) -> None:
        """Clear the input field."""
        input_widget = self.query_one("#command_input", Input)
        input_widget.value = ""
        self.history_index = 0
    
    def action_show_suggestions(self) -> None:
        """Toggle command suggestions display."""
        suggestions_area = self.query_one("#suggestions_area")
        
        if self.suggestions_visible:
            suggestions_area.add_class("hidden")
            self.suggestions_visible = False
        else:
            suggestions_area.remove_class("hidden")
            self.suggestions_visible = True
            self.call_later(self._update_suggestions)
    
    async def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for real-time validation and suggestions."""
        if event.input.id != "command_input":
            return
            
        command = event.value.strip()
        
        # Reset history navigation when user types
        self.history_index = 0
        
        # Update command mode indicator based on input
        self._update_command_mode(command)
        
        # Update suggestions if visible
        if self.suggestions_visible:
            await self._update_suggestions(command)
    
    def _determine_command_type(self, command: str) -> str:
        """Determine the type of command entered."""
        command_lower = command.lower().strip()
        
        # System commands
        if command_lower.startswith(('/help', '/status', '/sessions', '/tools')):
            return "system"
        
        # Tool invocation patterns
        if command_lower.startswith(('run:', 'execute:', 'tool:')):
            return "tool"
        
        # Default to chat
        return "chat"
    
    def _update_command_mode(self, command: str) -> None:
        """Update the visual command mode indicator."""
        mode_indicator = self.query_one("#mode_indicator", Static)
        command_type = self._determine_command_type(command)
        
        if command_type == "system":
            mode_indicator.update("⚙️ System")
            mode_indicator.remove_class("mode-chat", "mode-tool")
            mode_indicator.add_class("mode-system")
        elif command_type == "tool":
            mode_indicator.update("🔧 Tool")
            mode_indicator.remove_class("mode-chat", "mode-system")
            mode_indicator.add_class("mode-tool")
        else:
            mode_indicator.update("💬 Chat")
            mode_indicator.remove_class("mode-system", "mode-tool")
            mode_indicator.add_class("mode-chat")
        
        self.command_mode = command_type
    
    def _add_to_history(self, command: str) -> None:
        """Add a command to the history."""
        # Avoid duplicates
        if self.command_history and self.command_history[-1] == command:
            return
            
        self.command_history.append(command)
        
        # Limit history size
        if len(self.command_history) > self.max_history:
            self.command_history = self.command_history[-self.max_history:]
        
        # Reset history navigation
        self.history_index = 0
    
    async def _load_command_history(self) -> None:
        """Load command history from storage (if available)."""
        try:
            # For now, just initialize with empty history
            # In the future, this could load from database or file
            self.command_history = []
        except Exception as e:
            logger.error(f"Error loading command history: {e}")
    
    async def _update_history_display(self) -> None:
        """Update the visual history display."""
        try:
            history_list = self.query_one("#history_list", ListView)
            history_list.clear()
            
            # Show last 5 commands
            recent_commands = self.command_history[-5:] if self.command_history else []
            
            for i, command in enumerate(reversed(recent_commands)):
                # Truncate long commands
                display_command = command[:50] + "..." if len(command) > 50 else command
                history_list.append(ListItem(Label(f"{len(recent_commands)-i}. {display_command}")))
                
        except Exception as e:
            logger.error(f"Error updating history display: {e}")
    
    async def _update_suggestions(self, current_input: str = "") -> None:
        """Update command suggestions based on current input."""
        try:
            suggestions_list = self.query_one("#suggestions_list", ListView)
            suggestions_list.clear()
            
            # Basic suggestions based on command type and context
            suggestions = []
            
            if not current_input:
                # Default suggestions
                suggestions = [
                    "💬 Ask me anything",
                    "⚙️ /help - Show available commands",
                    "📊 /status - Show system status",
                    "🔧 /tools - List available tools",
                    "📋 /sessions - Manage sessions"
                ]
            else:
                # Context-aware suggestions
                if current_input.startswith('/'):
                    suggestions = [
                        "/help", "/status", "/tools", "/sessions", "/clear"
                    ]
                elif current_input.startswith('run:'):
                    suggestions = [
                        "run: python script",
                        "run: shell command",
                        "run: system check"
                    ]
                else:
                    # Chat suggestions based on recent patterns
                    suggestions = [
                        "How can I help you today?",
                        "What would you like to know?",
                        "Can you help me with...",
                        "Show me information about...",
                        "Execute the following task..."
                    ]
            
            # Filter suggestions based on input
            if current_input:
                suggestions = [s for s in suggestions if current_input.lower() in s.lower()]
            
            # Add to list
            for suggestion in suggestions[:5]:  # Limit to 5 suggestions
                suggestions_list.append(ListItem(Label(suggestion)))
                
        except Exception as e:
            logger.error(f"Error updating suggestions: {e}")
    
    def _reset_status(self) -> None:
        """Reset the status indicator to ready state."""
        try:
            status_widget = self.query_one("#command_status", Static)
            status_widget.update("Ready")
            status_widget.remove_class("status-processing", "status-success", "status-error")
            status_widget.add_class("status-ready")
        except Exception as e:
            logger.error(f"Error resetting status: {e}")
    
    def set_session_id(self, session_id: Optional[int]) -> None:
        """Set the current session ID for command context."""
        self.current_session_id = session_id
    
    def watch_current_session_id(self, session_id: Optional[int]) -> None:
        """React to session ID changes."""
        # Could update suggestions or validation based on session context
        pass