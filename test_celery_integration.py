#!/usr/bin/env python3
"""
Test script for Nagatha Celery Integration.

This script tests the basic functionality of the Nagatha core features
integration with Celery platform.

Usage:
    python test_celery_integration.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add web_dashboard to path
web_dashboard_path = Path(__file__).parent / "web_dashboard"
if web_dashboard_path.exists():
    sys.path.insert(0, str(web_dashboard_path))

# Add Nagatha source to path
nagatha_src_path = Path(__file__).parent / "src"
if nagatha_src_path.exists():
    sys.path.insert(0, str(nagatha_src_path))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_dashboard.settings.development')

import django
django.setup()

from dashboard.nagatha_celery_integration import (
    get_nagatha_bridge,
    process_message_with_nagatha,
    check_mcp_servers_health,
    cleanup_memory_and_maintenance,
    track_usage_metrics,
    process_scheduled_tasks,
    reload_mcp_configuration
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_bridge_initialization():
    """Test NagathaCeleryBridge initialization."""
    print("Testing NagathaCeleryBridge initialization...")
    
    try:
        bridge = get_nagatha_bridge()
        print("✓ Bridge created successfully")
        
        # Test async initialization
        result = bridge._run_async(bridge._ensure_initialized())
        print("✓ Bridge initialization successful")
        
        return True
    except Exception as e:
        print(f"✗ Bridge initialization failed: {e}")
        return False


def test_message_processing():
    """Test message processing with Nagatha core."""
    print("\nTesting message processing...")
    
    try:
        # Start the task
        result = process_message_with_nagatha.delay(None, "Hello from test script!")
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            print("✓ Message processing successful")
            print(f"  Response: {task_result.get('response', 'No response')[:100]}...")
            return True
        else:
            print(f"✗ Message processing failed: {task_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Message processing error: {e}")
        return False


def test_mcp_health_check():
    """Test MCP server health check."""
    print("\nTesting MCP health check...")
    
    try:
        # Start the task
        result = check_mcp_servers_health.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            print("✓ MCP health check successful")
            mcp_status = task_result.get('mcp_status', {})
            print(f"  Connected servers: {mcp_status.get('connected', 0)}")
            print(f"  Total configured: {mcp_status.get('total_configured', 0)}")
            return True
        else:
            print(f"✗ MCP health check failed: {task_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ MCP health check error: {e}")
        return False


def test_memory_cleanup():
    """Test memory cleanup and maintenance."""
    print("\nTesting memory cleanup...")
    
    try:
        # Start the task
        result = cleanup_memory_and_maintenance.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            print("✓ Memory cleanup successful")
            cleanup_result = task_result.get('cleanup_result', {})
            print(f"  Cleaned entries: {cleanup_result.get('cleaned_entries', 0)}")
            return True
        else:
            print(f"✗ Memory cleanup failed: {task_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Memory cleanup error: {e}")
        return False


def test_usage_tracking():
    """Test usage metrics tracking."""
    print("\nTesting usage tracking...")
    
    try:
        # Start the task
        result = track_usage_metrics.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            print("✓ Usage tracking successful")
            print(f"  Total cost: ${task_result.get('total_cost', 0):.4f}")
            print(f"  Total requests: {task_result.get('total_requests', 0)}")
            return True
        else:
            print(f"✗ Usage tracking failed: {task_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Usage tracking error: {e}")
        return False


def test_scheduled_tasks():
    """Test scheduled tasks processing."""
    print("\nTesting scheduled tasks...")
    
    try:
        # Start the task
        result = process_scheduled_tasks.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            print("✓ Scheduled tasks successful")
            print(f"  Due tasks: {task_result.get('due_tasks', 0)}")
            print(f"  Due reminders: {task_result.get('due_reminders', 0)}")
            return True
        else:
            print(f"✗ Scheduled tasks failed: {task_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Scheduled tasks error: {e}")
        return False


def test_mcp_reload():
    """Test MCP configuration reload."""
    print("\nTesting MCP reload...")
    
    try:
        # Start the task
        result = reload_mcp_configuration.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            print("✓ MCP reload successful")
            return True
        else:
            print(f"✗ MCP reload failed: {task_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ MCP reload error: {e}")
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Nagatha Celery Integration Test")
    print("=" * 60)
    
    # Check environment
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Nagatha source path: {nagatha_src_path}")
    print(f"Web dashboard path: {web_dashboard_path}")
    
    # Check required environment variables
    required_vars = ['OPENAI_API_KEY', 'DJANGO_SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {missing_vars}")
        print("Some tests may fail without these variables.")
    
    # Run tests
    tests = [
        ("Bridge Initialization", test_bridge_initialization),
        ("Message Processing", test_message_processing),
        ("MCP Health Check", test_mcp_health_check),
        ("Memory Cleanup", test_memory_cleanup),
        ("Usage Tracking", test_usage_tracking),
        ("Scheduled Tasks", test_scheduled_tasks),
        ("MCP Reload", test_mcp_reload),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{test_name:<25} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 