"""
Main entry point for the Nagatha Unified Server.

This module provides the command-line interface for starting and managing
the unified server.
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from nagatha_assistant.server.core_server import NagathaUnifiedServer, ServerConfig, start_unified_server, stop_unified_server
from nagatha_assistant.utils.logger import setup_logger_with_env_control


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Nagatha Unified Server - Single consciousness across interfaces"
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to (default: 8080)"
    )
    
    parser.add_argument(
        "--max-connections",
        type=int,
        default=3,
        help="Maximum connections per MCP server (default: 3)"
    )
    
    parser.add_argument(
        "--session-timeout",
        type=int,
        default=24,
        help="Session timeout in hours (default: 24)"
    )
    
    parser.add_argument(
        "--cleanup-interval",
        type=int,
        default=30,
        help="Cleanup interval in minutes (default: 30)"
    )
    
    parser.add_argument(
        "--no-websocket",
        action="store_true",
        help="Disable WebSocket API"
    )
    
    parser.add_argument(
        "--no-rest",
        action="store_true",
        help="Disable REST API"
    )
    
    parser.add_argument(
        "--no-events",
        action="store_true",
        help="Disable Events API"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    
    return parser.parse_args()


def load_config_file(config_path: str) -> dict:
    """Load configuration from file."""
    import json
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return {}


def create_server_config(args) -> ServerConfig:
    """Create server configuration from arguments."""
    config = ServerConfig(
        host=args.host,
        port=args.port,
        max_connections_per_server=args.max_connections,
        session_timeout_hours=args.session_timeout,
        cleanup_interval_minutes=args.cleanup_interval,
        enable_websocket=not args.no_websocket,
        enable_rest=not args.no_rest,
        enable_events=not args.no_events
    )
    
    # Override with config file if provided
    if args.config:
        file_config = load_config_file(args.config)
        for key, value in file_config.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return config


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    os.environ["LOG_LEVEL"] = args.log_level
    logger = setup_logger_with_env_control()
    
    logger.info("Starting Nagatha Unified Server")
    logger.info(f"Log level: {args.log_level}")
    
    # Create server configuration
    config = create_server_config(args)
    
    logger.info(f"Server configuration:")
    logger.info(f"  Host: {config.host}")
    logger.info(f"  Port: {config.port}")
    logger.info(f"  Max connections per server: {config.max_connections_per_server}")
    logger.info(f"  Session timeout: {config.session_timeout_hours} hours")
    logger.info(f"  Cleanup interval: {config.cleanup_interval_minutes} minutes")
    logger.info(f"  WebSocket API: {'enabled' if config.enable_websocket else 'disabled'}")
    logger.info(f"  REST API: {'enabled' if config.enable_rest else 'disabled'}")
    logger.info(f"  Events API: {'enabled' if config.enable_events else 'disabled'}")
    
    try:
        # Start the unified server
        await start_unified_server(config)
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
        
    finally:
        # Stop the server
        await stop_unified_server()
        logger.info("Server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1) 