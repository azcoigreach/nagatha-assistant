"""
Textual UI for Nagatha Assistant chat.
"""
import asyncio
import os
import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input
from textual.containers import Container

from nagatha_assistant.modules.chat import start_session, send_message, get_messages
from nagatha_assistant.utils.logger import setup_logger

# Use the shared logger setup and disable console output
logger = setup_logger("ui", disable_console=True)

# Redirect standard output and error to null when the UI is running
# sys.stdout = open(os.devnull, 'w')
# sys.stderr = open(os.devnull, 'w')


class ChatApp(App):
    """
    A Textual-based chat UI for Nagatha Assistant.
    """
    CSS = """
    Screen {
        layout: vertical;
    }
    #chat_log {
        height: 1fr;
        border: round $accent;
        padding: 1;
    }
    #chat_input {
        height: auto;
        border: round $accent;
        padding: 1;
    }
    """

    async def on_mount(self) -> None:
        # Initialize a new chat session
        self.session_id = await start_session()
        # Create UI components
        header = Header()
        footer = Footer()
        # Use RichLog for scrollable display, but isolate it from logging
        self.chat_log = RichLog(id="chat_log", wrap=True, highlight=False)
        self.chat_input = Input(placeholder="Type message and press Enter", id="chat_input")
        # Mount widgets vertically: header, chat log, input, footer
        await self.mount(header)
        await self.mount(self.chat_log)
        await self.mount(self.chat_input)
        await self.mount(footer)
        # Load any existing messages (should be none initially)
        history = await get_messages(self.session_id)
        for m in history:
            if m.role in ["user", "assistant"]:  # Only display chat messages
                self.chat_log.write(f"[{m.timestamp}] {m.role}: {m.content}")

        # Ensure the logger does not propagate to the RichLog
        logger.propagate = False

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value
        if not user_text.strip():
            return
        # Display user message
        self.chat_log.write(f"[you] {user_text}")
        # Send to AI
        reply = await send_message(self.session_id, user_text)
        # Display assistant reply
        self.chat_log.write(f"[assistant] {reply}")
        # Clear input
        self.chat_input.value = ""

def run_app():
    """
    Convenience function to run the ChatApp.
    """
    ChatApp().run()