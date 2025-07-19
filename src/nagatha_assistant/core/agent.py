import os
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable
import openai
from openai import AsyncOpenAI

from sqlalchemy import select

from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import ConversationSession, Message
from nagatha_assistant.utils.usage_tracker import record_usage
from nagatha_assistant.utils.logger import setup_logger_with_env_control, should_log_to_chat
from nagatha_assistant.core.mcp_manager import get_mcp_manager, shutdown_mcp_manager
from nagatha_assistant.core.personality import get_system_prompt
from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import (
    StandardEventTypes, create_system_event, create_agent_event, EventPriority
)

# OpenAI client for conversations with timeout configuration
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))  # 60 seconds for tool-heavy requests
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=OPENAI_TIMEOUT
)

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

async def startup() -> Dict[str, Any]:
    """
    Initialize the application and return initialization status.
    Returns summary of MCP server connections for error reporting.
    """
    # Setup enhanced logging
    logger = setup_logger_with_env_control()
    
    # Start the event bus
    event_bus = get_event_bus()
    await event_bus.start()
    
    # Publish system startup event
    startup_event = create_system_event(
        StandardEventTypes.SYSTEM_STARTUP,
        {"timestamp": asyncio.get_event_loop().time()},
        EventPriority.HIGH
    )
    await event_bus.publish(startup_event)
    
    await init_db()
    
    # Initialize MCP manager and get initialization summary
    mcp_manager = await get_mcp_manager()
    init_summary = mcp_manager.get_initialization_summary()
    
    # Log initialization results
    if init_summary["connected"] > 0:
        logger.info(f"Startup complete: {init_summary['connected']}/{init_summary['total_configured']} MCP servers connected")
    else:
        logger.warning(f"Startup complete but no MCP servers connected ({init_summary['total_configured']} configured)")
    
    return init_summary

async def shutdown() -> None:
    """Clean up application resources."""
    # Get event bus and publish shutdown event
    event_bus = get_event_bus()
    if event_bus._running:
        shutdown_event = create_system_event(
            StandardEventTypes.SYSTEM_SHUTDOWN,
            {"timestamp": asyncio.get_event_loop().time()},
            EventPriority.HIGH
        )
        await event_bus.publish(shutdown_event)
    
    await shutdown_mcp_manager()
    
    # Stop the event bus
    await event_bus.stop()

async def start_session() -> int:
    """Create a new conversation session and return its ID."""
    await init_db()
    # Ensure MCP is initialized
    await get_mcp_manager()
    
    async with SessionLocal() as session:
        new_session = ConversationSession()
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)
        session_id = new_session.id
        
        # Publish conversation started event
        event_bus = get_event_bus()
        if event_bus._running:
            conversation_event = create_agent_event(
                StandardEventTypes.AGENT_CONVERSATION_STARTED,
                session_id,
                {"session_created_at": new_session.created_at.isoformat() if new_session.created_at else None}
            )
            event_bus.publish_sync(conversation_event)
        
        return session_id

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

async def get_available_tools() -> List[Dict[str, Any]]:
    """Get list of all available MCP tools."""
    try:
        mcp_manager = await get_mcp_manager()
        return mcp_manager.get_available_tools()
    except Exception as e:
        logging.error(f"Error getting available tools: {e}")
        return []

async def get_mcp_status() -> Dict[str, Any]:
    """Get status information about MCP servers."""
    try:
        mcp_manager = await get_mcp_manager()
        return {
            "servers": mcp_manager.get_server_info(),
            "tools": mcp_manager.get_available_tools(),
            "initialized": mcp_manager._initialized,
            "summary": mcp_manager.get_initialization_summary()
        }
    except Exception as e:
        logging.error(f"Error getting MCP status: {e}")
        return {"error": str(e), "servers": {}, "tools": [], "initialized": False}

