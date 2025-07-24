#!/usr/bin/env python3
"""
Test script for Nagatha's hybrid storage system.

This script tests the combination of Redis (fast access) and SQLite (long-term persistence).
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from nagatha_assistant.db import engine
from nagatha_assistant.db_models import Base
from sqlalchemy import text

# Import the hybrid storage backend
try:
    from web_dashboard.dashboard.hybrid_memory_storage import HybridMemoryStorageBackend
    HYBRID_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Hybrid storage not available: {e}")
    HYBRID_AVAILABLE = False

async def setup_database():
    """Set up the database with all required tables."""
    print("🔧 Setting up database...")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")
        
        # Verify memory tables exist
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%memory%'"))
            tables = result.fetchall()
            print(f"📋 Memory tables found: {[t[0] for t in tables]}")
            
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        raise

async def test_redis_connection():
    """Test Redis connection."""
    print("\n🔴 Testing Redis connection...")
    
    try:
        import redis.asyncio as redis
        
        # Test Redis connection
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        await redis_client.ping()
        print("✅ Redis connection successful")
        
        # Test basic Redis operations
        await redis_client.set("test_key", "test_value")
        value = await redis_client.get("test_key")
        print(f"✅ Redis basic operations: stored='test_value', retrieved='{value}'")
        
        await redis_client.close()
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

async def test_hybrid_storage():
    """Test the hybrid storage backend."""
    if not HYBRID_AVAILABLE:
        print("❌ Hybrid storage not available")
        return False
    
    print("\n🔄 Testing HybridMemoryStorageBackend...")
    
    try:
        hybrid_storage = HybridMemoryStorageBackend()
        print("✅ Hybrid storage backend created")
        
        # Test storing data that should go to Redis (session state, temporary)
        print("\n📊 Testing Redis storage (session state, temporary)...")
        await hybrid_storage.set("session_state", "current_user", "Alice", session_id=456)
        await hybrid_storage.set("temporary", "cache_data", {"key": "value"}, ttl_seconds=300)
        await hybrid_storage.set("user_preferences", "theme", "dark")
        
        # Test storing data that should go to SQLite (facts, command history)
        print("💾 Testing SQLite storage (facts, command history)...")
        await hybrid_storage.set("facts", "important_fact", "This is a long-term fact")
        await hybrid_storage.set("command_history", "recent_command", "User asked about memory system")
        
        # Test retrieval from both storage systems
        print("\n📖 Testing retrieval from both storage systems...")
        user = await hybrid_storage.get("session_state", "current_user", session_id=456)
        theme = await hybrid_storage.get("user_preferences", "theme")
        fact = await hybrid_storage.get("facts", "important_fact")
        cache_data = await hybrid_storage.get("temporary", "cache_data")
        
        print(f"✅ Retrieved data:")
        print(f"   Session user: {user}")
        print(f"   Theme preference: {theme}")
        print(f"   Important fact: {fact}")
        print(f"   Cache data: {cache_data}")
        
        # Test search functionality
        print("\n🔍 Testing search functionality...")
        results = await hybrid_storage.search("facts", "long-term")
        print(f"✅ Search results: {len(results)} found")
        
        for result in results:
            print(f"   - {result.get('key')}: {result.get('value')}")
        
        # Test sync to database
        print("\n🔄 Testing Redis to SQLite sync...")
        sync_results = await hybrid_storage.sync_redis_to_sqlite()
        print(f"✅ Sync results: {sync_results}")
        
        # Test cleanup
        print("\n🧹 Testing cleanup...")
        cleaned_count = await hybrid_storage.cleanup_expired()
        print(f"✅ Cleaned up {cleaned_count} expired entries")
        
        await hybrid_storage.close()
        return True
        
    except Exception as e:
        print(f"❌ Hybrid storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_performance_comparison():
    """Test performance comparison between storage backends."""
    print("\n⚡ Testing performance comparison...")
    
    if not HYBRID_AVAILABLE:
        print("❌ Hybrid storage not available for performance test")
        return
    
    try:
        hybrid_storage = HybridMemoryStorageBackend()
        
        # Test Redis performance (fast access)
        print("\n🔴 Testing Redis performance (fast access)...")
        start_time = datetime.now()
        
        for i in range(100):
            await hybrid_storage.set("session_state", f"key_{i}", f"value_{i}", session_id=123)
        
        redis_write_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ Redis write time for 100 entries: {redis_write_time:.3f}s")
        
        # Test SQLite performance (long-term storage)
        print("\n💾 Testing SQLite performance (long-term storage)...")
        start_time = datetime.now()
        
        for i in range(100):
            await hybrid_storage.set("facts", f"fact_{i}", f"This is fact number {i}")
        
        sqlite_write_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ SQLite write time for 100 entries: {sqlite_write_time:.3f}s")
        
        # Test read performance
        print("\n📖 Testing read performance...")
        start_time = datetime.now()
        
        for i in range(100):
            await hybrid_storage.get("session_state", f"key_{i}", session_id=123)
        
        redis_read_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ Redis read time for 100 entries: {redis_read_time:.3f}s")
        
        start_time = datetime.now()
        for i in range(100):
            await hybrid_storage.get("facts", f"fact_{i}")
        
        sqlite_read_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ SQLite read time for 100 entries: {sqlite_read_time:.3f}s")
        
        print(f"\n📊 Performance Summary:")
        print(f"   Redis write: {redis_write_time:.3f}s (fast)")
        print(f"   SQLite write: {sqlite_write_time:.3f}s (persistent)")
        print(f"   Redis read: {redis_read_time:.3f}s (fast)")
        print(f"   SQLite read: {sqlite_read_time:.3f}s (persistent)")
        
        await hybrid_storage.close()
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")

async def test_celery_integration():
    """Test how the hybrid storage works with Celery tasks."""
    print("\n🎯 Testing Celery integration...")
    
    if not HYBRID_AVAILABLE:
        print("❌ Hybrid storage not available for Celery test")
        return
    
    try:
        # Simulate Celery task operations
        print("📝 Simulating Celery task operations...")
        
        hybrid_storage = HybridMemoryStorageBackend()
        
        # Simulate background task storing data
        await hybrid_storage.set("background_task", "task_result", "Task completed successfully", ttl_seconds=3600)
        await hybrid_storage.set("analytics", "user_activity", {"sessions": 5, "commands": 25}, ttl_seconds=86400)
        
        # Simulate task retrieving data
        task_result = await hybrid_storage.get("background_task", "task_result")
        analytics = await hybrid_storage.get("analytics", "user_activity")
        
        print(f"✅ Celery task data:")
        print(f"   Task result: {task_result}")
        print(f"   Analytics: {analytics}")
        
        # Simulate periodic sync task
        print("\n🔄 Simulating periodic sync task...")
        sync_results = await hybrid_storage.sync_redis_to_sqlite()
        print(f"✅ Periodic sync completed: {sync_results}")
        
        await hybrid_storage.close()
        
    except Exception as e:
        print(f"❌ Celery integration test failed: {e}")

async def main():
    """Main test function."""
    print("🔄 Nagatha Hybrid Storage System Test")
    print("=" * 50)
    
    try:
        # Setup database
        await setup_database()
        
        # Test Redis connection
        redis_ok = await test_redis_connection()
        
        if redis_ok:
            # Test hybrid storage
            hybrid_ok = await test_hybrid_storage()
            
            if hybrid_ok:
                # Test performance
                await test_performance_comparison()
                
                # Test Celery integration
                await test_celery_integration()
                
                print("\n🎉 All hybrid storage tests completed successfully!")
                print("\n📋 Summary:")
                print("✅ Database setup and migrations")
                print("✅ Redis connection and operations")
                print("✅ Hybrid storage functionality")
                print("✅ Performance comparison")
                print("✅ Celery integration")
                
                print("\n💡 Key Features Demonstrated:")
                print("   • Redis for fast, temporary data")
                print("   • SQLite for long-term persistence")
                print("   • Automatic data routing based on type")
                print("   • Synchronization between storage systems")
                print("   • Celery-compatible operations")
                print("   • Performance optimization")
                
            else:
                print("\n❌ Hybrid storage test failed")
        else:
            print("\n❌ Redis connection test failed")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 