"""
Database models for Nagatha Assistant chat sessions.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from nagatha_assistant.db import Base


class ConversationSession(Base):
    """
    Represents a chat session with the AI model.
    """
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """
    Represents a single message in a conversation session.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ConversationSession", back_populates="messages")