"""
UI Widgets package for Nagatha Assistant dashboard.

This package contains reusable widget components for the dashboard interface.
"""

from .status_panel import StatusPanel
from .command_panel import CommandPanel
from .notification_panel import NotificationPanel
from .resource_monitor import ResourceMonitor

__all__ = [
    "StatusPanel",
    "CommandPanel", 
    "NotificationPanel",
    "ResourceMonitor"
]