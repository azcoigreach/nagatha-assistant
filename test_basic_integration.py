#!/usr/bin/env python3
"""
Basic integration test for Nagatha Celery system without requiring Celery to be installed.

This test validates the code structure, imports, and basic functionality
that doesn't require a running Celery worker.
"""

import os
import sys
import logging

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


def test_imports():
    """Test that all new modules can be imported."""
    logger.info("Testing module imports...")
    
    try:
        # Test basic imports (these shouldn't require Celery to be installed)
        from nagatha_assistant.core.event import Event, EventPriority
        logger.info("✓ Core event system imports")
        
        from nagatha_assistant.core.celery_storage import (
            get_event_bus, create_session_sync, store_message_sync
        )
        logger.info("✓ Celery storage compatibility layer imports")
        
        # Test that the modules exist and have the expected structure
        import nagatha_assistant.core.celery_tasks
        logger.info("✓ Celery tasks module structure")
        
        import nagatha_assistant.core.celery_event_storage
        logger.info("✓ Celery event storage module structure")
        
        import nagatha_assistant.core.celery_event_bus
        logger.info("✓ Celery event bus module structure")
        
        import nagatha_assistant.core.celery_beat
        logger.info("✓ Celery beat configuration module structure")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error during imports: {e}")
        return False


def test_event_system_fallback():
    """Test that the event system falls back gracefully when Celery is not available."""
    logger.info("Testing event system fallback...")
    
    try:
        from nagatha_assistant.core.celery_storage import get_event_bus
        
        # This should fall back to the original event bus when Celery is not available
        event_bus = get_event_bus()
        logger.info(f"✓ Event bus obtained: {type(event_bus).__name__}")
        
        # Test that the event bus has the expected interface
        if hasattr(event_bus, 'subscribe') and hasattr(event_bus, 'publish_sync'):
            logger.info("✓ Event bus has expected interface")
            return True
        else:
            logger.error("✗ Event bus missing expected methods")
            return False
            
    except Exception as e:
        logger.error(f"✗ Event system fallback test failed: {e}")
        return False


def test_storage_compatibility():
    """Test the storage compatibility layer."""
    logger.info("Testing storage compatibility layer...")
    
    try:
        from nagatha_assistant.core.celery_storage import (
            create_session_sync, store_message_sync, get_session_messages_sync
        )
        
        # These functions should exist and be callable
        # (They will fail at runtime without Redis, but should be importable)
        logger.info("✓ Storage functions are importable")
        
        # Test that the functions have the expected signatures
        import inspect
        
        create_sig = inspect.signature(create_session_sync)
        if 'user_id' in create_sig.parameters:
            logger.info("✓ create_session_sync has expected signature")
        else:
            logger.error("✗ create_session_sync missing expected parameters")
            return False
            
        store_sig = inspect.signature(store_message_sync)
        expected_params = {'session_id', 'content', 'message_type'}
        if expected_params.issubset(store_sig.parameters.keys()):
            logger.info("✓ store_message_sync has expected signature")
        else:
            logger.error("✗ store_message_sync missing expected parameters")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"✗ Storage compatibility test failed: {e}")
        return False


def test_agent_integration():
    """Test that agent integration functions exist."""
    logger.info("Testing agent integration...")
    
    try:
        from nagatha_assistant.core.agent import send_message_via_celery
        
        # Function should exist and be callable
        import inspect
        sig = inspect.signature(send_message_via_celery)
        expected_params = {'session_id', 'user_message'}
        
        if expected_params.issubset(sig.parameters.keys()):
            logger.info("✓ send_message_via_celery has expected signature")
            return True
        else:
            logger.error("✗ send_message_via_celery missing expected parameters")
            return False
            
    except Exception as e:
        logger.error(f"✗ Agent integration test failed: {e}")
        return False


def test_discord_integration():
    """Test that Discord integration has been updated."""
    logger.info("Testing Discord integration...")
    
    try:
        # Read the Discord bot file to check for Celery integration
        discord_file = os.path.join('src', 'nagatha_assistant', 'plugins', 'discord_bot.py')
        
        if os.path.exists(discord_file):
            with open(discord_file, 'r') as f:
                content = f.read()
                
            if 'send_message_via_celery' in content:
                logger.info("✓ Discord bot updated to use Celery")
                return True
            else:
                logger.error("✗ Discord bot not updated for Celery")
                return False
        else:
            logger.warning("! Discord bot file not found, skipping test")
            return True
            
    except Exception as e:
        logger.error(f"✗ Discord integration test failed: {e}")
        return False


def test_configuration_files():
    """Test that configuration files are present."""
    logger.info("Testing configuration files...")
    
    files_to_check = [
        ('CELERY_INTEGRATION.md', 'Documentation'),
        ('.env.example.celery', 'Environment configuration'),
        ('start_celery.sh', 'Startup script'),
        ('test_celery_integration.py', 'Full integration test'),
    ]
    
    all_present = True
    
    for filename, description in files_to_check:
        if os.path.exists(filename):
            logger.info(f"✓ {description} present: {filename}")
        else:
            logger.error(f"✗ {description} missing: {filename}")
            all_present = False
    
    return all_present


def test_requirements_updated():
    """Test that requirements.txt has been updated with Celery dependencies."""
    logger.info("Testing requirements update...")
    
    try:
        with open('requirements.txt', 'r') as f:
            content = f.read()
        
        required_packages = ['celery', 'redis', 'kombu']
        found_packages = []
        
        for package in required_packages:
            if package in content.lower():
                found_packages.append(package)
                logger.info(f"✓ {package} found in requirements.txt")
            else:
                logger.error(f"✗ {package} missing from requirements.txt")
        
        return len(found_packages) == len(required_packages)
        
    except Exception as e:
        logger.error(f"✗ Requirements test failed: {e}")
        return False


def main():
    """Run all basic tests."""
    logger.info("Starting basic Celery integration tests...")
    logger.info("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Event System Fallback", test_event_system_fallback),
        ("Storage Compatibility", test_storage_compatibility),
        ("Agent Integration", test_agent_integration),
        ("Discord Integration", test_discord_integration),
        ("Configuration Files", test_configuration_files),
        ("Requirements Update", test_requirements_updated),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} Test ---")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"Test {test_name} raised exception: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("BASIC TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All basic tests passed! Code structure is correct.")
        logger.info("\nNext steps:")
        logger.info("1. Install Celery dependencies: pip install celery redis")
        logger.info("2. Start Redis server")
        logger.info("3. Run the full integration test: python test_celery_integration.py")
        logger.info("4. Start Celery services: ./start_celery.sh")
        return 0
    else:
        logger.warning("⚠️  Some basic tests failed. Check the code structure.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)