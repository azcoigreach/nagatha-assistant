import abc
import os
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable

from sqlalchemy import select
from openai import AsyncOpenAI

from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import ConversationSession, Message
from nagatha_assistant.utils.usage_tracker import record_usage
from nagatha_assistant.core.plugin import PluginManager


class Agent(abc.ABC):
    """
    Base Agent class for Nagatha Assistant.
    """

    @abc.abstractmethod
    async def run(self, *args, **kwargs):
        """
        Run the agent's main logic.
        """
        pass

# Plugin manager singleton and teardown registration
_plugin_manager: Optional[PluginManager] = None

async def _ensure_plugins_ready() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        from nagatha_assistant.utils.logger import setup_logger
        setup_logger()
        _plugin_manager = PluginManager()
        await _plugin_manager.discover()
        await _plugin_manager.setup_all({})
    return _plugin_manager

def _register_teardown() -> None:
    import atexit

    async def _async_teardown():
        if _plugin_manager:
            await _plugin_manager.teardown_all()

    def _sync():
        try:
            asyncio.run(_async_teardown())
        except RuntimeError:
            pass

    atexit.register(_sync)

_register_teardown()

# OpenAI client
client = AsyncOpenAI()

# Push notification pub/sub for UIs and other listeners
_push_callbacks: Dict[int, List[Callable[[Message], Awaitable[None]]]] = {}

def subscribe_session(session_id: int, callback: Callable[[Message], Awaitable[None]]) -> None:
    """Register a coroutine callback to receive new messages for a session."""
    _push_callbacks.setdefault(session_id, []).append(callback)

def unsubscribe_session(session_id: int, callback: Callable[[Message], Awaitable[None]]) -> None:
    """Remove a previously registered callback for a session."""
    if session_id in _push_callbacks:
        try:
            _push_callbacks[session_id].remove(callback)
        except ValueError:
            pass

async def _notify(session_id: int, message: Message) -> None:
    """Invoke all registered callbacks for a session with the new message."""
    callbacks = _push_callbacks.get(session_id, [])
    for cb in callbacks:
        try:
            res = cb(message)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception:
            logging.exception("Error in push callback for session %s", session_id)

# Database initialization and session handling
async def init_db() -> None:
    """Ensure the database schema is up-to-date."""
    await ensure_schema()

async def start_session() -> int:
    """Create a new conversation session and return its ID."""
    await init_db()
    async with SessionLocal() as session:
        new_session = ConversationSession()
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)
        return new_session.id

async def get_messages(session_id: int) -> List[Message]:
    """Retrieve all messages for a session, ordered by timestamp."""
    async with SessionLocal() as session:
        stmt = select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
        result = await session.execute(stmt)
        return result.scalars().all()

async def list_sessions() -> List[ConversationSession]:
    """List all conversation sessions, ordered by creation time."""
    async with SessionLocal() as session:
        stmt = select(ConversationSession).order_by(ConversationSession.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()

# Core message sending with plugin integration
async def send_message(
    session_id: int,
    user_message: str,
    model: Optional[str] = None,
    memory_limit: Optional[int] = None,
) -> str:
    """
    Send a user message to the LLM, handle function calls via plugins,
    save the conversation history, and return the assistant's reply.
    """
    model_name = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    if memory_limit is None:
        memory_limit = int(os.getenv("CONTEXT_MEMORY_MESSAGES", "0"))
    memory_limit = max(0, memory_limit)
    history: List[Dict[str, str]] = []
    if memory_limit:
        async with SessionLocal() as session:
            stmt = (
                select(Message)
                .where(Message.session_id != session_id)
                .order_by(Message.timestamp.desc())
                .limit(memory_limit)
            )
            result = await session.execute(stmt)
            other_msgs = list(result.scalars())
        for msg in reversed(other_msgs):
            history.append({"role": msg.role, "content": msg.content})
    msgs = await get_messages(session_id)
    for msg in msgs:
        history.append({"role": msg.role, "content": msg.content})
    history.append({"role": "user", "content": user_message})
    plugin_manager = await _ensure_plugins_ready()
    functions_spec = plugin_manager.function_specs() or None
    response = await client.chat.completions.create(
        model=model_name,
        messages=history,
        functions=functions_spec,
    )
    choice = response.choices[0].message
    assistant_msg: Optional[str]
    function_call = None
    if isinstance(choice, dict):
        assistant_msg = choice.get("content")
        function_call = choice.get("function_call")
    else:
        assistant_msg = getattr(choice, "content", None)
        function_call = getattr(choice, "function_call", None)
    if function_call:
        name = function_call.get("name") if isinstance(function_call, dict) else function_call.name
        args_json = function_call.get("arguments") if isinstance(function_call, dict) else function_call.arguments
        import json
        try:
            parsed = json.loads(args_json) if isinstance(args_json, str) else args_json
        except json.JSONDecodeError:
            parsed = {}
        result = await plugin_manager.call_function(name, parsed or {})
        history.append({"role": "function", "name": name, "content": str(result)})
        assistant_msg = str(result)
    usage = getattr(response, "usage", None)
    if usage:
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0))
        completion_tokens = int(getattr(usage, "completion_tokens", 0))
        record_usage(model_name, prompt_tokens, completion_tokens)
    assistant_msg = assistant_msg or ""
    async with SessionLocal() as session:
        session.add(Message(session_id=session_id, role="user", content=user_message))
        bot = Message(session_id=session_id, role="assistant", content=assistant_msg)
        session.add(bot)
        await session.commit()
    await _notify(session_id, bot)
    return assistant_msg

async def push_message(
    session_id: int,
    content: str,
    role: str = "assistant",
) -> Message:
    """
    Insert a message into the session and notify subscribers.
    """
    await init_db()
    async with SessionLocal() as session:
        msg = Message(session_id=session_id, role=role, content=content)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
    await _notify(session_id, msg)
    return msg