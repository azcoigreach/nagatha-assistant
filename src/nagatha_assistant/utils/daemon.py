"""
Daemon utility for running background processes.

Provides simple daemon process management for services like the Discord bot.
"""

import os
import sys
import signal
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable
import psutil

from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


class DaemonManager:
    """
    Simple daemon process manager.
    
    Manages background processes with PID file tracking for start/stop/status operations.
    """
    
    def __init__(self, name: str, pid_dir: Optional[Path] = None):
        """
        Initialize daemon manager.
        
        Args:
            name: Name of the daemon (used for PID file)
            pid_dir: Directory to store PID files (defaults to current working directory)
        """
        self.name = name
        self.pid_dir = pid_dir or Path.cwd()
        self.pid_file = self.pid_dir / f".{name}.pid"
    
    def is_running(self) -> bool:
        """
        Check if the daemon is currently running.
        
        Returns:
            True if daemon is running, False otherwise
        """
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists and is still running
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                # Additional check to ensure it's not a zombie or different process
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    # Verify it's actually our daemon process by checking command line
                    try:
                        cmdline = proc.cmdline()
                        if any('nagatha' in arg.lower() for arg in cmdline):
                            return True
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        # If we can't check command line, assume it's our process
                        return True
            
            # If we get here, PID file exists but process doesn't, clean up
            self.pid_file.unlink()
            return False
            
        except (ValueError, OSError, psutil.NoSuchProcess, psutil.AccessDenied):
            # If we can't read PID file or access process, assume not running
            try:
                self.pid_file.unlink()
            except OSError:
                pass
            return False
    
    def get_pid(self) -> Optional[int]:
        """
        Get the PID of the running daemon.
        
        Returns:
            PID if daemon is running, None otherwise
        """
        if not self.is_running():
            return None
        
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            return None
    
    def start_daemon(self, target_func: Callable, *args, **kwargs) -> bool:
        """
        Start the daemon process.
        
        Args:
            target_func: Async function to run in the daemon
            *args: Arguments to pass to target_func
            **kwargs: Keyword arguments to pass to target_func
        
        Returns:
            True if daemon started successfully, False if already running
        """
        if self.is_running():
            logger.warning(f"Daemon {self.name} is already running")
            return False
        
        logger.info(f"Starting daemon {self.name}")
        
        # Fork the process
        try:
            logger.info("About to fork daemon process")
            pid = os.fork()
            logger.info(f"Fork returned PID: {pid}")
            
            if pid > 0:
                # Parent process - just return success
                logger.info(f"Parent process, forked child PID {pid}, returning.")
                return True
            
            # Child process - become daemon
            logger.info("Child process, becoming daemon")
            self._daemonize_and_write_pid()
            
            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Run the target function in the daemon
            try:
                result = asyncio.run(target_func(*args, **kwargs))
                # If target function returns None or False, exit the daemon
                if result is False:
                    logger.info(f"Daemon {self.name} target function returned False, exiting")
                    self._cleanup_pid_file()
                    sys.exit(1)
            except Exception as e:
                logger.error(f"Daemon {self.name} crashed: {e}")
                logger.exception("Full traceback:")
                # Clean up PID file on crash
                self._cleanup_pid_file()
                sys.exit(1)
            finally:
                # Only clean up PID file when the daemon process actually exits
                # Don't clean up here as the daemon might still be running
                pass
            
            # Clean up PID file when daemon exits normally
            self._cleanup_pid_file()
            sys.exit(0)
                
        except OSError as e:
            logger.error(f"Failed to fork daemon {self.name}: {e}")
            return False

    def _daemonize_and_write_pid(self):
        """
        Daemonize the current process and write the PID file as the daemonized process.
        """
        try:
            # First fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit parent
        except OSError as e:
            logger.error(f"First fork failed: {e}")
            sys.exit(1)
        
        # Decouple from parent environment
        os.setsid()
        os.umask(0)
        
        try:
            # Second fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit second parent
        except OSError as e:
            logger.error(f"Second fork failed: {e}")
            sys.exit(1)
        
        # Now in the daemonized (grandchild) process
        daemon_pid = os.getpid()
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(daemon_pid))
            logger.info(f"[daemon] PID file written with PID {daemon_pid}")
        except Exception as e:
            logger.error(f"[daemon] Error writing PID file: {e}")
        # Don't redirect output for debugging - keep it visible
        logger.info("Daemon process started successfully")
    
    def stop_daemon(self, timeout: int = 10) -> bool:
        """
        Stop the daemon process.
        
        Args:
            timeout: Maximum time to wait for graceful shutdown
        
        Returns:
            True if daemon stopped successfully, False if not running
        """
        if not self.is_running():
            logger.warning(f"Daemon {self.name} is not running")
            return False
        
        pid = self.get_pid()
        if pid is None:
            return False
        
        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            proc = psutil.Process(pid)
            proc.wait(timeout=timeout)
            
            logger.info(f"Daemon {self.name} stopped gracefully")
            
        except psutil.TimeoutExpired:
            # Force kill if graceful shutdown failed
            try:
                os.kill(pid, signal.SIGKILL)
                logger.warning(f"Force killed daemon {self.name}")
            except OSError:
                pass
                
        except (OSError, psutil.NoSuchProcess):
            # Process already gone
            pass
        
        # Clean up PID file
        self._cleanup_pid_file()
        
        return True
    
    def get_status(self) -> dict:
        """
        Get detailed status information about the daemon.
        
        Returns:
            Dictionary with status information
        """
        if not self.is_running():
            return {
                "name": self.name,
                "running": False,
                "pid": None,
                "status": "stopped"
            }
        
        pid = self.get_pid()
        if pid is None:
            return {
                "name": self.name,
                "running": False,
                "pid": None,
                "status": "stopped"
            }
        
        try:
            proc = psutil.Process(pid)
            return {
                "name": self.name,
                "running": True,
                "pid": pid,
                "status": proc.status(),
                "memory": proc.memory_info().rss,
                "cpu_percent": proc.cpu_percent(),
                "create_time": proc.create_time()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {
                "name": self.name,
                "running": False,
                "pid": pid,
                "status": "not_found"
            }
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Daemon {self.name} received signal {signum}, shutting down gracefully")
            self._cleanup_pid_file()
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def _cleanup_pid_file(self):
        """Clean up the PID file."""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.debug(f"Cleaned up PID file for daemon {self.name}")
        except OSError as e:
            logger.warning(f"Failed to clean up PID file for daemon {self.name}: {e}")