#!/usr/bin/env python3
"""
Screenshot test for the Nagatha Assistant Dashboard UI.
"""

import asyncio
import os
import sys
from pathlib import Path

# Set dummy API key for testing
os.environ["OPENAI_API_KEY"] = "dummy-key-for-testing"
os.environ["LOG_LEVEL"] = "WARNING"  # Reduce log noise

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from nagatha_assistant.ui.dashboard import DashboardApp

class ScreenshotDashboardApp(DashboardApp):
    """Version of the dashboard that takes a screenshot."""
    
    async def on_mount(self) -> None:
        """Initialize and take screenshot."""
        try:
            # Call parent mount
            await super().on_mount()
            
            # Add some test content
            self._update_conversation_area("🎯 Dashboard Screenshot Test")
            self._update_conversation_area("📊 All panels are functional and displaying real-time data")
            self._update_conversation_area("🔧 Use Ctrl+1-4 to navigate between panels")
            self._update_conversation_area("💬 Type commands here and press Enter")
            
            # Wait a moment for rendering
            await asyncio.sleep(2)
            
            # Take screenshot
            screenshot_path = "dashboard_screenshot.png"
            try:
                # This will save a screenshot of the current screen
                self.save_screenshot(screenshot_path)
                print(f"Screenshot saved to: {screenshot_path}")
            except Exception as e:
                print(f"Could not save screenshot: {e}")
            
            # Exit after screenshot
            self.set_timer(1.0, self.exit)
            
        except Exception as e:
            print(f"Error during screenshot test: {e}")
            self.exit(1)

async def screenshot_test():
    """Run the dashboard screenshot test."""
    print("Starting Nagatha Dashboard screenshot test...")
    print("This will capture the dashboard interface...")
    
    try:
        app = ScreenshotDashboardApp()
        await app.run_async()
        print("Screenshot test completed!")
        return 0
    except Exception as e:
        print(f"Screenshot test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(screenshot_test())
    sys.exit(exit_code)