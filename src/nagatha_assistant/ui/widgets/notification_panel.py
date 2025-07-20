"""
Notification and Task Panel Widget for Nagatha Assistant Dashboard.

This widget displays:
- Recent notifications and alerts
- Active tasks and reminders
- System messages and events
- User-actionable items
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from textual.app import ComposeResult
from textual.widgets import Static, ListView, ListItem, Label, Button, Collapsible
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.binding import Binding

from nagatha_assistant.core.event_bus import get_event_bus, Event
from nagatha_assistant.core.event import StandardEventTypes, EventPriority
from nagatha_assistant.core import agent
from nagatha_assistant.db_models import Task, Reminder
from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


class NotificationItem:
    """Represents a notification item in the panel."""
    
    def __init__(self, 
                 id: str,
                 title: str,
                 message: str,
                 type: str = "info",  # info, warning, error, success, task, reminder
                 timestamp: Optional[datetime] = None,
                 actionable: bool = False,
                 action_label: str = "",
                 priority: EventPriority = EventPriority.NORMAL):
        self.id = id
        self.title = title
        self.message = message
        self.type = type
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.actionable = actionable
        self.action_label = action_label
        self.priority = priority
        self.read = False
    
    def get_icon(self) -> str:
        """Get the icon for this notification type."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
            "task": "📋",
            "reminder": "⏰",
            "system": "⚙️",
            "mcp": "🔧"
        }
        return icons.get(self.type, "📬")
    
    def get_display_text(self) -> str:
        """Get formatted display text for the notification."""
        time_str = self.timestamp.strftime("%H:%M")
        icon = self.get_icon()
        status = "" if self.read else "🔵 "
        
        return f"{status}{icon} {time_str} - {self.title}"


