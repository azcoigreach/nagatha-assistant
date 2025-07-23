"""
Celery-based Event Bus for Nagatha Assistant.

This module provides a Celery-based event bus that maintains the same
interface as the original event bus but uses Celery tasks for processing.
"""

import asyncio
import fnmatch
import logging
import threading
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable, Union
from datetime import datetime, timezone

from nagatha_assistant.core.event import Event, EventHandler, EventPriority, SyncEventHandler, AsyncEventHandler
from nagatha_assistant.core.celery_event_storage import (
    add_subscriber, remove_subscriber, get_subscribers, get_event_history
)

logger = logging.getLogger(__name__)


class CeleryEventBusError(Exception):
    """Base exception for Celery event bus related errors."""
    pass


class CeleryEventSubscription:
    """Represents a subscription to events in the Celery event bus."""
    
    def __init__(self, pattern: str, handler: EventHandler, 
                 priority_filter: Optional[EventPriority] = None,
                 source_filter: Optional[str] = None):
        self.pattern = pattern
        self.handler = handler
        self.priority_filter = priority_filter
        self.source_filter = source_filter
        self.subscription_id = None  # Will be set by the event bus
        self.handler_task_name = self._create_handler_task_name()
        
    def _create_handler_task_name(self) -> str:
        """Create a unique Celery task name for this handler."""
        handler_id = id(self.handler)
        return f"nagatha_assistant.core.celery_event_handlers.handler_{handler_id}"
        
    def matches(self, event: Event) -> bool:
        """Check if this subscription matches the given event."""
        # Check event type pattern
        if not fnmatch.fnmatch(event.event_type, self.pattern):
            return False
            
        # Check priority filter
        if self.priority_filter is not None and event.priority > self.priority_filter:
            return False
            
        # Check source filter
        if self.source_filter is not None and event.source != self.source_filter:
            return False
            
        return True


