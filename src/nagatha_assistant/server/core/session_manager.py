"""
Unified Session Manager for cross-interface session awareness.

This module provides session management that allows Nagatha to maintain
a single consciousness across multiple interfaces (CLI, Discord, Dashboard).
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum

from nagatha_assistant.utils.logger import get_logger
from nagatha_assistant.core.memory import get_memory_manager, ensure_memory_manager_started
from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.core.event import StandardEventTypes


class InterfaceType(Enum):
    """Supported interface types."""
    CLI = "cli"
    DISCORD = "discord"
    DASHBOARD = "dashboard"
    WEBSOCKET = "websocket"
    REST = "rest"


@dataclass
class SessionContext:
    """Context information for a unified session."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    interfaces: Set[str] = field(default_factory=set)
    interface_contexts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    related_sessions: Set[str] = field(default_factory=set)
    is_active: bool = True
    
    def add_interface(self, interface: str, context: Dict[str, Any] = None):
        """Add an interface to this session."""
        self.interfaces.add(interface)
        if context:
            self.interface_contexts[interface] = context
        self.last_activity = datetime.now()
    
    def remove_interface(self, interface: str):
        """Remove an interface from this session."""
        self.interfaces.discard(interface)
        self.interface_contexts.pop(interface, None)
        self.last_activity = datetime.now()
    
    def is_empty(self) -> bool:
        """Check if session has no active interfaces."""
        return len(self.interfaces) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "interfaces": list(self.interfaces),
            "interface_contexts": self.interface_contexts,
            "related_sessions": list(self.related_sessions),
            "is_active": self.is_active
        }


