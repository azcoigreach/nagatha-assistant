"""
Chat session management: start sessions, send messages via OpenAI, and persist history.
"""
# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
import asyncio
from typing import List, Optional

# Third-party (optional) -----------------------------------------------------
# ``python-dotenv`` is a developer convenience; silently ignore if missing so
# production environments without the package still run.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ModuleNotFoundError:
    pass
from sqlalchemy import select
from openai import AsyncOpenAI
from nagatha_assistant.db import SessionLocal, ensure_schema
from nagatha_assistant.db_models import ConversationSession, Message
from nagatha_assistant.utils.usage_tracker import record_usage

# ------------------------------------------------------------------
# Plugin system
# ------------------------------------------------------------------
from nagatha_assistant.core.plugin import PluginManager


# Global plugin manager instance – lazy initialisation
_plugin_manager: PluginManager | None = None


async def _ensure_plugins_ready() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        # Make sure logging is configured so plugin discovery emits records.
        from nagatha_assistant.utils.logger import setup_logger

        setup_logger()

        _plugin_manager = PluginManager()
        await _plugin_manager.discover()
        await _plugin_manager.setup_all({})  # No config for now
    return _plugin_manager

# Instantiate a single AsyncOpenAI client
client = AsyncOpenAI()

async def init_db() -> None:
    """
    Initialize database schema (create tables).
    """
    # Use Alembic-driven migrations
    await ensure_schema()

async def start_session() -> int:
    """
    Create a new conversation session and return its ID.
    """
    await init_db()
    async with SessionLocal() as session:
        new_session = ConversationSession()
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)
        return new_session.id

async def get_messages(session_id: int) -> List[Message]:  # noqa
    """
    Retrieve all messages for a session, ordered by timestamp.
    """
    """
    Retrieve all messages for a session, ordered by timestamp.
    """
    async with SessionLocal() as session:
        # Query messages directly to avoid lazy-loading issues
        stmt = select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
        result = await session.execute(stmt)
        return result.scalars().all()

async def list_sessions() -> List[ConversationSession]:  # noqa
    """
    List all conversation sessions, ordered by creation time.
    """
    async with SessionLocal() as session:
        stmt = select(ConversationSession).order_by(ConversationSession.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()

# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------
# ``memory_limit`` controls how many messages from *other* sessions are fed to
# the model in addition to the current session history.  This gives Nagatha a
# configurable long-term memory while preventing the prompt from growing
# without bound.
#
# The precedence order for determining the limit is:
#   1. Explicit ``memory_limit`` argument (CLI option, UI parameter, etc.)
#   2. ``CONTEXT_MEMORY_MESSAGES`` environment variable (integer)
#   3. Default: 0 (no cross-session context)


async def send_message(
    session_id: int,
    user_message: str,
    model: str | None = None,
    memory_limit: Optional[int] = None,
) -> str:
    """
    Send a user message to the OpenAI ChatCompletion API, optionally augmenting
    the prompt with a configurable number of messages from *other* sessions.
    All user/assistant messages are persisted and the assistant's reply is
    returned.
    """
    # Prepare model name
    model_name = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # Determine cross-session memory to include
    if memory_limit is None:
        memory_limit = int(os.getenv("CONTEXT_MEMORY_MESSAGES", "0"))
    memory_limit = max(memory_limit, 0)

    # ------------------------------------------------------------------
    # Collect context
    # ------------------------------------------------------------------
    history: list[dict[str, str]] = []

    # 1. Optional cross-session context (oldest first)
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
        # We queried newest first; reverse to chronological order
        for msg in reversed(other_msgs):
            history.append({"role": msg.role, "content": msg.content})

    # 2. Current session history (already ordered asc.)
    messages = await get_messages(session_id)
    for msg in messages:
        history.append({"role": msg.role, "content": msg.content})

    # 3. Append the new user message
    history.append({"role": "user", "content": user_message})

    # --------------------------------------------------------------
    # Plugin function-calling integration
    # --------------------------------------------------------------
    plugin_manager = await _ensure_plugins_ready()
    functions_spec = plugin_manager.function_specs()

    # Call OpenAI via AsyncOpenAI client, advertising tool specs if any
    response = await client.chat.completions.create(
        model=model_name,
        messages=history,
        functions=functions_spec or None,
    )
    # Extract assistant reply (handle both dict and resource objects)
    choice_msg = response.choices[0].message

    # If the assistant decided to call a function we handle it here
    function_call = None
    if isinstance(choice_msg, dict):  # mock dicts
        assistant_msg = choice_msg.get("content")
        function_call = choice_msg.get("function_call")
    else:
        assistant_msg = getattr(choice_msg, "content", None)
        function_call = getattr(choice_msg, "function_call", None)

    # Execute plugin function if requested
    if function_call:
        fn_name = function_call["name"] if isinstance(function_call, dict) else function_call.name
        args_json = function_call["arguments"] if isinstance(function_call, dict) else function_call.arguments
        import json

        try:
            parsed_args = json.loads(args_json) if isinstance(args_json, str) else args_json
        except json.JSONDecodeError:
            parsed_args = {}

        result = await plugin_manager.call_function(fn_name, parsed_args or {})

        # Record function call and its result as messages for transparency
        history.append({"role": "function", "name": fn_name, "content": str(result)})

        # Optionally: make a follow-up call so model can use the result, but
        # to keep this simple we just treat *result* as the assistant’s reply.
        assistant_msg = str(result)

    # ------------------------------------------------------------------
    # Usage tracking (tokens & cost)
    # ------------------------------------------------------------------
    usage = getattr(response, "usage", None)
    if usage:  # OpenAI returns this when billing is enabled
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0))
        completion_tokens = int(getattr(usage, "completion_tokens", 0))
        record_usage(model_name, prompt_tokens, completion_tokens)

    # Use empty string if assistant_msg is None
    assistant_msg = assistant_msg or ""

    # Store messages
    async with SessionLocal() as session:
        # user message
        user_rec = Message(
            session_id=session_id, role="user", content=user_message
        )
        session.add(user_rec)
        # assistant message
        bot_rec = Message(
            session_id=session_id, role="assistant", content=assistant_msg
        )
        session.add(bot_rec)
        await session.commit()

    return assistant_msg