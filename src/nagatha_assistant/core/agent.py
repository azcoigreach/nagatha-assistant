import os
import asyncio
import json
from typing import Any, Dict, List, Optional, Callable, Awaitable
import openai
from openai import AsyncOpenAI

from sqlalchemy import select

from nagatha_assistant.db import ensure_schema, SessionLocal
from nagatha_assistant.db_models import ConversationSession, Message
from nagatha_assistant.utils.usage_tracker import record_usage
from nagatha_assistant.utils.logger import setup_logger_with_env_control, should_log_to_chat, get_logger
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

# Background task for autonomous memory maintenance
_memory_maintenance_task: Optional[asyncio.Task] = None

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
            logger = get_logger()
            logger.exception("Error in push callback for session %s", session_id)

# Database initialization and session handling
async def init_db() -> None:
    """Ensure the database schema is up-to-date."""
    await ensure_schema()


async def _autonomous_memory_maintenance_loop() -> None:
    """Background task for autonomous memory maintenance."""
    logger = get_logger()
    
    while True:
        try:
            # Wait 1 hour between maintenance cycles
            await asyncio.sleep(3600)
            
            from .memory import get_memory_maintenance
            memory_maintenance = get_memory_maintenance()
            
            # Perform maintenance
            results = await memory_maintenance.perform_maintenance()
            
            if any(results.values()):
                logger.info(f"Memory maintenance completed: {results}")
            else:
                logger.debug("Memory maintenance completed: no actions needed")
                
        except asyncio.CancelledError:
            logger.info("Memory maintenance loop cancelled")
            break
        except Exception as e:
            logger.exception(f"Error in memory maintenance loop: {e}")
            # Wait before retrying on error
            await asyncio.sleep(300)  # 5 minutes


async def startup() -> Dict[str, Any]:
    """
    Initialize the application and return initialization status.
    Returns summary of MCP server connections for error reporting.
    """
    # Setup enhanced logging
    logger = get_logger()
    
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
    
    # Initialize memory manager
    try:
        from .memory import ensure_memory_manager_started
        await ensure_memory_manager_started()
        logger.info("Memory manager started")
        
        # Start autonomous memory maintenance task (only in production)
        if not os.getenv("TESTING"):
            global _memory_maintenance_task
            _memory_maintenance_task = asyncio.create_task(_autonomous_memory_maintenance_loop())
            logger.info("Autonomous memory maintenance started")
        
    except Exception as e:
        logger.exception(f"Error starting memory manager: {e}")
    
    # Initialize short-term memory system
    try:
        from .short_term_memory import ensure_short_term_memory_started
        await ensure_short_term_memory_started()
        logger.info("Short-term memory system started")
    except Exception as e:
        logger.warning(f"Failed to start short-term memory system: {e}")
    
    # Initialize MCP manager and get initialization summary
    mcp_manager = await get_mcp_manager()
    init_summary = mcp_manager.get_initialization_summary()
    
    # Initialize plugin manager and load plugins
    try:
        from .plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        plugin_results = await plugin_manager.load_and_start_all()
        logger.info(f"Loaded {len([r for r in plugin_results.values() if r])}/{len(plugin_results)} plugins")
    except Exception as e:
        logger.exception(f"Error initializing plugins: {e}")
    
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
    
    # Shutdown plugin manager
    try:
        from .plugin_manager import shutdown_plugin_manager
        await shutdown_plugin_manager()
    except Exception as e:
        logger = get_logger()
        logger.exception(f"Error shutting down plugins: {e}")
    
    # Cancel memory maintenance task (only if it exists)
    global _memory_maintenance_task
    if _memory_maintenance_task and not _memory_maintenance_task.done():
        _memory_maintenance_task.cancel()
        try:
            await _memory_maintenance_task
        except asyncio.CancelledError:
            pass
        logger = get_logger()
        logger.info("Memory maintenance task cancelled")
    
    # Shutdown short-term memory system
    try:
        from .short_term_memory import shutdown_short_term_memory
        await shutdown_short_term_memory()
        logger = get_logger()
        logger.info("Short-term memory system stopped")
    except Exception as e:
        logger = get_logger()
        logger.exception(f"Error shutting down short-term memory: {e}")
    
    # Shutdown memory manager
    try:
        from .memory import shutdown_memory_manager
        await shutdown_memory_manager()
    except Exception as e:
        logger = get_logger()
        logger.exception(f"Error shutting down memory manager: {e}")
    
    await shutdown_mcp_manager()
    
    # Stop the event bus
    if event_bus._running:
        await event_bus.stop()
    
    logger = get_logger()
    logger.info("Application shutdown complete")