class UnifiedSessionManager:
    """
    Manages unified sessions across multiple interfaces.
    
    This class provides:
    - Cross-interface session awareness
    - Session persistence and sharing
    - Memory integration across sessions
    - Session cleanup and expiration
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.memory_manager = None
        self.event_bus = None
        
        # Session storage
        self.active_sessions: Dict[str, SessionContext] = {}
        self.user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self.interface_sessions: Dict[str, str] = {}  # interface_id -> session_id
        
        # Configuration
        self.session_timeout = timedelta(hours=24)  # Sessions expire after 24 hours
        self.cleanup_interval = timedelta(minutes=30)  # Cleanup every 30 minutes
        
        # Background tasks
        self._cleanup_task = None
        self._running = False
    
    async def start(self):
        """Start the session manager."""
        self.logger.info("Starting Unified Session Manager")
        
        # Get dependencies
        self.memory_manager = await ensure_memory_manager_started()
        self.event_bus = get_event_bus()
        
        # Load existing sessions from memory
        await self._load_sessions_from_memory()
        
        # Start background cleanup task
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info(f"Unified Session Manager started with {len(self.active_sessions)} sessions")
    
    async def stop(self):
        """Stop the session manager."""
        self.logger.info("Stopping Unified Session Manager")
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save sessions to memory
        await self._save_sessions_to_memory()
        
        self.logger.info("Unified Session Manager stopped")
    
    async def get_or_create_session(
        self, 
        user_id: str, 
        interface: str, 
        interface_context: Dict[str, Any] = None
    ) -> str:
        """
        Get existing session for user or create new one.
        
        Args:
            user_id: Unique user identifier
            interface: Interface type (cli, discord, dashboard, etc.)
            interface_context: Context specific to this interface
            
        Returns:
            Session ID
        """
        # Check if user has active session in another interface
        existing_session = await self._find_user_session(user_id)
        
        if existing_session:
            # Join existing session
            session_id = existing_session.session_id
            existing_session.add_interface(interface, interface_context)
            
            # Update interface mapping
            interface_id = f"{interface}_{user_id}"
            self.interface_sessions[interface_id] = session_id
            
            self.logger.info(f"User {user_id} joined existing session {session_id} via {interface}")
            
            # Emit event (temporarily disabled)
            # await self._emit_session_event("session.joined", {
            #     "session_id": session_id,
            #     "user_id": user_id,
            #     "interface": interface,
            #     "existing_interfaces": list(existing_session.interfaces)
            # })
            
        else:
            # Create new session
            session_id = self._generate_session_id()
            session = SessionContext(
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.now(),
                last_activity=datetime.now()
            )
            session.add_interface(interface, interface_context)
            
            # Store session
            self.active_sessions[session_id] = session
            
            # Update user mapping
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = set()
            self.user_sessions[user_id].add(session_id)
            
            # Update interface mapping
            interface_id = f"{interface}_{user_id}"
            self.interface_sessions[interface_id] = session_id
            
            self.logger.info(f"Created new session {session_id} for user {user_id} via {interface}")
            
            # Emit event (temporarily disabled)
            # await self._emit_session_event("session.created", {
            #     "session_id": session_id,
            #     "user_id": user_id,
            #     "interface": interface
            # })
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session by ID."""
        session = self.active_sessions.get(session_id)
        if session and session.is_active:
            session.last_activity = datetime.now()
            return session
        return None
    
    async def get_user_sessions(self, user_id: str) -> List[SessionContext]:
        """Get all active sessions for a user."""
        session_ids = self.user_sessions.get(user_id, set())
        sessions = []
        
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    async def remove_interface_from_session(
        self, 
        session_id: str, 
        interface: str, 
        user_id: str
    ):
        """Remove an interface from a session."""
        session = await self.get_session(session_id)
        if not session:
            return
        
        session.remove_interface(interface)
        
        # Update interface mapping
        interface_id = f"{interface}_{user_id}"
        self.interface_sessions.pop(interface_id, None)
        
        self.logger.info(f"Removed interface {interface} from session {session_id}")
        
        # If session is empty, mark for cleanup
        if session.is_empty():
            session.is_active = False
            self.logger.info(f"Session {session_id} is now empty, marked for cleanup")
        
        # Emit event
        await self._emit_session_event("session.interface_removed", {
            "session_id": session_id,
            "user_id": user_id,
            "interface": interface,
            "remaining_interfaces": list(session.interfaces)
        })
    
    async def share_memory_across_sessions(self, session_id: str):
        """Enable memory sharing between related sessions."""
        session = await self.get_session(session_id)
        if not session:
            return
        
        # Get all sessions for this user
        user_sessions = await self.get_user_sessions(session.user_id)
        
        # Store cross-session awareness in memory
        await self.memory_manager.set_session_state(
            session_id,
            "related_sessions",
            [s.session_id for s in user_sessions if s.session_id != session_id]
        )
        
        # Store interface information
        await self.memory_manager.set_session_state(
            session_id,
            "active_interfaces",
            list(session.interfaces)
        )
        
        self.logger.debug(f"Updated cross-session memory for session {session_id}")
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        total_sessions = len(self.active_sessions)
        active_sessions = len([s for s in self.active_sessions.values() if s.is_active])
        total_users = len(self.user_sessions)
        total_interfaces = len(self.interface_sessions)
        
        # Interface breakdown
        interface_counts = {}
        for session in self.active_sessions.values():
            for interface in session.interfaces:
                interface_counts[interface] = interface_counts.get(interface, 0) + 1
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_users": total_users,
            "total_interfaces": total_interfaces,
            "interface_breakdown": interface_counts,
            "session_timeout_hours": self.session_timeout.total_seconds() / 3600,
            "cleanup_interval_minutes": self.cleanup_interval.total_seconds() / 60
        }
    
    async def _find_user_session(self, user_id: str) -> Optional[SessionContext]:
        """Find active session for user."""
        session_ids = self.user_sessions.get(user_id, set())
        
        for session_id in session_ids:
            session = self.active_sessions.get(session_id)
            if session and session.is_active:
                return session
        
        return None
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"session_{uuid.uuid4().hex[:8]}"
    
    async def _emit_session_event(self, event_type: str, data: Dict[str, Any]):
        """Emit session event."""
        if self.event_bus:
            await self.event_bus.emit(event_type, data)
    
    async def _load_sessions_from_memory(self):
        """Load sessions from memory storage."""
        try:
            # This would load from persistent storage
            # For now, we start with empty sessions
            self.logger.info("Loading sessions from memory (none found)")
        except Exception as e:
            self.logger.warning(f"Failed to load sessions from memory: {e}")
    
    async def _save_sessions_to_memory(self):
        """Save sessions to memory storage."""
        try:
            # Convert sessions to serializable format
            session_data = {
                session_id: session.to_dict()
                for session_id, session in self.active_sessions.items()
            }
            
            # Store in memory system
            await self.memory_manager.set_temporary(
                "unified_sessions",
                session_data,
                ttl_seconds=3600  # 1 hour TTL
            )
            
            self.logger.info(f"Saved {len(session_data)} sessions to memory")
        except Exception as e:
            self.logger.warning(f"Failed to save sessions to memory: {e}")
    
    async def _cleanup_loop(self):
        """Background task to clean up expired sessions."""
        while self._running:
            try:
                await self._cleanup_expired_sessions()
                await asyncio.sleep(self.cleanup_interval.total_seconds())
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if session.last_activity + self.session_timeout < now:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self._cleanup_session(session_id)
        
        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    async def _cleanup_session(self, session_id: str):
        """Clean up a specific session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        # Remove from all mappings
        self.active_sessions.pop(session_id, None)
        
        # Remove from user sessions
        if session.user_id in self.user_sessions:
            self.user_sessions[session.user_id].discard(session_id)
            if not self.user_sessions[session.user_id]:
                self.user_sessions.pop(session.user_id, None)
        
        # Remove interface mappings
        for interface in session.interfaces:
            interface_id = f"{interface}_{session.user_id}"
            self.interface_sessions.pop(interface_id, None)
        
        # Emit cleanup event
        await self._emit_session_event("session.cleaned_up", {
            "session_id": session_id,
            "user_id": session.user_id,
            "duration_hours": (datetime.now() - session.created_at).total_seconds() / 3600
        })
        
        self.logger.info(f"Cleaned up session {session_id}") 