#!/usr/bin/env python3
"""
Test script for the Nagatha Assistant Dashboard UI.

This script runs the dashboard for a short time to verify functionality.
"""

import asyncio
import os
import sys
import signal
from pathlib import Path

# Set dummy API key for testing
os.environ["OPENAI_API_KEY"] = "dummy-key-for-testing"
os.environ["LOG_LEVEL"] = "INFO"

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from nagatha_assistant.ui.dashboard import DashboardApp

class TestDashboardApp(DashboardApp):
    """Test version of the dashboard that auto-exits after a short time."""
    
    async def on_mount(self) -> None:
        """Initialize and then exit after a short time."""
        try:
            # Call parent mount
            await super().on_mount()
            
            # Add test message
            self._update_conversation_area("🧪 Dashboard test completed successfully!")
            
            # Exit after 3 seconds
            self.set_timer(3.0, self.exit)
            
        except Exception as e:
            print(f"Error during test: {e}")
            self.exit(1)

async def test_dashboard():
    """Run the dashboard test."""
    print("Starting Nagatha Dashboard test...")
    
    try:
        app = TestDashboardApp()
        await app.run_async()
        print("Dashboard test completed successfully!")
        return 0
    except Exception as e:
        print(f"Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(test_dashboard())
    sys.exit(exit_code)