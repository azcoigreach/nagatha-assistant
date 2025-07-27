"""
Central Event Bus System for Nagatha Assistant.

This module provides a thread-safe, asynchronous event bus with support for:
- Publish/subscribe pattern
- Event priorities
- Event history tracking
- Synchronous and asynchronous handlers
- Wildcard subscriptions
- Thread safety
"""

import asyncio
import fnmatch
import threading
import weakref
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable, Union
from datetime import datetime, timezone

from .event import Event, EventHandler, EventPriority, SyncEventHandler, AsyncEventHandler
from nagatha_assistant.utils.logger import get_logger

logger = get_logger()


class EventBusError(Exception):
    """Base exception for event bus related errors."""
    pass


class EventSubscription:
    """Represents a subscription to events."""
    
    def __init__(self, pattern: str, handler: EventHandler, 
                 priority_filter: Optional[EventPriority] = None,
                 source_filter: Optional[str] = None):
        self.pattern = pattern
        self.handler = handler
        self.priority_filter = priority_filter
        self.source_filter = source_filter
        self.subscription_id = id(self)
        
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


class EventBus:
    """
    Central event bus for asynchronous publish/subscribe communication.
    
    Features:
    - Thread-safe operations
    - Asynchronous and synchronous event handlers
    - Event priority ordering
    - Wildcard pattern matching for event types
    - Event history tracking
    - Filtering by priority and source
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize the event bus.
        
        Args:
            max_history: Maximum number of events to keep in history
        """
        self._subscriptions: List[EventSubscription] = []
        self._event_history: deque = deque(maxlen=max_history)
        self._lock = threading.RLock()
        self._running = False
        self._event_queue: Optional[asyncio.Queue] = None
        self._processor_task: Optional[asyncio.Task] = None
        
        # Weak references to cleanup handlers when objects are garbage collected
        self._weak_refs: Set[weakref.ref] = set()
        
    async def start(self) -> None:
        """Start the event bus processing."""
        async with asyncio.Lock():
            if self._running:
                return
                
            self._running = True
            self._event_queue = asyncio.Queue()
            self._processor_task = asyncio.create_task(self._process_events())
            logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event bus processing."""
        async with asyncio.Lock():
            if not self._running:
                return
                
            self._running = False
            
            if self._event_queue:
                await self._event_queue.put(None)  # Signal to stop processing
                
            if self._processor_task:
                try:
                    await asyncio.wait_for(self._processor_task, timeout=5.0)
                except asyncio.TimeoutError:
                    self._processor_task.cancel()
                    try:
                        await self._processor_task
                    except asyncio.CancelledError:
                        pass
                        
            self._event_queue = None
            self._processor_task = None
            logger.info("Event bus stopped")
    
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
            subscription = EventSubscription(pattern, handler, priority_filter, source_filter)
            self._subscriptions.append(subscription)
            
            # Create weak reference for cleanup
            if hasattr(handler, '__self__'):
                weak_ref = weakref.ref(handler.__self__, self._cleanup_dead_refs)
                self._weak_refs.add(weak_ref)
            
            logger.debug(f"Subscribed to pattern '{pattern}' with ID {subscription.subscription_id}")
            return subscription.subscription_id
    
    def unsubscribe(self, subscription_id: int) -> bool:
        """
        Unsubscribe from events using the subscription ID.
        
        Args:
            subscription_id: ID returned from subscribe()
            
        Returns:
            True if subscription was found and removed
        """
        with self._lock:
            for i, subscription in enumerate(self._subscriptions):
                if subscription.subscription_id == subscription_id:
                    del self._subscriptions[i]
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
            self._subscriptions = [
                sub for sub in self._subscriptions
                if sub.handler != handler or (removed_count := removed_count + 1, False)[1]
            ]
            if removed_count > 0:
                logger.debug(f"Unsubscribed {removed_count} subscriptions for handler")
            return removed_count
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all matching subscribers.
        
        Args:
            event: The event to publish
        """
        if not self._running or not self._event_queue:
            raise EventBusError("Event bus is not running")
            
        # Add to history immediately
        with self._lock:
            self._event_history.append(event)
        
        # Queue for processing
        await self._event_queue.put(event)
        logger.debug(f"Published event: {event.event_type} (ID: {event.event_id})")
    
    def publish_sync(self, event: Event) -> None:
        """
        Synchronously publish an event (creates task for async processing).
        
        Args:
            event: The event to publish
        """
        if not self._running:
            logger.warning(f"Event bus not running, discarding event: {event.event_type}")
            return
            
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            logger.warning(f"No event loop available, discarding event: {event.event_type}")
    
    def get_subscriptions(self) -> List[Dict[str, Any]]:
        """Get information about current subscriptions."""
        with self._lock:
            return [
                {
                    "id": sub.subscription_id,
                    "pattern": sub.pattern,
                    "priority_filter": sub.priority_filter,
                    "source_filter": sub.source_filter,
                    "handler": str(sub.handler)
                }
                for sub in self._subscriptions
            ]
    
    def get_event_history(self, limit: Optional[int] = None, 
                         event_type_pattern: Optional[str] = None) -> List[Event]:
        """
        Get event history, optionally filtered.
        
        Args:
            limit: Maximum number of events to return (most recent first)
            event_type_pattern: Glob pattern to filter event types
            
        Returns:
            List of events in reverse chronological order
        """
        with self._lock:
            events = list(self._event_history)
            
            if event_type_pattern:
                events = [e for e in events if fnmatch.fnmatch(e.event_type, event_type_pattern)]
            
            # Return most recent first
            events.reverse()
            
            if limit:
                events = events[:limit]
                
            return events
    
    def clear_history(self) -> None:
        """Clear the event history."""
        with self._lock:
            self._event_history.clear()
            logger.debug("Event history cleared")
    
    async def _process_events(self) -> None:
        """Process events from the queue."""
        logger.debug("Event processor started")
        
        while self._running:
            try:
                # Wait for event (or stop signal)
                event = await self._event_queue.get()
                if event is None:  # Stop signal
                    break
                    
                await self._dispatch_event(event)
                
            except Exception as e:
                logger.exception(f"Error processing event: {e}")
        
        logger.debug("Event processor stopped")
    
    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch an event to all matching subscribers."""
        # Get matching subscriptions (thread-safe copy)
        with self._lock:
            matching_subs = [sub for sub in self._subscriptions if sub.matches(event)]
        
        if not matching_subs:
            logger.debug(f"No subscribers for event: {event.event_type}")
            return
        
        # Sort by priority for processing order
        matching_subs.sort(key=lambda sub: (
            sub.priority_filter or EventPriority.NORMAL,
            sub.subscription_id
        ))
        
        # Process handlers
        tasks = []
        for subscription in matching_subs:
            try:
                handler = subscription.handler
                
                if asyncio.iscoroutinefunction(handler):
                    # Async handler
                    task = asyncio.create_task(handler(event))
                    tasks.append(task)
                else:
                    # Sync handler - run in thread pool to avoid blocking
                    task = asyncio.create_task(
                        asyncio.get_event_loop().run_in_executor(None, handler, event)
                    )
                    tasks.append(task)
                    
            except Exception as e:
                logger.exception(f"Error calling event handler: {e}")
        
        # Wait for all handlers to complete
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.exception(f"Error in event handler execution: {e}")
    
    def _cleanup_dead_refs(self, weak_ref: weakref.ref) -> None:
        """Clean up subscriptions for garbage collected objects."""
        with self._lock:
            self._weak_refs.discard(weak_ref)
            # Note: In a full implementation, we'd also remove subscriptions
            # for the dead object, but this requires tracking which subscriptions
            # belong to which objects.


# Global event bus instance
_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get the global event bus instance (singleton pattern)."""
    global _event_bus
    
    if _event_bus is None:
        with _bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    
    return _event_bus


async def ensure_event_bus_started() -> EventBus:
    """Ensure the global event bus is started and return it."""
    bus = get_event_bus()
    await bus.start()
    return bus


async def shutdown_event_bus() -> None:
    """Shutdown the global event bus."""
    global _event_bus
    
    if _event_bus is not None:
        await _event_bus.stop()
        with _bus_lock:
            _event_bus = None