async def start_session() -> int:
    """Create a new conversation session and return its ID."""
    logger = get_logger()
    await init_db()
    # Ensure MCP is initialized
    await get_mcp_manager()
    
    # Ensure memory manager is started
    try:
        from .memory import ensure_memory_manager_started
        await ensure_memory_manager_started()
    except Exception as e:
        logger = get_logger()
        logger.exception(f"Error ensuring memory manager is started: {e}")
    
    # Ensure plugins are initialized
    try:
        from .plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        if not plugin_manager._plugins:  # Only load if not already loaded
            await plugin_manager.load_and_start_all()
    except Exception as e:
        logger = get_logger()
        logger.exception(f"Error ensuring plugins are loaded: {e}")
    
    async with SessionLocal() as session:
        new_session = ConversationSession()
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)
        session_id = new_session.id
        
        # Load startup memories and create welcome message
        try:
            from .memory import get_contextual_recall
            contextual_recall = get_contextual_recall()
            
            # Get user's name and startup memories
            user_name = await contextual_recall.get_user_name()
            startup_memories = await contextual_recall.get_session_startup_memories(session_id)
            
            # Create welcome message with context
            welcome_message = "Hello! I'm Nagatha, your AI assistant. "
            
            if user_name:
                welcome_message += f"Welcome back, {user_name}! "
            
            # Add context from startup memories
            context_items = []
            if startup_memories.get("user_preferences"):
                context_items.append("I remember your preferences")
            
            if startup_memories.get("personality"):
                context_items.append("I'll adapt to your communication style")
            
            if startup_memories.get("facts"):
                context_items.append("I have some relevant context from our previous conversations")
            
            if context_items:
                welcome_message += " ".join(context_items) + ". "
            
            welcome_message += "How can I help you today?"
            
            # Add the welcome message to the session
            welcome_msg = Message(session_id=session_id, role="assistant", content=welcome_message)
            session.add(welcome_msg)
            await session.commit()
            
            logger.info(f"Session {session_id} started with welcome message for user: {user_name or 'Unknown'}")
            
        except Exception as e:
            logger.warning(f"Error creating welcome message for session {session_id}: {e}")
            # Fallback welcome message
            welcome_msg = Message(session_id=session_id, role="assistant", content="Hello! I'm Nagatha, your AI assistant. How can I help you today?")
            session.add(welcome_msg)
            await session.commit()
        
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
    """Get list of all available MCP tools and plugin commands."""
    tools = []
    
    # Get MCP tools
    try:
        mcp_manager = await get_mcp_manager()
        mcp_tools = mcp_manager.get_available_tools()
        tools.extend(mcp_tools)
    except Exception as e:
        logger = get_logger()
        logger.error(f"Error getting MCP tools: {e}")
    
    # Get plugin commands
    try:
        from .plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        plugin_commands = plugin_manager.get_available_commands()
        
        # Convert plugin commands to tool format
        for cmd_name, cmd_info in plugin_commands.items():
            tools.append({
                "name": cmd_name,
                "description": cmd_info["description"],
                "schema": cmd_info.get("parameters", {
                    "type": "object",
                    "properties": {},
                    "required": []
                }),
                "server": f"plugin:{cmd_info['plugin']}"
            })
    except Exception as e:
        logger = get_logger()
        logger.error(f"Error getting plugin commands: {e}")
    
    return tools

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
        logger = get_logger()
        logger.error(f"Error getting MCP status: {e}")
        return {"error": str(e), "servers": {}, "tools": [], "initialized": False}