class CeleryEventBus:
    """
    Celery-based event bus that maintains compatibility with the original event bus API.
    
    Events are processed through Celery tasks instead of in-memory queues.
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize the Celery event bus.
        
        Args:
            max_history: Maximum number of events to keep in history (handled by Redis)
        """
        self._subscriptions: Dict[str, CeleryEventSubscription] = {}
        self._lock = threading.RLock()
        self._running = False
        self._handler_registry = {}  # Maps handler task names to actual handlers
        
    async def start(self) -> None:
        """Start the Celery event bus."""
        with self._lock:
            if self._running:
                return
                
            self._running = True
            self._register_handler_tasks()
            logger.info("Celery event bus started")
    
    async def stop(self) -> None:
        """Stop the Celery event bus."""
        with self._lock:
            if not self._running:
                return
                
            self._running = False
            self._unregister_handler_tasks()
            logger.info("Celery event bus stopped")
    
    def subscribe(self, pattern: str, handler: EventHandler, 
                  priority_filter: Optional[EventPriority] = None,
                  source_filter: Optional[str] = None) -> int:
        """
        Subscribe to events matching the given pattern.
        
        Args:
            pattern: Glob pattern for event types (e.g., "agent.*", "mcp.tool.*")
            handler: Function to handle matching events
            priority_filter: Only receive events with this priority or higher
            source_filter: Only receive events from this source
            
        Returns:
            Subscription ID for later unsubscription
        """
        with self._lock:
            subscription = CeleryEventSubscription(pattern, handler, priority_filter, source_filter)
            
            # Register handler as a Celery task
            self._register_handler(subscription)
            
            # Add to Redis-based subscriber storage
            subscription_id = add_subscriber(
                pattern, 
                subscription.handler_task_name,
                priority_filter.value if priority_filter else None,
                source_filter
            )
            
            subscription.subscription_id = subscription_id
            self._subscriptions[subscription_id] = subscription
            
            logger.debug(f"Subscribed to pattern '{pattern}' with ID {subscription_id}")
            return int(subscription_id, 16) if isinstance(subscription_id, str) else subscription_id
    
    def unsubscribe(self, subscription_id: int) -> bool:
        """
        Unsubscribe from events using the subscription ID.
        
        Args:
            subscription_id: ID returned from subscribe()
            
        Returns:
            True if subscription was found and removed
        """
        with self._lock:
            subscription_id_str = str(subscription_id) if isinstance(subscription_id, int) else subscription_id
            
            if subscription_id_str in self._subscriptions:
                subscription = self._subscriptions[subscription_id_str]
                
                # Remove from Redis storage
                success = remove_subscriber(subscription.subscription_id)
                
                if success:
                    # Unregister handler task
                    self._unregister_handler(subscription)
                    del self._subscriptions[subscription_id_str]
                    logger.debug(f"Unsubscribed subscription ID {subscription_id}")
                    return True
            
            return False
    
    def unsubscribe_handler(self, handler: EventHandler) -> int:
        """
        Unsubscribe all subscriptions for a specific handler.
        
        Args:
            handler: The handler function to remove
            
        Returns:
            Number of subscriptions removed
        """
        with self._lock:
            removed_count = 0
            subscriptions_to_remove = []
            
            for subscription_id, subscription in self._subscriptions.items():
                if subscription.handler == handler:
                    subscriptions_to_remove.append(subscription_id)
            
            for subscription_id in subscriptions_to_remove:
                if self.unsubscribe(subscription_id):
                    removed_count += 1
                    
            if removed_count > 0:
                logger.debug(f"Unsubscribed {removed_count} subscriptions for handler")
            return removed_count
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all matching subscribers.
        
        Args:
            event: The event to publish
        """
        if not self._running:
            raise CeleryEventBusError("Celery event bus is not running")
        
        try:
            # Import here to avoid circular imports
            from nagatha_assistant.core.celery_tasks import publish_event_task
            
            # Publish event through Celery
            publish_event_task.delay(
                event.event_type,
                event.data,
                event.priority.value,
                event.source,
                event.correlation_id
            )
            
            logger.debug(f"Published event: {event.event_type} (ID: {event.event_id})")
            
        except Exception as e:
            logger.error(f"Error publishing event {event.event_type}: {e}")
            raise CeleryEventBusError(f"Failed to publish event: {e}")
    
    def publish_sync(self, event: Event) -> None:
        """
        Synchronously publish an event (creates task for async processing).
        
        Args:
            event: The event to publish
        """
        if not self._running:
            logger.warning(f"Celery event bus not running, discarding event: {event.event_type}")
            return
            
        try:
            # Import here to avoid circular imports
            from nagatha_assistant.core.celery_tasks import publish_event_task
            
            # Publish event through Celery
            publish_event_task.delay(
                event.event_type,
                event.data,
                event.priority.value,
                event.source,
                event.correlation_id
            )
            
        except Exception as e:
            logger.warning(f"Failed to publish event sync: {e}")
    
    def get_subscriptions(self) -> List[Dict[str, Any]]:
        """Get information about current subscriptions."""
        with self._lock:
            return [
                {
                    "id": sub.subscription_id,
                    "pattern": sub.pattern,
                    "priority_filter": sub.priority_filter,
                    "source_filter": sub.source_filter,
                    "handler": str(sub.handler),
                    "handler_task": sub.handler_task_name
                }
                for sub in self._subscriptions.values()
            ]
    
    def get_event_history(self, limit: Optional[int] = None, 
                         event_type_pattern: Optional[str] = None) -> List[Event]:
        """
        Get event history from Redis storage.
        
        Args:
            limit: Maximum number of events to return (most recent first)
            event_type_pattern: Glob pattern to filter event types
            
        Returns:
            List of events in reverse chronological order
        """
        try:
            # Get events from Redis
            redis_events = get_event_history(limit or 100, event_type_pattern)
            
            # Convert to Event objects
            events = []
            for event_data in redis_events:
                try:
                    event = Event(
                        event_type=event_data['event_type'],
                        data=event_data.get('data', {}),
                        priority=EventPriority(int(event_data.get('priority', 2))),
                        source=event_data.get('source'),
                        correlation_id=event_data.get('correlation_id'),
                        event_id=event_data['event_id']
                    )
                    if 'timestamp' in event_data:
                        event.timestamp = datetime.fromisoformat(event_data['timestamp'])
                    events.append(event)
                except Exception as e:
                    logger.warning(f"Error converting event data: {e}")
                    
            return events
            
        except Exception as e:
            logger.error(f"Error getting event history: {e}")
            return []
    
    def clear_history(self) -> None:
        """Clear the event history."""
        try:
            from nagatha_assistant.core.celery_event_storage import get_redis_client
            redis_client = get_redis_client()
            redis_client.delete("event_history")
            logger.debug("Event history cleared")
        except Exception as e:
            logger.error(f"Error clearing event history: {e}")
    
    def _register_handler_tasks(self) -> None:
        """Register all handler tasks with Celery."""
        for subscription in self._subscriptions.values():
            self._register_handler(subscription)
    
    def _unregister_handler_tasks(self) -> None:
        """Unregister all handler tasks."""
        for subscription in self._subscriptions.values():
            self._unregister_handler(subscription)
    
    def _register_handler(self, subscription: CeleryEventSubscription) -> None:
        """Register a handler as a Celery task."""
        try:
            from nagatha_assistant.celery_app import app
            
            # Store handler in registry
            self._handler_registry[subscription.handler_task_name] = subscription.handler
            
            # Create a Celery task for this handler
            def create_handler_task(handler_func, task_name):
                @app.task(bind=True, name=task_name)
                def handler_task(self, event_metadata: Dict[str, Any]):
                    try:
                        # Convert event metadata back to Event object
                        event = Event(
                            event_type=event_metadata['event_type'],
                            data=event_metadata.get('data', {}),
                            priority=EventPriority(int(event_metadata.get('priority', 2))),
                            source=event_metadata.get('source'),
                            correlation_id=event_metadata.get('correlation_id'),
                            event_id=event_metadata['event_id']
                        )
                        if 'timestamp' in event_metadata:
                            event.timestamp = datetime.fromisoformat(event_metadata['timestamp'])
                        
                        # Call the handler
                        if asyncio.iscoroutinefunction(handler_func):
                            # Async handler
                            return asyncio.run(handler_func(event))
                        else:
                            # Sync handler
                            return handler_func(event)
                            
                    except Exception as e:
                        logger.error(f"Error in handler task {task_name}: {e}")
                        return {'success': False, 'error': str(e)}
                
                return handler_task
            
            # Register the task
            task = create_handler_task(subscription.handler, subscription.handler_task_name)
            
            logger.debug(f"Registered handler task: {subscription.handler_task_name}")
            
        except Exception as e:
            logger.error(f"Error registering handler task: {e}")
    
    def _unregister_handler(self, subscription: CeleryEventSubscription) -> None:
        """Unregister a handler task."""
        try:
            # Remove from registry
            if subscription.handler_task_name in self._handler_registry:
                del self._handler_registry[subscription.handler_task_name]
            
            logger.debug(f"Unregistered handler task: {subscription.handler_task_name}")
            
        except Exception as e:
            logger.error(f"Error unregistering handler task: {e}")


# Global Celery event bus instance
_celery_event_bus: Optional[CeleryEventBus] = None
_bus_lock = threading.Lock()


def get_celery_event_bus() -> CeleryEventBus:
    """Get the global Celery event bus instance (singleton pattern)."""
    global _celery_event_bus
    
    if _celery_event_bus is None:
        with _bus_lock:
            if _celery_event_bus is None:
                _celery_event_bus = CeleryEventBus()
    
    return _celery_event_bus


async def ensure_celery_event_bus_started() -> CeleryEventBus:
    """Ensure the global Celery event bus is started and return it."""
    bus = get_celery_event_bus()
    await bus.start()
    return bus


async def shutdown_celery_event_bus() -> None:
    """Shutdown the global Celery event bus."""
    global _celery_event_bus
    
    if _celery_event_bus is not None:
        await _celery_event_bus.stop()
        with _bus_lock:
            _celery_event_bus = None