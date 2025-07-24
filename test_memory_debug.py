#!/usr/bin/env python3
"""
Debug script for Nagatha's memory system.

This script helps identify what's causing the hanging issue.
"""

import asyncio
import sys
import os
from pathlib import Path

print("🔍 Starting debug script...")

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print(f"📁 Added {src_path} to Python path")

try:
    print("📦 Testing imports...")
    from nagatha_assistant.db import engine
    print("✅ Engine import successful")
    
    from nagatha_assistant.db_models import Base
    print("✅ Base import successful")
    
    from nagatha_assistant.core.memory import MemoryManager
    print("✅ MemoryManager import successful")
    
    from nagatha_assistant.core.storage import DatabaseStorageBackend
    print("✅ DatabaseStorageBackend import successful")
    
    from sqlalchemy import text
    print("✅ SQLAlchemy text import successful")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def test_database_connection():
    """Test database connection."""
    print("\n🔧 Testing database connection...")
    
    try:
        async with engine.begin() as conn:
            print("✅ Database connection successful")
            
            # Test a simple query
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            print(f"✅ Test query successful: {value}")
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_storage_backend():
    """Test storage backend."""
    print("\n💾 Testing storage backend...")
    
    try:
        storage = DatabaseStorageBackend()
        print("✅ Storage backend created")
        
        # Test basic operations
        await storage.set("test", "key", "value")
        print("✅ Set operation successful")
        
        value = await storage.get("test", "key")
        print(f"✅ Get operation successful: {value}")
        
    except Exception as e:
        print(f"❌ Storage backend test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def main():
    """Main debug function."""
    print("🐛 Nagatha Memory System Debug")
    print("=" * 40)
    
    # Test database connection
    db_ok = await test_database_connection()
    
    if db_ok:
        # Test storage backend
        storage_ok = await test_storage_backend()
        
        if storage_ok:
            print("\n🎉 All debug tests passed!")
        else:
            print("\n❌ Storage backend test failed")
    else:
        print("\n❌ Database connection test failed")
    
    print("\n🔍 Debug complete")

if __name__ == "__main__":
    asyncio.run(main()) 