"""
Textual UI client for Nagatha Assistant.
"""
import os
import asyncio
import json
from datetime import datetime

from aiohttp import ClientSession
from textual.app import App
from textual.widgets import Static, Footer, RichLog, Input

# Initialize logging
from nagatha_assistant.utils.logger import setup_logger
logger = setup_logger()


class ApiClient:
    """HTTP client for Nagatha core server."""
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = ClientSession()

    async def close(self):
        await self.session.close()

    async def new_session(self) -> int:
        async with self.session.post(f"{self.base_url}/sessions") as resp:
            data = await resp.json()
            return data["id"]

    async def get_messages(self, session_id: int) -> list[dict]:
        async with self.session.get(f"{self.base_url}/sessions/{session_id}/messages") as resp:
            return await resp.json()

    async def send_message(self, session_id: int, content: str) -> str:
        async with self.session.post(
            f"{self.base_url}/sessions/{session_id}/messages", json={"content": content}
        ) as resp:
            data = await resp.json()
            return data.get("reply", "")



class ChatApp(App):
    """A Textual-based chat UI client for Nagatha."""
    CSS = """
    Screen {
        layout: vertical;
    }
    #header { text-align: center; }
    #chat_log { height: 1fr; border: round $accent; padding: 1; }
    #chat_input { height: auto; border: round $accent; padding: 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client: ApiClient
        self.session_id: int

    async def on_mount(self) -> None:
        # Setup client and session
        server = os.getenv("NAGATHA_SERVER", "http://127.0.0.1:8000")
        self.client = ApiClient(server)
        self.header = Static("", id="header")
        footer = Footer()
        self.chat_log = RichLog(id="chat_log", wrap=True, highlight=False)
        self.chat_input = Input(placeholder="Type message and press enter", id="chat_input")
        for w in (self.header, self.chat_log, self.chat_input, footer):
            await self.mount(w)
        # Header refresh
        self.set_interval(1, self._update_header)
        # Start a new session
        self.session_id = await self.client.new_session()
        self.chat_log.write(f"[system] Started session {self.session_id}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        # Display user message
        self.chat_log.write(f"[you] {text}")
        # Send message and display assistant reply
        reply = await self.client.send_message(self.session_id, text)
        self.chat_log.write(f"[nagatha] {reply}")
        self.chat_input.value = ""

    # WebSocket listener removed to simplify display

    def _update_header(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.header.update(f"Nagatha    {now}")

def run_app():
    """Run the Textual chat UI for Nagatha."""
    ChatApp().run()