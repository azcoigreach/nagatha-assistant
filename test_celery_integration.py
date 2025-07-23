#!/usr/bin/env python3
"""
Test script for the Celery-based event system integration.

This script tests the basic functionality of the new Celery event system
to ensure it works correctly with the existing codebase.
"""

import asyncio
import os
import sys
import logging
from typing import Dict, Any

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.utils.logger import setup_logger_with_env_control
from nagatha_assistant.core.event import Event, EventPriority

logger = setup_logger_with_env_control()


async def test_event_bus():
    """Test the Celery event bus functionality."""
    logger.info("Testing Celery event bus...")
    
    try:
        from nagatha_assistant.core.celery_event_bus import get_celery_event_bus, ensure_celery_event_bus_started
        
        # Get and start the event bus
        event_bus = await ensure_celery_event_bus_started()
        logger.info("✓ Celery event bus started successfully")
        
        # Test event creation
        test_event = Event(
            event_type="test.celery.integration",
            data={"test": True, "message": "Hello from Celery test"},
            priority=EventPriority.NORMAL,
            source="test_script"
        )
        
        # Test publishing an event
        await event_bus.publish(test_event)
        logger.info("✓ Event published successfully")
        
        # Test event history
        history = event_bus.get_event_history(limit=5)
        logger.info(f"✓ Event history retrieved: {len(history)} events")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Event bus test failed: {e}")
        return False


async def test_storage_layer():
    """Test the Redis storage layer."""
    logger.info("Testing Redis storage layer...")
    
    try:
        from nagatha_assistant.core.celery_event_storage import get_system_status, create_session, store_message
        
        # Test system status
        status = get_system_status()
        logger.info(f"✓ System status retrieved: {status.get('system_health', 'unknown')}")
        
        # Test session creation
        session_id = create_session("test_user")
        logger.info(f"✓ Session created with ID: {session_id}")
        
        # Test message storage
        message_id = store_message(session_id, "Hello, this is a test message!", "user")
        logger.info(f"✓ Message stored with ID: {message_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Storage layer test failed: {e}")
        return False


async def test_task_system():
    """Test the Celery task system."""
    logger.info("Testing Celery task system...")
    
    try:
        from nagatha_assistant.core.celery_tasks import publish_event_task, system_health_check_task
        
        # Test event publishing task
        result = publish_event_task.delay(
            "test.task.event",
            {"test": True, "from": "task_system"},
            priority=2,
            source="test_script"
        )
        logger.info(f"✓ Event task queued with ID: {result.id}")
        
        # Test system health check task
        health_result = system_health_check_task.delay()
        logger.info(f"✓ Health check task queued with ID: {health_result.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Task system test failed: {e}")
        return False


async def test_compatibility_layer():
    """Test the compatibility layer."""
    logger.info("Testing compatibility layer...")
    
    try:
        from nagatha_assistant.core.celery_storage import get_event_bus, get_system_status_sync
        
        # Test getting event bus through compatibility layer
        event_bus = get_event_bus()
        logger.info("✓ Event bus obtained through compatibility layer")
        
        # Test system status through compatibility layer
        status = get_system_status_sync()
        logger.info(f"✓ System status through compatibility layer: {status.get('system_health', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Compatibility layer test failed: {e}")
        return False


def test_celery_connection():
    """Test basic Celery connectivity."""
    logger.info("Testing Celery connection...")
    
    try:
        from nagatha_assistant.celery_app import app
        
        # Test Celery app configuration
        logger.info(f"✓ Celery app created: {app.main}")
        logger.info(f"✓ Broker URL: {app.conf.broker_url}")
        logger.info(f"✓ Result backend: {app.conf.result_backend}")
        
        # Test Redis connection
        from nagatha_assistant.core.celery_event_storage import get_redis_client
        redis_client = get_redis_client()
        redis_client.ping()
        logger.info("✓ Redis connection successful")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Celery connection test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("Starting Celery integration tests...")
    logger.info("=" * 50)
    
    tests = [
        ("Celery Connection", test_celery_connection),
        ("Storage Layer", test_storage_layer),
        ("Compatibility Layer", test_compatibility_layer),
        ("Event Bus", test_event_bus),
        ("Task System", test_task_system),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} Test ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"Test {test_name} raised exception: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Celery integration is working correctly.")
        return 0
    else:
        logger.warning("⚠️  Some tests failed. Check the logs above for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)