async def reload_mcp_configuration() -> Dict[str, Any]:
    """Reload MCP configuration and return updated status."""
    try:
        mcp_manager = await get_mcp_manager()
        await mcp_manager.reload_configuration()
        return await get_mcp_status()
    except Exception as e:
        logger = get_logger()
        logger.error(f"Error reloading MCP configuration: {e}")
        return {"error": str(e), "servers": {}, "tools": [], "initialized": False}

async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call an MCP tool and return the result."""
    try:
        mcp_manager = await get_mcp_manager()
        return await mcp_manager.call_tool(tool_name, arguments)
    except Exception as e:
        logger = get_logger()
        logger.error(f"Error calling MCP tool '{tool_name}': {e}")
        raise


async def call_plugin_command(command_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a plugin command and return the result."""
    try:
        from .plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        return await plugin_manager.execute_command(command_name, **arguments)
    except Exception as e:
        logger = get_logger()
        logger.error(f"Error calling plugin command '{command_name}': {e}")
        raise


async def call_tool_or_command(name: str, arguments: Dict[str, Any]) -> Any:
    """
    Call either an MCP tool or plugin command by name.
    
    For memory operations, prefer plugin commands over MCP tools.
    For other operations, try MCP tools first, then plugin commands.
    Handles json import errors gracefully with fallback implementations.
    """
    logger = get_logger()
    
    # For memory operations, try plugin command first
    if "memory" in name.lower():
        try:
            return await call_plugin_command(name, arguments)
        except Exception as plugin_error:
            logger.warning(f"Plugin command '{name}' failed, trying MCP tool: {plugin_error}")
            try:
                return await call_mcp_tool(name, arguments)
            except Exception as mcp_error:
                logger.error(f"Both plugin command and MCP tool failed for '{name}': {mcp_error}")
                raise RuntimeError(f"Memory operation '{name}' is currently unavailable. Please try again later.")
    
    # For other operations, try MCP tool first
    try:
        return await call_mcp_tool(name, arguments)
    except Exception as e:
        error_msg = str(e)
        
        # Handle json import errors in external MCP servers
        if "json is not defined" in error_msg:
            logger.warning(f"External MCP server json error for tool '{name}': {error_msg}")
            
            # Provide fallback implementations for common tools
            if "firecrawl" in name.lower():
                return await _fallback_web_search(name, arguments)
            else:
                # For other tools, try plugin command as fallback
                try:
                    return await call_plugin_command(name, arguments)
                except Exception as plugin_error:
                    logger.error(f"Both MCP tool and plugin command failed for '{name}': {plugin_error}")
                    raise RuntimeError(f"Tool '{name}' is currently unavailable due to external server issues. Please try again later.")
        
        # For other errors, try plugin command as fallback
        try:
            return await call_plugin_command(name, arguments)
        except Exception as plugin_error:
            logger.error(f"Error calling tool/command '{name}': {e}")
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

