"""
Textual UI for Nagatha Assistant chat.
"""
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input
from textual.containers import Container

from nagatha_assistant.modules.chat import start_session, send_message, get_messages


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
        # Create UI
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")
        # Use RichLog for scrollable display
        self.chat_log = RichLog(id="chat_log")
        self.chat_input = Input(placeholder="Type message and press Enter", id="chat_input")
        await self.view.dock(self.chat_log, edge="left")
        await self.view.dock(self.chat_input, edge="bottom")
        # Load any existing messages (should be none)
        history = await get_messages(self.session_id)
        for m in history:
            self.chat_log.write(f"[{m.timestamp}] {m.role}: {m.content}")

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