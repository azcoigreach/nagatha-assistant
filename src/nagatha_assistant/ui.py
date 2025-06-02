"""
Textual UI client for Nagatha Assistant.
"""
import nagatha_assistant  # Ensures .env is loaded
import os
import asyncio
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Static, Footer, RichLog, Input, OptionList, Button
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from nagatha_assistant.utils.logger import setup_logger_with_env_control, should_log_to_chat
from nagatha_assistant.core import agent
import logging

# Set up enhanced logger
logger = setup_logger_with_env_control()

# Get tool name from env or default
MCP_TOOL = os.getenv("NAGATHA_MCP_TOOL", "run_python_code")
MCP_TIMEOUT = float(os.getenv("NAGATHA_MCP_TIMEOUT", "10"))
# Longer timeout for conversations that may involve tool calls
CONVERSATION_TIMEOUT = float(os.getenv("NAGATHA_CONVERSATION_TIMEOUT", "120"))

def markdown_to_rich(text: str) -> str:
    """Convert basic markdown syntax to Rich markup."""
    if not text:
        return text
    
    import re
    
    # Convert common markdown patterns to Rich markup
    # Bold: **text** or __text__ -> [bold]text[/bold]
    text = re.sub(r'\*\*(.*?)\*\*', r'[bold]\1[/bold]', text)
    text = re.sub(r'__(.*?)__', r'[bold]\1[/bold]', text)
    
    # Italic: *text* or _text_ -> [italic]text[/italic]  
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'[italic]\1[/italic]', text)
    text = re.sub(r'(?<!_)_([^_]+?)_(?!_)', r'[italic]\1[/italic]', text)
    
    # Code: `text` -> [cyan]text[/cyan] (using cyan for better visibility)
    text = re.sub(r'`([^`]+?)`', r'[cyan]\1[/cyan]', text)
    
    # Code blocks: ```text``` -> [cyan]text[/cyan]
    text = re.sub(r'```([^`]+?)```', r'[cyan]\1[/cyan]', text, flags=re.DOTALL)
    
    # Links: [text](url) -> [link=url]text[/link]
    text = re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', r'[link=\2]\1[/link]', text)
    
    # Headers: # Header -> [bold]Header[/bold]
    text = re.sub(r'^#+\s*(.+)$', r'[bold]\1[/bold]', text, flags=re.MULTILINE)
    
    # Escape any existing Rich markup that might conflict
    # This needs to be done carefully to not break our new markup
    return text

