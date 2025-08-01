"""
Nagatha Assistant Unified Server Package

This package provides the unified server architecture that allows Nagatha to
operate as a single consciousness across multiple interfaces (CLI, Discord, Dashboard).
"""

from .core_server import NagathaUnifiedServer
from .core.session_manager import UnifiedSessionManager
from .core.connection_pool import SharedMCPConnectionPool

__all__ = [
    'NagathaUnifiedServer',
    'UnifiedSessionManager', 
    'SharedMCPConnectionPool'
]

__version__ = "1.0.0" 