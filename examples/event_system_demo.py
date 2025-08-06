#!/usr/bin/env python3
"""
Demo script to show the Event Bus System working in Nagatha Assistant.
"""

import asyncio
from typing import List

from nagatha_assistant.core.event_bus import get_event_bus, ensure_event_bus_started
from nagatha_assistant.core.event import (
    Event, EventPriority, StandardEventTypes,
    create_system_event, create_agent_event, create_mcp_event
)
from nagatha_assistant.utils.logger import get_logger

# Set up logging to see events
import logging
logging.basicConfig(level=logging.INFO)
logger = get_logger()


async def demo_event_system():
    """Demonstrate the event bus system features."""
    
    print("🚀 Starting Event Bus System Demo")
    print("=" * 50)
    
    # Start the event bus
    event_bus = await ensure_event_bus_started()
    
    # Storage for received events
    received_events: List[Event] = []
    
    # Define event handlers
    async def system_event_handler(event: Event):
        logger.info(f"🏛️  System Event: {event.event_type} (Priority: {event.priority.name})")
        received_events.append(event)
    
    async def agent_event_handler(event: Event):
        logger.info(f"🤖 Agent Event: {event.event_type} - Session {event.data.get('session_id')}")
        received_events.append(event)
    
    async def mcp_event_handler(event: Event):
        logger.info(f"🔧 MCP Event: {event.event_type} - Server: {event.data.get('server_name')}")
        received_events.append(event)
    
    def priority_event_handler(event: Event):
        logger.info(f"⚡ High Priority Event: {event.event_type} (Priority: {event.priority.name})")
        received_events.append(event)
    
    async def all_events_handler(event: Event):
        logger.info(f"📡 All Events Monitor: {event.event_type}")
    
    # Subscribe to different event patterns
    print("\n📋 Setting up event subscriptions...")
    
    # Subscribe to all system events
    system_sub = event_bus.subscribe("system.*", system_event_handler)
    
    # Subscribe to all agent events
    agent_sub = event_bus.subscribe("agent.*", agent_event_handler)
    
    # Subscribe to all MCP events
    mcp_sub = event_bus.subscribe("mcp.*", mcp_event_handler)
    
    # Subscribe to high priority events only
    priority_sub = event_bus.subscribe("*", priority_event_handler, 
                                      priority_filter=EventPriority.HIGH)
    
    # Subscribe to all events (for monitoring)
    all_sub = event_bus.subscribe("*", all_events_handler)
    
    print(f"✅ Created {len(event_bus.get_subscriptions())} subscriptions")
    
    # Publish various events
    print("\n📤 Publishing test events...")
    
    # System events
    await event_bus.publish(create_system_event(
        StandardEventTypes.SYSTEM_STARTUP,
        {"demo": True, "version": "1.0"},
        EventPriority.HIGH
    ))
    
    # Agent events
    await event_bus.publish(create_agent_event(
        StandardEventTypes.AGENT_CONVERSATION_STARTED,
        123,
        {"user": "demo_user"}
    ))
    
    await event_bus.publish(create_agent_event(
        StandardEventTypes.AGENT_MESSAGE_RECEIVED,
        123,
        {"content": "Hello Nagatha!", "role": "user"}
    ))
    
    await event_bus.publish(create_agent_event(
        StandardEventTypes.AGENT_MESSAGE_SENT,
        123,
        {"content": "Hello! How can I help you today?", "role": "assistant"}
    ))
    
    # MCP events
    await event_bus.publish(create_mcp_event(
        StandardEventTypes.MCP_SERVER_CONNECTED,
        "demo-server",
        {"status": "connected", "tools": ["search", "analyze"]}
    ))
    
    await event_bus.publish(create_mcp_event(
        StandardEventTypes.MCP_TOOL_CALLED,
        "demo-server",
        {"tool": "search", "args": {"query": "Python async"}},
        priority=EventPriority.HIGH
    ))
    
    # Custom events
    custom_event = Event(
        event_type="demo.custom.event",
        data={"custom": True, "value": 42},
        priority=EventPriority.CRITICAL,
        source="demo"
    )
    await event_bus.publish(custom_event)
    
    # Give time for async processing
    await asyncio.sleep(0.5)
    
    # Show results
    print(f"\n📊 Event Processing Results:")
    print(f"   Total events received by handlers: {len(received_events)}")
    print(f"   Total events in history: {len(event_bus.get_event_history())}")
    
    # Show event history
    print(f"\n📜 Event History (last 5 events):")
    history = event_bus.get_event_history(limit=5)
    for i, event in enumerate(history, 1):
        print(f"   {i}. {event.event_type} (Priority: {event.priority.name}, Source: {event.source})")
    
    # Show pattern matching
    print(f"\n🔍 Pattern Matching Demo:")
    agent_history = event_bus.get_event_history(event_type_pattern="agent.*")
    print(f"   Agent events in history: {len(agent_history)}")
    
    system_history = event_bus.get_event_history(event_type_pattern="system.*")
    print(f"   System events in history: {len(system_history)}")
    
    # Show subscriptions
    print(f"\n📋 Active Subscriptions:")
    subs = event_bus.get_subscriptions()
    for sub in subs:
        priority_filter = f" (Priority: {sub['priority_filter'].name})" if sub['priority_filter'] else ""
        print(f"   • Pattern: {sub['pattern']}{priority_filter}")
    
    # Cleanup
    print(f"\n🧹 Cleaning up...")
    event_bus.unsubscribe(system_sub)
    event_bus.unsubscribe(agent_sub)
    event_bus.unsubscribe(mcp_sub)
    event_bus.unsubscribe(priority_sub)
    event_bus.unsubscribe(all_sub)
    
    print(f"   Subscriptions after cleanup: {len(event_bus.get_subscriptions())}")
    
    # Stop the event bus
    await event_bus.stop()
    
    print(f"\n✅ Event Bus System Demo Complete!")
    print(f"   The system successfully demonstrated:")
    print(f"   • Asynchronous publish/subscribe pattern")
    print(f"   • Event priorities and filtering")
    print(f"   • Event history tracking")
    print(f"   • Wildcard pattern subscriptions")
    print(f"   • Thread-safe operations")


if __name__ == "__main__":
    asyncio.run(demo_event_system())