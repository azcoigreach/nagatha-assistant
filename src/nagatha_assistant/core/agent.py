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


async def _autonomous_memory_maintenance_loop() -> None:
    """Background task for autonomous memory maintenance."""
    logger = setup_logger_with_env_control()
    
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
    
    # Initialize memory manager
    try:
        from .memory import ensure_memory_manager_started
        await ensure_memory_manager_started()
        logger.info("Memory manager started")
        
        # Start autonomous memory maintenance task
        asyncio.create_task(_autonomous_memory_maintenance_loop())
        logger.info("Autonomous memory maintenance started")
        
    except Exception as e:
        logger.exception(f"Error starting memory manager: {e}")
    
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
        logging.exception(f"Error shutting down plugins: {e}")
    
    # Shutdown memory manager
    try:
        from .memory import shutdown_memory_manager
        await shutdown_memory_manager()
    except Exception as e:
        logging.exception(f"Error shutting down memory manager: {e}")
    
    await shutdown_mcp_manager()
    
    # Stop the event bus
    await event_bus.stop()

async def start_session() -> int:
    """Create a new conversation session and return its ID."""
    await init_db()
    # Ensure MCP is initialized
    await get_mcp_manager()
    
    # Ensure memory manager is started
    try:
        from .memory import ensure_memory_manager_started
        await ensure_memory_manager_started()
    except Exception as e:
        logging.exception(f"Error ensuring memory manager is started: {e}")
    
    # Ensure plugins are initialized
    try:
        from .plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        if not plugin_manager._plugins:  # Only load if not already loaded
            await plugin_manager.load_and_start_all()
    except Exception as e:
        logging.exception(f"Error ensuring plugins are loaded: {e}")
    
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
    """Get list of all available MCP tools and plugin commands."""
    tools = []
    
    # Get MCP tools
    try:
        mcp_manager = await get_mcp_manager()
        mcp_tools = mcp_manager.get_available_tools()
        tools.extend(mcp_tools)
    except Exception as e:
        logging.error(f"Error getting MCP tools: {e}")
    
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
        logging.error(f"Error getting plugin commands: {e}")
    
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
        logging.error(f"Error getting MCP status: {e}")
        return {"error": str(e), "servers": {}, "tools": [], "initialized": False}

async def reload_mcp_configuration() -> Dict[str, Any]:
    """Reload MCP configuration and return updated status."""
    try:
        mcp_manager = await get_mcp_manager()
        await mcp_manager.reload_configuration()
        return await get_mcp_status()
    except Exception as e:
        logging.error(f"Error reloading MCP configuration: {e}")
        return {"error": str(e), "servers": {}, "tools": [], "initialized": False}

async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call an MCP tool and return the result."""
    try:
        mcp_manager = await get_mcp_manager()
        return await mcp_manager.call_tool(tool_name, arguments)
    except Exception as e:
        logging.error(f"Error calling MCP tool '{tool_name}': {e}")
        raise


async def call_plugin_command(command_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a plugin command and return the result."""
    try:
        from .plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        return await plugin_manager.execute_command(command_name, **arguments)
    except Exception as e:
        logging.error(f"Error calling plugin command '{command_name}': {e}")
        raise


async def call_tool_or_command(name: str, arguments: Dict[str, Any]) -> Any:
    """
    Call either an MCP tool or plugin command by name.
    
    First tries MCP tools, then plugin commands.
    """
    try:
        # Try MCP tool first
        return await call_mcp_tool(name, arguments)
    except Exception:
        try:
            # Fall back to plugin command
            return await call_plugin_command(name, arguments)
        except Exception as e:
            logging.error(f"Error calling tool/command '{name}': {e}")
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
    
    logging.getLogger(__name__).info(f"Tool selection: {len(available_tools)} available, {len(selected_tools)} selected for user message")
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
            # Get conversation history
            messages = await get_messages(session_id)
            conversation_history = []
            
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
                
                # Get personality adaptations
                personality_adaptations = await personality_memory.adapt_to_context(
                    user_message, session_id
                )
                
                # Create base system prompt
                base_system_prompt = get_system_prompt(available_tools)
                
                # Enhance with memory context
                memory_context = ""
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
                
                # Enhance with personality adaptations
                if personality_adaptations:
                    personality_context = "\n\n## Interaction Guidance for This Context:\n"
                    personality_context += f"- **Tone**: {personality_adaptations.get('tone', 'warm and professional')}\n"
                    personality_context += f"- **Detail Level**: {personality_adaptations.get('detail_level', 'balanced')}\n"
                    personality_context += f"- **Formality**: {personality_adaptations.get('formality', 'casual-professional')}\n"
                    personality_context += f"- **Response Style**: {personality_adaptations.get('response_style', 'helpful and engaging')}\n"
                    
                    memory_context += personality_context
                
                # Combine base prompt with memory context
                enhanced_system_prompt = base_system_prompt + memory_context
                
                logger.debug(f"Enhanced system prompt with {len(relevant_memories)} memory sections and personality adaptations")
                
            except Exception as e:
                logger.warning(f"Error enhancing system prompt with memory context: {e}")
                enhanced_system_prompt = get_system_prompt(available_tools)
            
            conversation_history.append({"role": "system", "content": enhanced_system_prompt})
            
            # Add message history (excluding the latest user message which we already have)
            for msg in messages[:-1]:  # Exclude the last message we just saved
                conversation_history.append({"role": msg.role, "content": msg.content})
            
            # Add the current user message
            conversation_history.append({"role": "user", "content": user_message})

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
                        tool_result = await call_tool_or_command(tool_name, tool_args)
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
                    
                    assistant_msg = final_response.choices[0].message.content or assistant_msg
            else:
                # No tool calls, just use the direct response
                assistant_msg = response.choices[0].message.content or ""
            
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