#!/usr/bin/env python3
"""
Demonstration script for Nagatha Assistant Task Scheduler.

This script shows how to use the task scheduler to schedule various types of tasks
including MCP tool calls, plugin commands, notifications, and shell commands.
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timezone, timedelta

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.plugins.scheduler import get_scheduler
from nagatha_assistant.core.event_bus import ensure_event_bus_started, shutdown_event_bus


async def demonstrate_scheduler():
    """Demonstrate the task scheduler functionality."""
    
    print("🚀 Nagatha Assistant Task Scheduler Demonstration")
    print("=" * 60)
    
    # Start the event bus
    await ensure_event_bus_started()
    
    # Get the scheduler
    scheduler = get_scheduler()
    
    print("\n1. 📅 Scheduling Tasks")
    print("-" * 30)
    
    # Schedule a notification in 2 minutes
    try:
        task_id1 = await scheduler.schedule_notification(
            message="Hello from the scheduler! This is a test notification.",
            schedule_spec="in 2 minutes",
            notification_type="info",
            task_name="Demo Notification"
        )
        print(f"✅ Scheduled notification task: {task_id1}")
    except Exception as e:
        print(f"❌ Failed to schedule notification: {e}")
    
    # Schedule a recurring notification (every 5 minutes)
    try:
        task_id2 = await scheduler.schedule_notification(
            message="Recurring reminder from scheduler",
            schedule_spec="*/5 * * * *",  # Every 5 minutes
            notification_type="info",
            task_name="Recurring Demo"
        )
        print(f"✅ Scheduled recurring notification: {task_id2}")
    except Exception as e:
        print(f"❌ Failed to schedule recurring notification: {e}")
    
    # Schedule an MCP tool call (if available)
    try:
        task_id3 = await scheduler.schedule_mcp_tool(
            server_name="time",
            tool_name="get_current_time",
            arguments={},
            schedule_spec="in 30 seconds",
            task_name="Time Check"
        )
        print(f"✅ Scheduled MCP tool call: {task_id3}")
    except Exception as e:
        print(f"❌ Failed to schedule MCP tool call: {e}")
    
    # Schedule a plugin command
    try:
        task_id4 = await scheduler.schedule_plugin_command(
            plugin_name="echo",
            command_name="echo",
            arguments={"text": "Hello from scheduled plugin command!"},
            schedule_spec="in 45 seconds",
            task_name="Echo Test"
        )
        print(f"✅ Scheduled plugin command: {task_id4}")
    except Exception as e:
        print(f"❌ Failed to schedule plugin command: {e}")
    
    print("\n2. 📋 Listing Scheduled Tasks")
    print("-" * 30)
    
    # List all scheduled tasks
    tasks = scheduler.get_scheduled_tasks()
    if tasks:
        print(f"Found {len(tasks)} scheduled tasks:")
        for task in tasks:
            print(f"  • {task['task_id'][:8]}... - {task.get('name', task['task_type'])} ({task['status']})")
    else:
        print("No scheduled tasks found.")
    
    print("\n3. 🔍 Task Information")
    print("-" * 30)
    
    # Show details for the first task if available
    if tasks:
        first_task = tasks[0]
        task_info = scheduler.get_task_info(first_task['task_id'])
        if task_info:
            print(f"Task Details for {first_task['task_id'][:8]}...:")
            print(f"  Name: {task_info.get('name', 'N/A')}")
            print(f"  Type: {task_info['task_type']}")
            print(f"  Schedule Type: {task_info['schedule_type']}")
            print(f"  Status: {task_info['status']}")
            print(f"  Created: {task_info['created_at']}")
    
    print("\n4. ⏰ Natural Language Parsing Examples")
    print("-" * 30)
    
    # Test natural language parsing
    examples = [
        "in 30 minutes",
        "in 2 hours", 
        "tomorrow",
        "next week",
        "at 14:30"
    ]
    
    for example in examples:
        try:
            parsed = scheduler._parse_natural_language_time(example)
            if parsed:
                print(f"  '{example}' → {parsed.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            else:
                print(f"  '{example}' → Could not parse")
        except Exception as e:
            print(f"  '{example}' → Error: {e}")
    
    print("\n5. 📝 Cron Expression Examples")
    print("-" * 30)
    
    cron_examples = [
        ("0 9 * * *", "Daily at 9 AM"),
        ("*/5 * * * *", "Every 5 minutes"),
        ("0 0 * * 0", "Weekly on Sunday at midnight"),
        ("0 12 1 * *", "Monthly on the 1st at noon")
    ]
    
    for cron, description in cron_examples:
        try:
            parsed = scheduler._parse_schedule(cron)
            print(f"  '{cron}' - {description} ✅")
        except Exception as e:
            print(f"  '{cron}' - {description} ❌ ({e})")
    
    print("\n6. ❌ Canceling a Task")
    print("-" * 30)
    
    # Cancel the first scheduled task if available
    if tasks:
        task_to_cancel = tasks[0]['task_id']
        try:
            cancelled = await scheduler.cancel_task(task_to_cancel)
            if cancelled:
                print(f"✅ Successfully cancelled task: {task_to_cancel[:8]}...")
            else:
                print(f"❌ Failed to cancel task: {task_to_cancel[:8]}...")
        except Exception as e:
            print(f"❌ Error cancelling task: {e}")
    else:
        print("No tasks available to cancel.")
    
    print("\n7. 📊 Final Task Status")
    print("-" * 30)
    
    # Show final status
    final_tasks = scheduler.get_scheduled_tasks()
    if final_tasks:
        status_counts = {}
        for task in final_tasks:
            status = task['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("Task status summary:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
    else:
        print("No tasks remaining.")
    
    print("\n🎉 Demonstration Complete!")
    print("=" * 60)
    
    print("\nNext Steps:")
    print("1. Start Redis server: docker run -d -p 6379:6379 redis:7-alpine")
    print("2. Start Celery worker: celery -A nagatha_assistant.plugins.celery_app worker --loglevel=info")
    print("3. Start Celery beat: celery -A nagatha_assistant.plugins.celery_app beat --loglevel=info")
    print("4. Use Docker Compose: docker-compose -f docker-compose.scheduler.yml up")
    print("5. Use CLI commands: python -m nagatha_assistant.cli scheduler --help")
    
    # Clean up
    await shutdown_event_bus()


async def test_basic_functionality():
    """Test basic scheduler functionality without external dependencies."""
    
    print("🧪 Testing Basic Scheduler Functionality")
    print("=" * 50)
    
    # Start the event bus
    await ensure_event_bus_started()
    
    # Get the scheduler
    scheduler = get_scheduler()
    
    # Test natural language parsing
    print("\n📅 Testing Natural Language Parsing:")
    examples = ["in 30 minutes", "tomorrow", "invalid time"]
    
    for example in examples:
        result = scheduler._parse_natural_language_time(example)
        if result:
            print(f"  ✅ '{example}' → {result}")
        else:
            print(f"  ❌ '{example}' → Could not parse")
    
    # Test cron parsing
    print("\n⏰ Testing Cron Expression Parsing:")
    cron_examples = ["0 9 * * *", "*/5 * * * *", "invalid cron"]
    
    for cron in cron_examples:
        try:
            result = scheduler._parse_schedule(cron)
            print(f"  ✅ '{cron}' → {type(result).__name__}")
        except Exception as e:
            print(f"  ❌ '{cron}' → {e}")
    
    # Test task argument preparation
    print("\n🔧 Testing Task Argument Preparation:")
    test_cases = [
        ("mcp_tool", {"server_name": "test", "tool_name": "test", "arguments": {}}),
        ("notification", {"message": "test message"}),
        ("plugin_command", {"plugin_name": "test", "command_name": "test", "arguments": {}})
    ]
    
    for task_type, args in test_cases:
        result = scheduler._prepare_task_args(task_type, args)
        print(f"  ✅ {task_type}: {result}")
    
    print("\n✅ Basic functionality tests completed!")
    
    # Clean up
    await shutdown_event_bus()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Nagatha Assistant Scheduler Demo")
    parser.add_argument("--basic", action="store_true", 
                       help="Run basic tests only (no external dependencies)")
    args = parser.parse_args()
    
    if args.basic:
        asyncio.run(test_basic_functionality())
    else:
        asyncio.run(demonstrate_scheduler())