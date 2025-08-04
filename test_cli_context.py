#!/usr/bin/env python3
"""
Test script for CLI chat conversation context.
"""

import asyncio
import subprocess
import time
import sys


def test_cli_conversation():
    """Test conversation context using CLI chat."""
    print("🧠 Testing CLI Chat Conversation Context")
    print("=" * 50)
    
    try:
        # Test 1: Send first message
        print("\n📝 Test 1: Sending first message...")
        result1 = subprocess.run([
            "nagatha", "chat", "--new", "--message", 
            "My name is Alice and I'm 25 years old"
        ], capture_output=True, text=True, timeout=30)
        
        if result1.returncode == 0:
            print(f"✅ Response 1: {result1.stdout.strip()}")
        else:
            print(f"❌ Error 1: {result1.stderr}")
            return False
        
        # Extract session ID from the response (if available)
        session_id = None
        if "session" in result1.stdout.lower():
            # Try to extract session ID from output
            lines = result1.stdout.split('\n')
            for line in lines:
                if "session" in line.lower() and any(char.isdigit() for char in line):
                    # Extract the first number found
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        session_id = numbers[0]
                        break
        
        # Test 2: Send second message (should maintain context)
        print("\n📝 Test 2: Sending second message...")
        if session_id:
            cmd = ["nagatha", "chat", "--session-id", session_id, "--message", "What's my name?"]
        else:
            cmd = ["nagatha", "chat", "--new", "--message", "What's my name?"]
        
        result2 = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result2.returncode == 0:
            response2 = result2.stdout.strip()
            print(f"✅ Response 2: {response2}")
            
            # Check if context was maintained
            context_maintained = "Alice" in response2
            print(f"Context maintained: {context_maintained}")
            
            if context_maintained:
                print("✅ CLI chat is maintaining conversation context!")
            else:
                print("❌ CLI chat is not maintaining conversation context")
            
            return context_maintained
        else:
            print(f"❌ Error 2: {result2.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def test_interactive_cli():
    """Test interactive CLI chat mode."""
    print("\n🧠 Testing Interactive CLI Chat")
    print("=" * 50)
    
    print("This will start an interactive chat session.")
    print("You can test conversation context by:")
    print("1. Saying 'My name is Alice and I'm 25 years old'")
    print("2. Then asking 'What's my name?'")
    print("3. Press Ctrl+C to exit")
    
    try:
        # Start interactive mode
        subprocess.run(["nagatha", "chat", "--interactive"], timeout=60)
    except subprocess.TimeoutExpired:
        print("Interactive session ended")
    except KeyboardInterrupt:
        print("\nInteractive session interrupted")
    except Exception as e:
        print(f"❌ Interactive test failed: {e}")


def main():
    """Run the CLI chat tests."""
    print("🧠 Testing Nagatha CLI Chat Context")
    print("=" * 50)
    
    # Test single message mode
    success = test_cli_conversation()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    if success:
        print("✅ CLI chat conversation context test PASSED!")
        print("   This means the core conversation logic is working.")
        print("   Discord should also work if using the same logic.")
    else:
        print("❌ CLI chat conversation context test FAILED!")
        print("   The core conversation logic needs fixing.")
    
    # Ask if user wants to test interactive mode
    print("\nWould you like to test interactive CLI chat mode? (y/n)")
    try:
        response = input().lower().strip()
        if response in ['y', 'yes']:
            test_interactive_cli()
    except KeyboardInterrupt:
        print("\nSkipping interactive test")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 