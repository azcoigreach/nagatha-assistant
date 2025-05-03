"""
Textual UI for Nagatha Assistant chat.
"""
import asyncio
import os
import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input
# We now expose additional controls from the UI such as listing sessions or
# switching between them, so we import the necessary helpers.
# Note: Container is no longer required but kept for potential future layout
# enhancements.  If linting complains about the unused import, it can be
# safely removed.
from textual.containers import Container  # noqa: F401

from nagatha_assistant.modules.chat import (
    start_session,
    send_message,
    get_messages,
    list_sessions,
)
from nagatha_assistant.utils.logger import setup_logger

# Use the shared logger setup and disable console output
logger = setup_logger("ui", disable_console=True)
# Ensure root logger level honours LOG_LEVEL env-var even when UI is launched
# directly (i.e. not via the CLI entry-point which already does this).
import logging, os

root_level_name = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.root.setLevel(getattr(logging, root_level_name, logging.WARNING))

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
        """Set up widgets, create first session and show instructions."""

        # Runtime state --------------------------------------------------
        self.context_limit: int = int(os.getenv("CONTEXT_MEMORY_MESSAGES", "0"))
        self.session_id: int = await start_session()

        # Widgets --------------------------------------------------------
        header = Header()
        footer = Footer()
        self.chat_log = RichLog(id="chat_log", wrap=True, highlight=False)
        self.chat_input = Input(
            placeholder="Type message or /command (use /help)", id="chat_input"
        )

        for w in (header, self.chat_log, self.chat_input, footer):
            await self.mount(w)

        # Load history (none yet) and show helper text
        await self._render_history()
        self._print_help()

        # Prevent log propagation into RichLog
        logger.propagate = False

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        # Commands start with '/'
        if user_text.startswith("/"):
            await self._handle_command(user_text)
        else:
            # Regular chat ------------------------------------------------
            self.chat_log.write(f"[you] {user_text}")
            reply = await send_message(
                self.session_id, user_text, memory_limit=self.context_limit
            )
            self.chat_log.write(f"[nagatha] {reply}")

        # Clear input after processing
        self.chat_input.value = ""

    # ------------------------------------------------------------------
    # Helper / command handling
    # ------------------------------------------------------------------

    async def _handle_command(self, cmd: str) -> None:
        """Parse and execute slash commands from the input box."""

        parts = cmd.lstrip("/").split()
        if not parts:
            return

        name, *args = parts

        if name in ("help", "h"):
            self._print_help()
        elif name == "sessions":
            await self._list_sessions()
        elif name == "new":
            await self._new_session()
        elif name == "switch":
            if not args:
                self.chat_log.write("[system] Usage: /switch <session_id>")
            else:
                try:
                    await self._switch_session(int(args[0]))
                except ValueError:
                    self.chat_log.write("[system] session_id must be an integer")
        elif name == "context":
            if not args:
                self.chat_log.write(
                    f"[system] Current context_limit={self.context_limit}"
                )
            else:
                try:
                    new_limit = int(args[0])
                    if new_limit < 0:
                        raise ValueError
                    self.context_limit = new_limit
                    self.chat_log.write(
                        f"[system] Context limit set to {self.context_limit} messages"
                    )
                except ValueError:
                    self.chat_log.write("[system] context value must be >=0 integer")
        elif name == "history":
            await self._render_history()
        elif name == "models":
            await self._show_models()
        elif name == "usage":
            self._show_usage()
        else:
            self.chat_log.write(f"[system] Unknown command '{name}'. Try /help.")

    async def _new_session(self) -> None:
        new_id = await start_session()
        await self._switch_session(new_id)

    async def _render_history(self) -> None:
        self.chat_log.clear()
        msgs = await get_messages(self.session_id)
        if not msgs:
            self.chat_log.write("[system] (no history)")
        for m in msgs:
            if m.role in ("user", "assistant"):
                self.chat_log.write(f"[{m.timestamp}] {m.role}: {m.content}")

    async def _switch_session(self, session_id: int) -> None:
        sessions = await list_sessions()
        if not any(s.id == session_id for s in sessions):
            self.chat_log.write(f"[system] Session id {session_id} not found")
            return

        self.session_id = session_id
        await self._render_history()
        self.chat_log.write(f"[system] Switched to session {session_id}")

    async def _list_sessions(self):
        sessions = await list_sessions()
        if not sessions:
            self.chat_log.write("[system] No sessions.")
            return
        self.chat_log.write("[system] Sessions:")
        for s in sessions:
            self.chat_log.write(f" · id={s.id} created_at={s.created_at}")

    async def _show_models(self):
        """Fetch and display available models."""
        try:
            import openai

            client = openai.OpenAI()
            mdl_list = client.models.list()
        except Exception as exc:  # noqa: BLE001
            self.chat_log.write(f"[system] Error fetching models: {exc}")
            return

        self.chat_log.write("[system] Available models:")
        for m in mdl_list.data:
            self.chat_log.write(f" · {m.id}")

    def _show_usage(self):
        from nagatha_assistant.utils.usage_tracker import load_usage

        data = load_usage()
        if not data:
            self.chat_log.write("[system] No usage recorded yet.")
            return

        self.chat_log.write("[system] Usage statistics (tokens / cost):")
        for model, stats in data.items():
            cost = stats.get("cost_usd", 0)
            self.chat_log.write(
                f" · {model}: prompt={int(stats['prompt_tokens'])}, "
                f"completion={int(stats['completion_tokens'])}, cost=${cost:.4f}"
            )

    def _print_help(self):
        self.chat_log.write("[system] Commands:")
        self.chat_log.write("  /help                – show this help")
        self.chat_log.write("  /sessions            – list sessions")
        self.chat_log.write("  /new                 – create and switch to a new session")
        self.chat_log.write("  /switch <id>         – switch to existing session")
        self.chat_log.write("  /history             – show current session history")
        self.chat_log.write("  /context [N]         – get or set cross-session context limit")
        self.chat_log.write("  /models             – list available OpenAI models")
        self.chat_log.write("  /usage              – show total token usage & cost")

def run_app():
    """
    Convenience function to run the ChatApp.
    """
    ChatApp().run()