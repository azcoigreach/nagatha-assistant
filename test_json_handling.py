#!/usr/bin/env python3

import json
import asyncio
from src.nagatha_assistant.core.mcp_manager import MCPManager

async def test_json_handling():
    """Test the JSON handling improvements."""
    
    # Test argument sanitization
    test_args = {
        "text": "test message",
        "number": 42,
        "complex": {"nested": "value"},
        "non_serializable": lambda x: x  # This should be converted to string
    }
    
    print("Testing argument sanitization...")
    try:
        json.dumps(test_args)
        print("✅ Original arguments are JSON serializable")
    except (TypeError, ValueError) as e:
        print(f"❌ Original arguments are not JSON serializable: {e}")
        
        # Test sanitization
        sanitized_args = {}
        for key, value in test_args.items():
            try:
                json.dumps(value)
                sanitized_args[key] = value
            except (TypeError, ValueError):
                sanitized_args[key] = str(value)
        
        print(f"✅ Sanitized arguments: {sanitized_args}")
        try:
            json.dumps(sanitized_args)
            print("✅ Sanitized arguments are JSON serializable")
        except (TypeError, ValueError) as e:
            print(f"❌ Sanitized arguments still not serializable: {e}")
    
    print("\nTesting result handling...")
    test_results = [
        "simple string",
        42,
        {"key": "value"},
        None,
        ["list", "of", "items"]
    ]
    
    for result in test_results:
        try:
            json.dumps(result)
            print(f"✅ Result '{result}' is JSON serializable")
        except (TypeError, ValueError) as e:
            print(f"❌ Result '{result}' is not JSON serializable: {e}")
            str_result = str(result)
            print(f"✅ Converted to string: '{str_result}'")

if __name__ == "__main__":
    asyncio.run(test_json_handling()) 