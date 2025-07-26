#!/usr/bin/env python3
"""
Simple test to check if imports work correctly.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("Testing imports...")

try:
    print("Importing memory module...")
    from nagatha_assistant.core.memory import get_contextual_recall
    print("✅ Memory module imported successfully")
    
    print("Importing storage module...")
    from nagatha_assistant.core.storage import DatabaseStorageBackend
    print("✅ Storage module imported successfully")
    
    print("Importing agent module...")
    from nagatha_assistant.core.agent import start_session
    print("✅ Agent module imported successfully")
    
    print("🎉 All imports successful!")
    
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc() 