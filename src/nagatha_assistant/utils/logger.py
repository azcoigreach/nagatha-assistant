import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str = __name__,
    disable_console: bool = False,
) -> logging.Logger:
    """
    Set up logging with RotatingFileHandler.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Determine the desired log level.  The precedence order is:
    # 1.  ``LOG_LEVEL`` environment variable – allows users to override
    #     the log level globally without touching the code.
    # 2.  Fallback to ``WARNING`` which is the project-wide default.
    log_level = os.getenv("LOG_LEVEL", "WARNING").upper()

    # Convert the textual level to the corresponding ``logging`` constant.
    # If the provided value is invalid we still end up with a sensible
    # default (`logging.WARNING`).
    logger.setLevel(getattr(logging, log_level, logging.WARNING))

    log_file = os.getenv("LOG_FILE", "nagatha.log")
    handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Add the RotatingFileHandler to the root logger
    logging.root.addHandler(handler)
    logging.root.setLevel(logger.level)

    # Disable console output for all loggers if requested
    if disable_console:
        logging.root.handlers = [
            h
            for h in logging.root.handlers
            if not isinstance(h, logging.StreamHandler)
        ]

    return logger

def setup_logger_with_env_control():
    """
    Set up logging with environment variable control.
    
    Environment variables:
    - NAGATHA_LOG_LEVEL_FILE: Log level for file logging (default: INFO)
    - NAGATHA_LOG_LEVEL_CHAT: Log level for chat session display (default: WARNING)
    """
    logger = logging.getLogger("nagatha_assistant")
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Get log levels from environment
    file_log_level = os.getenv("NAGATHA_LOG_LEVEL_FILE", "INFO").upper()
    chat_log_level = os.getenv("NAGATHA_LOG_LEVEL_CHAT", "WARNING").upper()
    
    # Convert string levels to logging constants
    file_level = getattr(logging, file_log_level, logging.INFO)
    chat_level = getattr(logging, chat_log_level, logging.WARNING)
    
    # Set base logger level to the most verbose of the two
    logger.setLevel(min(file_level, chat_level))
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler for detailed logging
    file_handler = logging.FileHandler("nagatha.log")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Store chat log level for UI components to use
    logger.chat_log_level = chat_level
    
    logger.info(f"Logger initialized - File level: {file_log_level}, Chat level: {chat_log_level}")
    
    return logger

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with unified configuration.
    
    This is the preferred way to get loggers throughout the application.
    It ensures consistent configuration and avoids duplicate handler setup.
    
    Args:
        name: Logger name (defaults to calling module's __name__)
        
    Returns:
        Configured logger instance
    """
    if name is None:
        # Get the calling module's name
        import inspect
        frame = inspect.currentframe()
        try:
            # Go up one frame to get the caller's module
            caller_frame = frame.f_back
            name = caller_frame.f_globals.get('__name__', __name__)
        finally:
            # Clean up the frame reference
            del frame
    
    logger = logging.getLogger(name)
    
    # If this is the first time getting this logger, ensure it's configured
    if not logger.handlers and name != "nagatha_assistant":
        # Use the main logger's configuration as a base
        main_logger = logging.getLogger("nagatha_assistant")
        if main_logger.handlers:
            # Copy the main logger's level
            logger.setLevel(main_logger.level)
        else:
            # Fall back to basic setup if main logger isn't configured
            setup_logger_with_env_control()
            logger.setLevel(logging.getLogger("nagatha_assistant").level)
    
    # Ensure the logger level is at least INFO to reduce debug noise
    if logger.level < logging.INFO:
        logger.setLevel(logging.INFO)
    
    return logger

def should_log_to_chat(level: int) -> bool:
    """Check if a log level should be displayed in chat."""
    logger = logging.getLogger("nagatha_assistant")
    chat_level = getattr(logger, 'chat_log_level', logging.WARNING)
    return level >= chat_level

def get_chat_log_level() -> int:
    """Get the current chat log level."""
    logger = logging.getLogger("nagatha_assistant")
    return getattr(logger, 'chat_log_level', logging.WARNING)