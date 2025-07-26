#!/usr/bin/env python3
"""
Simple test to verify the logger fix.
"""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nagatha_assistant.core.agent import start_session

async def test_logger_fix():
    """Test that the logger fix works."""
    print("🔧 Testing Logger Fix")
    print("=" * 25)
    
    try:
        print("Starting session...")
        session_id = await start_session()
        print(f"✅ Session {session_id} started successfully!")
        print("✅ Logger fix works correctly!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_logger_fix()) 