class NotificationPanel(Vertical):
    """
    Panel that displays notifications, tasks, and actionable items.
    """
    
    BINDINGS = [
        Binding("r", "mark_all_read", "Mark all read", show=False),
        Binding("c", "clear_old", "Clear old", show=False),
    ]
    
    # Reactive attributes
    unread_count: reactive[int] = reactive(0)
    total_notifications: reactive[int] = reactive(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.notifications: List[NotificationItem] = []
        self.max_notifications = 50
        self.event_subscription_id = None
        
    def compose(self) -> ComposeResult:
        """Compose the notification panel."""
        
        # Header with counters
        with Horizontal(id="notification_header"):
            yield Static("📬 Notifications", id="notification_title")
            yield Static("0 unread", id="unread_counter", classes="counter")
            
        # Quick actions
        with Horizontal(id="notification_actions", classes="action-bar"):
            yield Button("Mark All Read", variant="default", id="mark_read_btn", classes="small-btn")
            yield Button("Clear Old", variant="default", id="clear_old_btn", classes="small-btn")
            
        # Active notifications list
        with Collapsible(title="Recent Activity", collapsed=False, id="recent_notifications"):
            yield ListView(id="notifications_list")
            
        # Active tasks section
        with Collapsible(title="Active Tasks", collapsed=False, id="active_tasks"):
            yield ListView(id="tasks_list")
            yield Static("No active tasks", id="no_tasks", classes="empty-state")
            
        # Reminders section
        with Collapsible(title="Reminders", collapsed=True, id="reminders_section"):
            yield ListView(id="reminders_list")
            yield Static("No pending reminders", id="no_reminders", classes="empty-state")
    
    async def on_mount(self) -> None:
        """Initialize the notification panel when mounted."""
        try:
            # Subscribe to events for real-time notifications
            event_bus = get_event_bus()
            self.event_subscription_id = event_bus.subscribe(
                pattern="*",
                handler=self._handle_event,
                priority_filter=EventPriority.HIGH
            )
            
            # Load initial data
            await self._refresh_all_data()
            
            # Set up periodic refresh for tasks and reminders
            self.set_interval(60, self._refresh_tasks_and_reminders)  # Every minute
            
        except Exception as e:
            logger.error(f"Error initializing notification panel: {e}")
            await self._add_system_notification("Initialization Error", str(e), "error")
    
    async def on_unmount(self) -> None:
        """Clean up when the widget is unmounted."""
        if self.event_subscription_id:
            event_bus = get_event_bus()
            event_bus.unsubscribe(self.event_subscription_id)
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming events and convert to notifications."""
        try:
            # Convert certain events to notifications
            if event.event_type == StandardEventTypes.AGENT_MESSAGE_RECEIVED:
                await self._add_agent_notification(event)
            elif event.event_type.startswith("mcp."):
                await self._add_mcp_notification(event)
            elif event.event_type.startswith("system."):
                await self._add_system_event_notification(event)
            elif event.event_type.startswith("task."):
                await self._add_task_notification(event)
            elif event.event_type.startswith("reminder."):
                await self._add_reminder_notification(event)
            elif event.priority <= EventPriority.HIGH:
                # Convert high-priority events to notifications
                await self._add_generic_notification(event)
                
        except Exception as e:
            logger.error(f"Error handling event in notification panel: {e}")
    
    async def _add_agent_notification(self, event: Event) -> None:
        """Add notification for agent messages."""
        session_id = event.data.get("session_id", "Unknown")
        message_content = event.data.get("content", "")[:100] + "..."
        
        notification = NotificationItem(
            id=f"agent_{event.event_id}",
            title=f"Message in Session {session_id}",
            message=message_content,
            type="info",
            timestamp=event.timestamp
        )
        
        await self._add_notification(notification)
    
    async def _add_mcp_notification(self, event: Event) -> None:
        """Add notification for MCP events."""
        server_name = event.data.get("server_name", "Unknown")
        
        if event.event_type == StandardEventTypes.MCP_SERVER_CONNECTED:
            notification = NotificationItem(
                id=f"mcp_{event.event_id}",
                title=f"MCP Server Connected",
                message=f"Server '{server_name}' is now available",
                type="success",
                timestamp=event.timestamp
            )
        elif event.event_type == StandardEventTypes.MCP_SERVER_DISCONNECTED:
            notification = NotificationItem(
                id=f"mcp_{event.event_id}",
                title=f"MCP Server Disconnected",
                message=f"Server '{server_name}' is no longer available",
                type="warning",
                timestamp=event.timestamp
            )
        elif event.event_type == StandardEventTypes.MCP_TOOL_CALLED:
            tool_name = event.data.get("tool_name", "Unknown")
            notification = NotificationItem(
                id=f"mcp_{event.event_id}",
                title=f"Tool Executed",
                message=f"Called '{tool_name}' on '{server_name}'",
                type="mcp",
                timestamp=event.timestamp
            )
        else:
            return  # Don't create notification for other MCP events
            
        await self._add_notification(notification)
    
    async def _add_system_event_notification(self, event: Event) -> None:
        """Add notification for system events."""
        if event.event_type == StandardEventTypes.SYSTEM_STARTUP:
            notification = NotificationItem(
                id=f"system_{event.event_id}",
                title="System Started",
                message="Nagatha Assistant is now running",
                type="success",
                timestamp=event.timestamp
            )
        elif event.event_type == StandardEventTypes.SYSTEM_SHUTDOWN:
            notification = NotificationItem(
                id=f"system_{event.event_id}",
                title="System Shutdown",
                message="Nagatha Assistant is shutting down",
                type="warning",
                timestamp=event.timestamp
            )
        else:
            return
            
        await self._add_notification(notification)
    
    async def _add_task_notification(self, event: Event) -> None:
        """Add notification for task events."""
        task_title = event.data.get("title", "Unknown Task")
        
        if event.event_type == StandardEventTypes.TASK_CREATED:
            notification = NotificationItem(
                id=f"task_{event.event_id}",
                title="New Task Created",
                message=f"Task: {task_title}",
                type="task",
                timestamp=event.timestamp,
                actionable=True,
                action_label="View Task"
            )
        elif event.event_type == StandardEventTypes.TASK_COMPLETED:
            notification = NotificationItem(
                id=f"task_{event.event_id}",
                title="Task Completed",
                message=f"Completed: {task_title}",
                type="success",
                timestamp=event.timestamp
            )
        else:
            return
            
        await self._add_notification(notification)
    
    async def _add_reminder_notification(self, event: Event) -> None:
        """Add notification for reminder events."""
        reminder_text = event.data.get("reminder_text", "Unknown Reminder")
        
        notification = NotificationItem(
            id=f"reminder_{event.event_id}",
            title="Reminder",
            message=reminder_text,
            type="reminder",
            timestamp=event.timestamp,
            actionable=True,
            action_label="Acknowledge",
            priority=EventPriority.HIGH
        )
        
        await self._add_notification(notification)
    
    async def _add_generic_notification(self, event: Event) -> None:
        """Add notification for generic high-priority events."""
        event_type_parts = event.event_type.split('.')
        title = f"{event_type_parts[0].title()} Event"
        
        notification = NotificationItem(
            id=f"generic_{event.event_id}",
            title=title,
            message=f"Event: {event.event_type}",
            type="info",
            timestamp=event.timestamp,
            priority=event.priority
        )
        
        await self._add_notification(notification)
    
    async def _add_system_notification(self, title: str, message: str, type: str = "info") -> None:
        """Add a system notification directly."""
        notification = NotificationItem(
            id=f"system_{datetime.now().timestamp()}",
            title=title,
            message=message,
            type=type,
            timestamp=datetime.now(timezone.utc)
        )
        
        await self._add_notification(notification)
    
    async def _add_notification(self, notification: NotificationItem) -> None:
        """Add a notification to the panel."""
        try:
            # Add to list
            self.notifications.insert(0, notification)  # Most recent first
            
            # Limit total notifications
            if len(self.notifications) > self.max_notifications:
                self.notifications = self.notifications[:self.max_notifications]
            
            # Update counters
            self.unread_count = sum(1 for n in self.notifications if not n.read)
            self.total_notifications = len(self.notifications)
            
            # Update display
            await self._update_notifications_display()
            
        except Exception as e:
            logger.error(f"Error adding notification: {e}")
    
    async def _update_notifications_display(self) -> None:
        """Update the notifications list display."""
        try:
            notifications_list = self.query_one("#notifications_list", ListView)
            notifications_list.clear()
            
            # Show recent notifications (last 10)
            recent_notifications = self.notifications[:10]
            
            for notification in recent_notifications:
                display_text = notification.get_display_text()
                list_item = ListItem(Label(display_text))
                list_item.set_reactive("notification_id", notification.id)
                notifications_list.append(list_item)
            
            # Update counter
            unread_counter = self.query_one("#unread_counter", Static)
            unread_counter.update(f"{self.unread_count} unread")
            
        except Exception as e:
            logger.error(f"Error updating notifications display: {e}")
    
    async def _refresh_tasks_and_reminders(self) -> None:
        """Refresh the tasks and reminders sections."""
        try:
            await asyncio.gather(
                self._update_tasks_display(),
                self._update_reminders_display(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error refreshing tasks and reminders: {e}")
    
    async def _update_tasks_display(self) -> None:
        """Update the active tasks display."""
        try:
            tasks_list = self.query_one("#tasks_list", ListView)
            no_tasks = self.query_one("#no_tasks", Static)
            
            tasks_list.clear()
            
            # For now, show placeholder - in real implementation, would query database
            # active_tasks = await agent.get_active_tasks()
            active_tasks = []  # Placeholder
            
            if active_tasks:
                no_tasks.add_class("hidden")
                tasks_list.remove_class("hidden")
                
                for task in active_tasks:
                    due_str = task.due_date.strftime("%m/%d") if hasattr(task, 'due_date') and task.due_date else "No due date"
                    task_text = f"📋 {task.title} (Due: {due_str})"
                    tasks_list.append(ListItem(Label(task_text)))
            else:
                no_tasks.remove_class("hidden")
                tasks_list.add_class("hidden")
                
        except Exception as e:
            logger.error(f"Error updating tasks display: {e}")
    
    async def _update_reminders_display(self) -> None:
        """Update the reminders display."""
        try:
            reminders_list = self.query_one("#reminders_list", ListView)
            no_reminders = self.query_one("#no_reminders", Static)
            
            reminders_list.clear()
            
            # For now, show placeholder - in real implementation, would query database
            # pending_reminders = await agent.get_pending_reminders()
            pending_reminders = []  # Placeholder
            
            if pending_reminders:
                no_reminders.add_class("hidden")
                reminders_list.remove_class("hidden")
                
                for reminder in pending_reminders:
                    time_str = reminder.trigger_time.strftime("%H:%M") if hasattr(reminder, 'trigger_time') else "Unknown"
                    reminder_text = f"⏰ {time_str} - {reminder.reminder_text}"
                    reminders_list.append(ListItem(Label(reminder_text)))
            else:
                no_reminders.remove_class("hidden")
                reminders_list.add_class("hidden")
                
        except Exception as e:
            logger.error(f"Error updating reminders display: {e}")
    
    async def _refresh_all_data(self) -> None:
        """Refresh all data in the panel."""
        await asyncio.gather(
            self._update_notifications_display(),
            self._update_tasks_display(),
            self._update_reminders_display(),
            return_exceptions=True
        )
    
    def action_mark_all_read(self) -> None:
        """Mark all notifications as read."""
        for notification in self.notifications:
            notification.read = True
        
        self.unread_count = 0
        self.call_later(self._update_notifications_display)
    
    def action_clear_old(self) -> None:
        """Clear old read notifications."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        self.notifications = [
            n for n in self.notifications 
            if not n.read or n.timestamp > cutoff_time or n.priority <= EventPriority.HIGH
        ]
        
        self.total_notifications = len(self.notifications)
        self.unread_count = sum(1 for n in self.notifications if not n.read)
        self.call_later(self._update_notifications_display)
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "mark_read_btn":
            self.action_mark_all_read()
        elif event.button.id == "clear_old_btn":
            self.action_clear_old()
    
    def watch_unread_count(self, count: int) -> None:
        """React to unread count changes."""
        # Could trigger visual alerts or sounds
        pass