async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call an MCP tool and return the result."""
    try:
        mcp_manager = await get_mcp_manager()
        return await mcp_manager.call_tool(tool_name, arguments)
    except Exception as e:
        logging.error(f"Error calling MCP tool '{tool_name}': {e}")
        raise

def format_mcp_status_for_chat(init_summary: Dict[str, Any]) -> str:
    """Format MCP initialization status for display in chat."""
    messages = []
    
    if init_summary["connected"] > 0:
        messages.append(f"✅ Connected to {init_summary['connected']}/{init_summary['total_configured']} MCP servers")
        messages.append(f"🔧 {init_summary['total_tools']} tools available")
        
        if init_summary["connected_servers"]:
            messages.append(f"Connected servers: {', '.join(init_summary['connected_servers'])}")
    else:
        messages.append("⚠️ No MCP servers connected")
    
    if init_summary["failed"]:
        messages.append(f"❌ {init_summary['failed']} server(s) failed to connect:")
        for server_name, error in init_summary["failed_servers"]:
            messages.append(f"  • {server_name}: {error}")
    
    return "\n".join(messages)

async def send_message(
    session_id: int,
    user_message: str,
    model: str = None,
    tool_name: Optional[str] = None,
    tool_args: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Send a user message and get Nagatha's response.
    
    This function handles both direct tool calls and intelligent conversation
    that may involve using MCP tools when appropriate.
    """
    logger = setup_logger_with_env_control()

    if not model:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Save user message
    async with SessionLocal() as session:
        user_msg = Message(session_id=session_id, role="user", content=user_message)
        session.add(user_msg)
        await session.commit()
        await session.refresh(user_msg)
    
    # Publish user message received event
    event_bus = get_event_bus()
    if event_bus._running:
        message_event = create_agent_event(
            StandardEventTypes.AGENT_MESSAGE_RECEIVED,
            session_id,
            {
                "message_id": user_msg.id,
                "role": "user",
                "content": user_message[:100] + "..." if len(user_message) > 100 else user_message,
                "timestamp": user_msg.timestamp.isoformat() if user_msg.timestamp else None
            }
        )
        event_bus.publish_sync(message_event)

    # If a specific tool is requested, call it directly
    if tool_name:
        try:
            tool_args = tool_args or {}
            logger.info(f"Direct tool call: '{tool_name}' with args: {tool_args}")
            result = await call_mcp_tool(tool_name, tool_args)
            assistant_msg = f"Tool '{tool_name}' result:\n{result}"
        except Exception as e:
            logger.exception(f"Error calling MCP tool '{tool_name}'")
            assistant_msg = f"Error calling tool '{tool_name}': {e}"
    else:
        # Use Nagatha's intelligent conversation system
        try:
            # Get conversation history
            messages = await get_messages(session_id)
            conversation_history = []
            
            # Get available tools and create system prompt
            available_tools = await get_available_tools()
            system_prompt = get_system_prompt(available_tools)
            conversation_history.append({"role": "system", "content": system_prompt})
            
            # Add message history (excluding the latest user message which we already have)
            for msg in messages[:-1]:  # Exclude the last message we just saved
                conversation_history.append({"role": msg.role, "content": msg.content})
            
            # Add the current user message
            conversation_history.append({"role": "user", "content": user_message})

            # Call OpenAI with function calling for tool use
            tools = None
            if available_tools:
                # Convert MCP tools to OpenAI function format
                tools = []
                for tool in available_tools:
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"]
                        }
                    }
                    
                    # Add schema if available
                    if tool.get("schema"):
                        tool_def["function"]["parameters"] = tool["schema"]
                    else:
                        # Default schema for tools without one
                        tool_def["function"]["parameters"] = {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    
                    tools.append(tool_def)

            # Make the OpenAI call
            call_params = {
                "model": model,
                "messages": conversation_history
            }
            
            if tools:
                call_params["tools"] = tools
                call_params["tool_choice"] = "auto"

            response = await client.chat.completions.create(**call_params)
            
            assistant_msg = ""
            
            # Handle tool calls if any
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                tool_calls = response.choices[0].message.tool_calls
                
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        import json
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    try:
                        logger.info(f"LLM requested tool call: '{tool_name}' with args: {tool_args}")
                        tool_result = await call_mcp_tool(tool_name, tool_args)
                        assistant_msg += f"I used the {tool_name} tool and here's what I found:\n\n{tool_result}\n\n"
                    except Exception as e:
                        logger.error(f"Error in tool call '{tool_name}': {e}")
                        assistant_msg += f"I tried to use the {tool_name} tool but encountered an error: {e}\n\n"
                
                # If we made tool calls, get a follow-up response from the LLM
                if assistant_msg:
                    # Add tool results to conversation and get final response
                    conversation_history.append({
                        "role": "assistant", 
                        "content": f"I've gathered some information using my tools:\n\n{assistant_msg}"
                    })
                    conversation_history.append({
                        "role": "user", 
                        "content": "Please provide a comprehensive response based on the tool results."
                    })
                    
                    final_response = await client.chat.completions.create(
                        model=model,
                        messages=conversation_history
                    )
                    
                    assistant_msg = final_response.choices[0].message.content
            else:
                # No tool calls, just use the direct response
                assistant_msg = response.choices[0].message.content
            
            # Record usage
            if hasattr(response, 'usage') and response.usage:
                record_usage(
                    model=model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            
        except Exception as e:
            logger.exception("Error in conversation processing")
            assistant_msg = f"I encountered an error while processing your request: {e}"

    # Save assistant reply
    async with SessionLocal() as session:
        bot = Message(session_id=session_id, role="assistant", content=assistant_msg)
        session.add(bot)
        await session.commit()
        await session.refresh(bot)

    # Notify subscribers
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
    
    # Publish message event
    event_bus = get_event_bus()
    if event_bus._running:
        event_type = (StandardEventTypes.AGENT_MESSAGE_SENT 
                     if role == "assistant" 
                     else StandardEventTypes.AGENT_MESSAGE_RECEIVED)
        message_event = create_agent_event(
            event_type,
            session_id,
            {
                "message_id": msg.id,
                "role": role,
                "content": content[:100] + "..." if len(content) > 100 else content,  # Truncate for events
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            }
        )
        event_bus.publish_sync(message_event)
    
    await _notify(session_id, msg)
    return msg

async def push_system_message(session_id: int, content: str) -> Message:
    """Push a system message to the chat session."""
    return await push_message(session_id, content, role="system")