class ToolsInfoModal(ModalScreen[None]):
    """Modal screen for displaying available MCP tools."""
    
    CSS = """
    ToolsInfoModal {
        align: center middle;
    }
    
    #tools_dialog {
        width: 90;
        height: 30;
        border: thick $background 80%;
        background: $surface;
    }
    
    #tools_content {
        height: 1fr;
        border: solid $accent;
        margin: 1;
        padding: 1;
    }
    
    #server_list {
        height: 10;
        border: solid $accent;
        margin: 1;
    }
    
    #tool_details {
        height: 1fr;
        border: solid $accent;
        margin: 1;
        padding: 1;
    }
    
    #tools_buttons {
        height: auto;
        margin: 1;
    }
    
    .server-connected { color: $success; }
    .server-failed { color: $error; }
    .server-partial { color: $warning; }
    """
    
    def __init__(self):
        super().__init__()
        self.mcp_status = None
        self.tools_by_server = {}
    
    def compose(self) -> ComposeResult:
        with Vertical(id="tools_dialog"):
            yield Static("MCP Servers & Tools", classes="title")
            yield Static("Select a server to view its tools:", classes="subtitle")
            yield OptionList(id="server_list")
            yield RichLog(id="tool_details", wrap=True, highlight=False)
            with Horizontal(id="tools_buttons"):
                yield Button("Refresh", variant="default", id="refresh_btn")
                yield Button("Close", variant="primary", id="close_btn")
    
    async def on_mount(self) -> None:
        """Load and display the list of MCP servers."""
        await self.refresh_data()
    
    async def refresh_data(self) -> None:
        """Refresh the MCP server and tools data."""
        server_list = self.query_one("#server_list", OptionList)
        tool_details = self.query_one("#tool_details", RichLog)
        
        # Clear existing data
        server_list.clear_options()
        tool_details.clear()
        
        try:
            # Get MCP status including server connection info
            self.mcp_status = await agent.get_mcp_status()
            tools = self.mcp_status.get('tools', [])
            summary = self.mcp_status.get('summary', {})
            
            # Group tools by server
            self.tools_by_server = {}
            for tool in tools:
                server = tool.get('server', 'unknown')
                if server not in self.tools_by_server:
                    self.tools_by_server[server] = []
                self.tools_by_server[server].append(tool)
            
            # Show server overview
            if summary.get('total_configured', 0) == 0:
                server_list.add_option(Option("No MCP servers configured", disabled=True))
                tool_details.write("No MCP servers are configured in mcp.json")
            else:
                # Add connected servers
                connected_servers = set()
                for server_name in self.tools_by_server.keys():
                    connected_servers.add(server_name)
                    tool_count = len(self.tools_by_server[server_name])
                    status_icon = "✓"
                    css_class = "server-connected"
                    server_list.add_option(Option(
                        f"{status_icon} {server_name} ({tool_count} tools)",
                        id=server_name
                    ))
                
                # Add failed servers from summary
                failed_servers = summary.get('failed_servers', [])
                for server_name, error in failed_servers:
                    if server_name not in connected_servers:
                        status_icon = "✗"
                        css_class = "server-failed"
                        server_list.add_option(Option(
                            f"{status_icon} {server_name} (failed)",
                            id=f"failed_{server_name}"
                        ))
                
                # Show overall status in details pane
                connected = summary.get('connected', 0)
                total_configured = summary.get('total_configured', 0)
                total_tools = summary.get('total_tools', 0)
                
                tool_details.write("[bold]MCP Server Status Overview[/bold]")
                tool_details.write(f"Connected servers: {connected}/{total_configured}")
                tool_details.write(f"Total available tools: {total_tools}")
                
                if failed_servers:
                    tool_details.write("\n[bold red]Connection Failures:[/bold red]")
                    for server_name, error in failed_servers:
                        tool_details.write(f"• {server_name}: {error}")
                
                tool_details.write("\n[dim]Select a server above to view its tools and capabilities.[/dim]")
                
        except Exception as e:
            server_list.add_option(Option(f"Error loading servers: {e}", disabled=True))
            tool_details.write(f"[red]Error loading MCP data: {e}[/red]")
    
    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle server selection to show its tools."""
        server_name = event.option.id
        if not server_name or server_name.startswith("failed_"):
            return
            
        tool_details = self.query_one("#tool_details", RichLog)
        tool_details.clear()
        
        # Show tools for the selected server
        if server_name in self.tools_by_server:
            tools = self.tools_by_server[server_name]
            tool_details.write(f"[bold cyan]{server_name}[/bold cyan] - {len(tools)} tools available")
            tool_details.write("")
            
            for i, tool in enumerate(tools, 1):
                tool_details.write(f"[bold]{i}. {tool['name']}[/bold]")
                description = markdown_to_rich(tool.get('description', 'No description'))
                tool_details.write(f"   {description}")
                
                # Show parameters if available
                if 'parameters' in tool and tool['parameters']:
                    params = tool['parameters']
                    if 'properties' in params:
                        required = params.get('required', [])
                        properties = params['properties']
                        
                        tool_details.write("   [dim]Parameters:[/dim]")
                        for param_name, param_info in properties.items():
                            param_type = param_info.get('type', 'unknown')
                            is_required = " (required)" if param_name in required else ""
                            param_desc = markdown_to_rich(param_info.get('description', 'No description'))
                            tool_details.write(f"   • {param_name} ({param_type}){is_required}: {param_desc}")
                
                tool_details.write("")
            
            # Scroll to top after writing all content
            tool_details.scroll_home()
        else:
            tool_details.write(f"[yellow]No tools found for server: {server_name}[/yellow]")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "close_btn":
            self.dismiss()
        elif event.button.id == "refresh_btn":
            await self.refresh_data()

class SessionSelectorModal(ModalScreen[int]):
    """Modal screen for selecting a chat session."""
    
    CSS = """
    SessionSelectorModal {
        align: center middle;
    }
    
    #session_dialog {
        width: 60;
        height: 20;
        border: thick $background 80%;
        background: $surface;
    }
    
    #session_list {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }
    
    #session_buttons {
        height: auto;
        margin: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Vertical(id="session_dialog"):
            yield Static("Select a Chat Session", classes="title")
            yield OptionList(id="session_list")
            with Horizontal(id="session_buttons"):
                yield Button("Select", variant="primary", id="select_btn")
                yield Button("Cancel", variant="default", id="cancel_btn")
    
    async def on_mount(self) -> None:
        """Load and display the list of chat sessions."""
        session_list = self.query_one("#session_list", OptionList)
        
        try:
            sessions = await agent.list_sessions()
            if not sessions:
                session_list.add_option(Option("No sessions found", disabled=True))
            else:
                for session in sessions:
                    # Format the session display with ID and creation date
                    created_str = session.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    option_text = f"Session {session.id} - {created_str}"
                    session_list.add_option(Option(option_text, id=session.id))
        except Exception as e:
            session_list.add_option(Option(f"Error loading sessions: {e}", disabled=True))
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "select_btn":
            session_list = self.query_one("#session_list", OptionList)
            if session_list.highlighted is not None:
                selected_option = session_list.get_option_at_index(session_list.highlighted)
                if selected_option and selected_option.id is not None:
                    self.dismiss(selected_option.id)
                else:
                    self.dismiss(None)
            else:
                self.dismiss(None)
        elif event.button.id == "cancel_btn":
            self.dismiss(None)
    
    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (double-click or Enter)."""
        if event.option.id is not None:
            self.dismiss(event.option.id)

class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #header { text-align: center; }
    #chat_log { height: 1fr; border: round $accent; padding: 1; }
    #chat_input { height: auto; border: round $accent; padding: 1; }
    """
    BINDINGS = [
        Binding("ctrl+c", "copy_chat", "Copy chat log"),
        Binding("ctrl+s", "show_sessions", "Switch session"),
        Binding("ctrl+t", "show_tools", "Show tools"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session_id: int = None
        self.startup_status: dict = None

    async def on_mount(self) -> None:
        self.header = Static("", id="header")
        footer = Footer()
        self.chat_log = RichLog(id="chat_log", wrap=True, highlight=False)
        self.chat_input = Input(placeholder="Type message and press enter", id="chat_input")
        for w in (self.header, self.chat_log, self.chat_input, footer):
            await self.mount(w)
        self.set_interval(1, self._update_header)
        
        # Initialize with startup information
        try:
            logger.info("Starting Nagatha chat session...")
            self.chat_log.write("[system] Initializing Nagatha and MCP servers...")
            
            # Start session and get MCP status
            self.session_id = await asyncio.wait_for(agent.start_session(), timeout=MCP_TIMEOUT)
            self.startup_status = await agent.get_mcp_status()
            
            # Display initialization status
            summary = self.startup_status.get('summary', {})
            status_msg = agent.format_mcp_status_for_chat(summary)
            
            self.chat_log.write(f"[system] Started session {self.session_id}")
            self.chat_log.write(f"[system] {status_msg}")
            
            # If there are failed servers, show them as errors too
            if summary.get('failed'):
                error_msg = f"Some MCP servers failed to connect. Check logs for details."
                self.chat_log.write(f"[error] {error_msg}")
                logger.warning(error_msg)
            
            # Add startup message to database
            if summary.get('connected', 0) > 0:
                await agent.push_system_message(
                    self.session_id, 
                    f"Nagatha initialized with {summary['connected']} MCP servers and {summary['total_tools']} tools."
                )
            else:
                await agent.push_system_message(
                    self.session_id,
                    "Nagatha initialized without MCP servers. Basic conversation available."
                )
            
            await self._refresh_messages()
            logger.info(f"Started session {self.session_id} with {summary.get('connected', 0)} MCP servers")
            
        except asyncio.TimeoutError:
            logger.error("Timeout while connecting to MCP agent (start_session)")
            self.chat_log.write("[error] Timeout while starting session.")
        except Exception as e:
            logger.exception("Failed to start session")
            self.chat_log.write(f"[error] Failed to start session: {e}")

    async def _refresh_messages(self):
        try:
            logger.debug(f"Fetching messages for session {self.session_id}")
            messages = await asyncio.wait_for(agent.get_messages(self.session_id), timeout=MCP_TIMEOUT)
            self.chat_log.clear()
            
            # Show startup status first if available
            if self.startup_status:
                summary = self.startup_status.get('summary', {})
                status_msg = agent.format_mcp_status_for_chat(summary)
                self.chat_log.write(f"[system] {status_msg}")
            
            for m in messages:
                if m.role == "user":
                    prefix = "[you]"
                elif m.role == "system":
                    prefix = "[system]"
                else:
                    prefix = "[nagatha]"
                self.chat_log.write(f"{prefix} {m.content}")
        except asyncio.TimeoutError:
            logger.error("Timeout while fetching messages from MCP agent")
            self.chat_log.write("[error] Timeout while fetching messages.")
        except Exception as e:
            logger.exception("Failed to fetch messages")
            self.chat_log.write(f"[error] Failed to fetch messages: {e}")

    def action_show_sessions(self) -> None:
        """Show the session selector modal."""
        def handle_session_selection(session_id: int | None) -> None:
            """Handle the session selection result."""
            if session_id is not None:
                # Switch to the selected session
                self.session_id = session_id
                self.chat_log.write(f"[system] Switched to session {self.session_id}")
                logger.info(f"Switched to session {self.session_id}")
                # Schedule the refresh using call_later with a proper async method
                self.call_later(self._do_refresh_messages)
                # Focus back on the input
                self.query_one("#chat_input", Input).focus()
        
        try:
            self.push_screen(SessionSelectorModal(), handle_session_selection)
        except Exception as e:
            logger.exception("Error showing session selector")
            self.chat_log.write(f"[error] Failed to show session selector: {e}")

    def action_show_tools(self) -> None:
        """Show the tools information modal."""
        try:
            self.push_screen(ToolsInfoModal())
        except Exception as e:
            logger.exception("Error showing tools information")
            self.chat_log.write(f"[error] Failed to show tools information: {e}")

    async def _do_refresh_messages(self) -> None:
        """Wrapper method to properly handle async refresh."""
        await self._refresh_messages()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        self.chat_log.write(f"[you] {text}")
        try:
            # Use normal conversation mode by default (no tool_name)
            # The agent will intelligently decide whether to use LLM or MCP tools
            logger.info(f"Sending message to agent for normal conversation")
            reply = await asyncio.wait_for(
                agent.send_message(self.session_id, text),
                timeout=CONVERSATION_TIMEOUT
            )
            self.chat_log.write(f"[nagatha] {reply}")
            logger.info(f"Received reply from agent")
        except asyncio.TimeoutError:
            logger.error("Timeout while sending message to agent")
            self.chat_log.write("[error] Timeout while sending message to agent.")
        except Exception as e:
            logger.exception("Error sending message to agent")
            self.chat_log.write(f"[error] Agent error: {e}")
        self.chat_input.value = ""

    def _update_header(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        session_info = f"Session {self.session_id}" if self.session_id else "No Session"
        
        # Show MCP status in header
        mcp_status = ""
        if self.startup_status:
            summary = self.startup_status.get('summary', {})
            connected = summary.get('connected', 0)
            total = summary.get('total_configured', 0)
            if total > 0:
                if connected == total:
                    mcp_status = f" | MCP: {connected}/{total} ✓"
                elif connected > 0:
                    mcp_status = f" | MCP: {connected}/{total} ⚠"
                else:
                    mcp_status = f" | MCP: {connected}/{total} ✗"
            else:
                mcp_status = " | MCP: none"
        
        self.header.update(f"Nagatha - {session_info}{mcp_status} - {now}")

    def action_copy_chat(self) -> None:
        log: RichLog = self.query_one("#chat_log")
        plain_lines: list[str] = []
        for strip in log.lines:
            if hasattr(strip, "plain"):
                plain_lines.append(strip.plain)
            else:
                plain_lines.append("".join(seg.text for seg in strip))
        text = "\n".join(plain_lines)
        try:
            import pyperclip
            pyperclip.copy(text)
            method = "pyperclip"
        except Exception:
            import base64
            b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
            print(f"\033]52;c;{b64}\a", end="", flush=True)
            method = "OSC52"
        self.chat_log.write(f"[system] Chat log copied via {method}.")
        self.chat_log.scroll_end()
        self.query_one("#chat_input", Input).focus()

async def run_app():
    """Run the Textual chat application."""
    app = ChatApp()
    await app.run_async()