async def _fallback_web_search(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Fallback implementation for web search when external MCP server fails."""
    logger = get_logger()
    logger.info(f"Using fallback web search for '{tool_name}' with args: {arguments}")
    
    # Extract search query from arguments
    query = arguments.get("query", "")
    if not query:
        return "No search query provided."
    
    try:
        # Simple fallback: return a message about the search
        return f"I would search for '{query}' but the web search service is temporarily unavailable. Please try again later or ask me something else."
    except Exception as e:
        logger.error(f"Fallback web search failed: {e}")
        return "Web search is currently unavailable. Please try again later."


async def _fallback_memory_operation(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Fallback implementation for memory operations when external MCP server fails."""
    logger = get_logger()
    logger.info(f"Using fallback memory operation for '{tool_name}' with args: {arguments}")
    
    try:
        # Try to use the plugin command as fallback
        return await call_plugin_command(tool_name, arguments)
    except Exception as e:
        logger.error(f"Fallback memory operation failed: {e}")
        return f"Memory operation '{tool_name}' is temporarily unavailable. Please try again later."


def _select_relevant_tools(available_tools: List[Dict[str, Any]], user_message: str, max_tools: int = 125) -> List[Dict[str, Any]]:
    """
    Select the most relevant tools for a user message, respecting OpenAI's tool limit.
    
    Args:
        available_tools: All available MCP tools
        user_message: The user's message to analyze for relevance
        max_tools: Maximum number of tools to return (default 125 to stay under 128 limit)
    
    Returns:
        Filtered list of tools, prioritized by relevance
    """
    if len(available_tools) <= max_tools:
        return available_tools
    
    # Keywords that suggest specific tool categories
    web_keywords = ['search', 'web', 'website', 'url', 'scrape', 'crawl', 'online', 'internet', 'browse']
    file_keywords = ['file', 'read', 'write', 'directory', 'folder', 'save', 'load', 'path']
    code_keywords = ['python', 'code', 'script', 'execute', 'run', 'programming', 'function']
    github_keywords = ['github', 'git', 'repository', 'repo', 'issue', 'pull request', 'commit']
    memory_keywords = ['remember', 'recall', 'memory', 'knowledge', 'graph', 'entity', 'relationship']
    time_keywords = ['time', 'date', 'calendar', 'schedule', 'when', 'today', 'tomorrow']
    thinking_keywords = ['think', 'analyze', 'reason', 'consider', 'evaluate', 'step by step']
    
    # Categorize tools by type
    priority_tools = []
    web_tools = []
    file_tools = []
    code_tools = []
    github_tools = []
    memory_tools = []
    time_tools = []
    thinking_tools = []
    other_tools = []
    
    user_lower = user_message.lower()
    
    for tool in available_tools:
        tool_name = tool['name'].lower()
        tool_desc = tool.get('description', '').lower()
        server_name = tool.get('server', '').lower()
        
        # Check for keyword matches in user message
        has_web_match = any(kw in user_lower for kw in web_keywords)
        has_file_match = any(kw in user_lower for kw in file_keywords)
        has_code_match = any(kw in user_lower for kw in code_keywords)
        has_github_match = any(kw in user_lower for kw in github_keywords)
        has_memory_match = any(kw in user_lower for kw in memory_keywords)
        has_time_match = any(kw in user_lower for kw in time_keywords)
        has_thinking_match = any(kw in user_lower for kw in thinking_keywords)
        
        # Categorize tools
        if any(kw in tool_name or kw in tool_desc for kw in web_keywords) or 'firecrawl' in server_name:
            if has_web_match:
                priority_tools.append(tool)
            else:
                web_tools.append(tool)
        elif any(kw in tool_name or kw in tool_desc for kw in file_keywords) or 'filesystem' in server_name:
            if has_file_match:
                priority_tools.append(tool)
            else:
                file_tools.append(tool)
        elif any(kw in tool_name or kw in tool_desc for kw in code_keywords):
            if has_code_match:
                priority_tools.append(tool)
            else:
                code_tools.append(tool)
        elif any(kw in tool_name or kw in tool_desc for kw in github_keywords) or 'github' in server_name:
            if has_github_match:
                priority_tools.append(tool)
            else:
                github_tools.append(tool)
        elif any(kw in tool_name or kw in tool_desc for kw in memory_keywords) or 'memory' in server_name:
            if has_memory_match:
                priority_tools.append(tool)
            else:
                memory_tools.append(tool)
        elif any(kw in tool_name or kw in tool_desc for kw in time_keywords) or 'time' in server_name:
            if has_time_match:
                priority_tools.append(tool)
            else:
                time_tools.append(tool)
        elif any(kw in tool_name or kw in tool_desc for kw in thinking_keywords) or 'sequential-thinking' in server_name:
            if has_thinking_match:
                priority_tools.append(tool)
            else:
                thinking_tools.append(tool)
        else:
            other_tools.append(tool)
    
    # Build final tool list prioritizing matched categories
    selected_tools = []
    
    # Always include priority tools (directly matched to user intent)
    selected_tools.extend(priority_tools)
    
    # Add tools from categories based on user message content
    remaining_slots = max_tools - len(selected_tools)
    if remaining_slots > 0:
        # Distribute remaining slots across relevant categories
        categories = []
        if any(kw in user_lower for kw in web_keywords):
            categories.extend(web_tools)
        if any(kw in user_lower for kw in file_keywords):
            categories.extend(file_tools)
        if any(kw in user_lower for kw in code_keywords):
            categories.extend(code_tools)
        if any(kw in user_lower for kw in github_keywords):
            categories.extend(github_tools)
        if any(kw in user_lower for kw in memory_keywords):
            categories.extend(memory_tools)
        if any(kw in user_lower for kw in time_keywords):
            categories.extend(time_tools)
        if any(kw in user_lower for kw in thinking_keywords):
            categories.extend(thinking_tools)
        
        # If no specific category matches, include a balanced mix
        if not categories:
            # Include most useful general tools
            categories = (web_tools[:3] + file_tools[:3] + memory_tools[:3] + 
                         thinking_tools[:2] + code_tools[:2] + time_tools[:1] + other_tools)
        
        selected_tools.extend(categories[:remaining_slots])
    
    logger = get_logger()
    logger.info(f"Tool selection: {len(available_tools)} available, {len(selected_tools)} selected for user message")
    return selected_tools

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
    logger = get_logger()

    if not model:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Save user message
    async with SessionLocal() as session:
        user_msg = Message(session_id=session_id, role="user", content=user_message)
        session.add(user_msg)
        await session.commit()
        await session.refresh(user_msg)
    
    # Add to conversation context for short-term memory
    try:
        from .memory import get_memory_manager
        memory_manager = get_memory_manager()
        await memory_manager.add_conversation_context(
            session_id, user_msg.id, "user", user_message
        )
    except Exception as e:
        logger.warning(f"Failed to add user message to conversation context: {e}")
    
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

    # Autonomous memory processing for user message
    try:
        from .memory import get_memory_trigger, get_contextual_recall, get_personality_memory
        
        # Analyze user message for autonomous storage
        memory_trigger = get_memory_trigger()
        context = {"session_id": session_id, "message_id": user_msg.id}
        
        storage_analysis = await memory_trigger.analyze_for_storage(user_message, context)
        
        if storage_analysis["should_store"]:
            logger.debug(f"Autonomous memory: storing {len(storage_analysis['entries'])} items from user message")
            
            # Store identified entries
            for entry in storage_analysis["entries"]:
                await memory_trigger.memory_manager.set(
                    section=entry["section"],
                    key=entry["key"],
                    value=entry["value"],
                    session_id=entry.get("session_id"),
                    ttl_seconds=entry.get("ttl_seconds")
                )
        else:
            logger.debug(f"Autonomous memory: not storing user message - {storage_analysis['reason']}")
    
    except Exception as e:
        logger.warning(f"Error in autonomous memory processing: {e}")

    # If a specific tool is requested, call it directly
    if tool_name:
        try:
            tool_args = tool_args or {}
            logger.info(f"Direct tool call: '{tool_name}' with args: {tool_args}")
            result = await call_tool_or_command(tool_name, tool_args)
            assistant_msg = f"Tool '{tool_name}' result:\n{result}"
        except Exception as e:
            logger.exception(f"Error calling tool/command '{tool_name}'")
            assistant_msg = f"Error calling tool '{tool_name}': {e}"
    else:
        # Use Nagatha's intelligent conversation system
        try:
            # Get conversation context from short-term memory first
            conversation_context = []
            try:
                from .memory import get_memory_manager
                memory_manager = get_memory_manager()
                context_entries = await memory_manager.get_conversation_context(session_id, limit=15)
                
                # Convert to conversation format
                for entry in context_entries:
                    value = entry.get("value", {})
                    conversation_context.append({
                        "role": value.get("role", "user"),
                        "content": value.get("content", "")
                    })
                
                # If we have recent context, use it instead of full database history
                if conversation_context:
                    logger.debug(f"Using {len(conversation_context)} recent conversation context entries")
                    logger.debug(f"Conversation context: {conversation_context}")
                else:
                    # Fallback to database messages
                    messages = await get_messages(session_id)
                    conversation_context = [
                        {"role": msg.role, "content": msg.content}
                        for msg in messages[-15:]  # Last 15 messages
                    ]
                    logger.debug(f"Using {len(conversation_context)} database messages as fallback")
                    logger.debug(f"Database conversation context: {conversation_context}")
                    
            except Exception as e:
                logger.warning(f"Error getting conversation context: {e}")
                # Fallback to database messages
                messages = await get_messages(session_id)
                conversation_context = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages[-15:]  # Last 15 messages
                ]
                logger.debug(f"Using {len(conversation_context)} database messages after error")
                logger.debug(f"Database conversation context: {conversation_context}")
            
            # Get available tools and create enhanced system prompt with memory context
            available_tools = await get_available_tools()
            
            # Enhanced system prompt with contextual memory and personality adaptation
            try:
                from .memory import get_contextual_recall, get_personality_memory
                
                contextual_recall = get_contextual_recall()
                personality_memory = get_personality_memory()
                
                # Get relevant memories based on user message context
                relevant_memories = await contextual_recall.get_relevant_memories(
                    user_message, session_id, max_results=5
                )
                
                # If no relevant memories found for the specific message, get startup memories
                if not any(relevant_memories.values()):
                    startup_memories = await contextual_recall.get_session_startup_memories(session_id, max_results=3)
                    # Convert startup memories to the same format as relevant memories
                    for section, memories in startup_memories.items():
                        if memories:
                            relevant_memories[section] = memories
                
                # Get personality adaptations
                personality_adaptations = await personality_memory.adapt_to_context(
                    user_message, session_id
                )
                
                # Create base system prompt
                base_system_prompt = get_system_prompt(available_tools)
                
                # Add conversation flow instructions
                conversation_instructions = """
                
## Conversation Guidelines:
- Always maintain natural conversation flow
- When asked about previous information, respond conversationally rather than just stating facts
- Use phrases like "Yes, I remember..." or "As you mentioned earlier..." to show continuity
- Keep responses engaging and conversational
- If you have context from previous messages, use it naturally in your responses
"""
                
                # Get user's name for context
                user_name = await contextual_recall.get_user_name()
                
                # Enhance with memory context
                memory_context = ""
                if user_name:
                    memory_context += f"\n\n## User Information:\n- **Name**: {user_name}\n"
                
                if any(relevant_memories.values()):
                    memory_context += "\n\n## Relevant Context from Our History:\n"
                    
                    for section, memories in relevant_memories.items():
                        if memories:
                            memory_context += f"\n**{section.replace('_', ' ').title()}:**\n"
                            for memory in memories[:3]:  # Limit to top 3 per section
                                if isinstance(memory.get("value"), dict):
                                    if "text" in memory["value"]:
                                        memory_context += f"- {memory['value']['text']}\n"
                                    elif "fact" in memory["value"]:
                                        memory_context += f"- {memory['value']['fact']}\n"
                                    elif "task" in memory["value"]:
                                        memory_context += f"- Current focus: {memory['value']['task']}\n"
                                    elif "preference" in memory["value"]:
                                        memory_context += f"- {memory['value']['preference']}\n"
                                    elif "style_type" in memory["value"]:
                                        memory_context += f"- Communication style: {memory['value']['style_type']}\n"
                
                # Enhance with personality adaptations
                if personality_adaptations:
                    personality_context = "\n\n## Interaction Guidance for This Context:\n"
                    personality_context += f"- **Tone**: {personality_adaptations.get('tone', 'warm and professional')}\n"
                    personality_context += f"- **Detail Level**: {personality_adaptations.get('detail_level', 'balanced')}\n"
                    
                    enhanced_system_prompt = base_system_prompt + conversation_instructions + memory_context + personality_context
                else:
                    enhanced_system_prompt = base_system_prompt + conversation_instructions + memory_context
                    
            except Exception as e:
                logger.warning(f"Error enhancing system prompt with memory context: {e}")
                enhanced_system_prompt = get_system_prompt(available_tools)
            
            conversation_history = [{"role": "system", "content": enhanced_system_prompt}]
            
            # Add conversation context (excluding the current user message which we'll add separately)
            logger.debug(f"Building conversation history with {len(conversation_context)} context messages")
            context_added = 0
            for msg in conversation_context:
                if msg["role"] != "user" or msg["content"] != user_message:
                    conversation_history.append(msg)
                    context_added += 1
                    logger.debug(f"Added context message: {msg['role']}: {msg['content'][:50]}...")
                else:
                    logger.debug(f"Skipped duplicate message: {msg['role']}: {msg['content'][:50]}...")
            
            # Add the current user message
            conversation_history.append({"role": "user", "content": user_message})
            logger.debug(f"Added current user message: {user_message[:50]}...")
            logger.debug(f"Final conversation history has {len(conversation_history)} messages ({context_added} context messages)")
            
            # Ensure we have at least some context for conversation flow
            if context_added == 0 and len(conversation_context) > 0:
                logger.warning("No conversation context was added - this may affect conversation flow")
                # Add the most recent context message anyway
                for msg in reversed(conversation_context):
                    if msg["role"] == "assistant":
                        conversation_history.insert(1, msg)  # Insert after system message
                        logger.debug(f"Added fallback context: {msg['role']}: {msg['content'][:50]}...")
                        break
            
            # Call OpenAI with function calling for tool use
            tools = None
            if available_tools:
                # Filter tools to respect OpenAI's 128 tool limit
                selected_tools = _select_relevant_tools(available_tools, user_message)
                
                # Convert selected MCP tools to OpenAI function format
                tools = []
                for tool in selected_tools:
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
                
                logger.info(f"Prepared {len(tools)} tools for OpenAI (filtered from {len(available_tools)} available)")
                tool_names = [tool['function']['name'] for tool in tools]
                logger.info(f"Tool names being sent to OpenAI: {tool_names}")
                print(f"DEBUG: Tool names being sent to OpenAI: {tool_names}")
            
            # Call OpenAI
            try:
                client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
                response = await client.chat.completions.create(
                    model=model,
                    messages=conversation_history,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                    temperature=0.7,
                    max_tokens=4000
                )
                
                assistant_msg = response.choices[0].message.content or ""
                
                # Handle tool calls if any
                if response.choices[0].message.tool_calls:
                    tool_calls = response.choices[0].message.tool_calls
                    logger.info(f"OpenAI requested {len(tool_calls)} tool calls")
                    
                    # Process tool calls
                    for tool_call in tool_calls:
                        try:
                            tool_name = tool_call.function.name
                            tool_args = json.loads(tool_call.function.arguments)
                            
                            logger.info(f"Calling tool: {tool_name} with args: {tool_args}")
                            result = await call_tool_or_command(tool_name, tool_args)
                            
                            # Add tool result to conversation
                            conversation_history.append({
                                "role": "assistant",
                                "content": assistant_msg,
                                "tool_calls": [tool_call.model_dump()]
                            })
                            
                            conversation_history.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(result)
                            })
                            
                            # Get final response from OpenAI
                            final_response = await client.chat.completions.create(
                                model=model,
                                messages=conversation_history,
                                temperature=0.7,
                                max_tokens=2000
                            )
                            
                            assistant_msg = final_response.choices[0].message.content or ""
                            
                        except Exception as e:
                            logger.exception(f"Error processing tool call {tool_call.function.name}: {e}")
                            error_msg = str(e)
                            
                            # Handle specific firecrawl errors
                            if "firecrawl" in tool_call.function.name.lower() and "json is not defined" in error_msg:
                                assistant_msg = f"⚠️ I'm having trouble with web search tools right now due to a technical issue. Please try again later or ask me something else!"
                            elif "memory" in tool_call.function.name.lower() and "json is not defined" in error_msg:
                                assistant_msg = f"⚠️ I'm having trouble with memory tools right now due to a technical issue. Please try again later!"
                            else:
                                assistant_msg = f"Error executing tool '{tool_call.function.name}': {e}"
                
            except Exception as e:
                logger.exception(f"Error calling OpenAI: {e}")
                assistant_msg = f"I encountered an error while processing your request: {e}"
            
        except Exception as e:
            logger.exception("Error in conversation processing")
            assistant_msg = f"I encountered an error while processing your request: {e}"

    # Save assistant reply
    async with SessionLocal() as session:
        bot = Message(session_id=session_id, role="assistant", content=assistant_msg)
        session.add(bot)
        await session.commit()
        await session.refresh(bot)
    
    # Add assistant response to conversation context
    try:
        from .memory import get_memory_manager
        memory_manager = get_memory_manager()
        await memory_manager.add_conversation_context(
            session_id, bot.id, "assistant", assistant_msg
        )
    except Exception as e:
        logger.warning(f"Failed to add assistant message to conversation context: {e}")

    # Autonomous memory processing for assistant response
    try:
        from .memory import get_memory_trigger, get_memory_learning
        
        # Analyze assistant response for memory insights
        memory_trigger = get_memory_trigger()
        memory_learning = get_memory_learning()
        
        context = {
            "session_id": session_id, 
            "message_id": bot.id,
            "user_message": user_message,
            "is_assistant_response": True
        }
        
        # Learn from successful interaction patterns
        await memory_learning.learn_from_feedback(
            "interaction_pattern",
            f"User: {user_message[:100]}... | Assistant: {assistant_msg[:100]}...",
            context
        )
        
        # Store any self-awareness or personality insights from assistant response
        storage_analysis = await memory_trigger.analyze_for_storage(assistant_msg, context)
        
        if storage_analysis["should_store"]:
            logger.debug(f"Autonomous memory: storing {len(storage_analysis['entries'])} items from assistant response")
            
            for entry in storage_analysis["entries"]:
                await memory_trigger.memory_manager.set(
                    section=entry["section"],
                    key=entry["key"],
                    value=entry["value"],
                    session_id=entry.get("session_id"),
                    ttl_seconds=entry.get("ttl_seconds")
                )
        
    except Exception as e:
        logger.warning(f"Error in autonomous memory processing for assistant response: {e}")

    # Publish assistant message sent event
    if event_bus._running:
        response_event = create_agent_event(
            StandardEventTypes.AGENT_MESSAGE_SENT,
            session_id,
            {
                "message_id": bot.id,
                "role": "assistant",
                "content": assistant_msg[:100] + "..." if len(assistant_msg) > 100 else assistant_msg,
                "timestamp": bot.timestamp.isoformat() if bot.timestamp else None
            }
        )
        event_bus.publish_sync(response_event)

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