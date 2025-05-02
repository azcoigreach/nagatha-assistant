"""
Chat session management: start sessions, send messages via OpenAI, and persist history.
"""
import os
import openai
from dotenv import load_dotenv
from typing import List, Dict
from sqlalchemy import select

from sqlalchemy import select
from nagatha_assistant.db import engine, SessionLocal
from nagatha_assistant.db_models import ConversationSession, Message

load_dotenv()

async def init_db() -> None:
    """
    Initialize database schema (create tables).
    """
    async with engine.begin() as conn:
        # import Base here to ensure metadata includes models
        from nagatha_assistant.db import Base

        await conn.run_sync(Base.metadata.create_all)

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

async def send_message(
    session_id: int,
    user_message: str,
    model: str = None
) -> str:
    """
    Send a user message to the OpenAI ChatCompletion API, store the user and assistant messages,
    and return the assistant's reply.
    """
    # Prepare model and API key
    model_name = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Load history
    history = []
    messages = await get_messages(session_id)
    for msg in messages:
        history.append({"role": msg.role, "content": msg.content})

    # Append user message
    history.append({"role": "user", "content": user_message})

    # Call OpenAI
    response = await openai.ChatCompletion.acreate(
        model=model_name,
        messages=history
    )
    # Extract assistant reply
    assistant_msg = response.choices[0].message["content"]

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