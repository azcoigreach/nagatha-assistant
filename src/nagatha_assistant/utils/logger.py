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
    
    # Ensure the log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except (OSError, PermissionError):
            # Fallback to current directory if we can't create the log directory
            log_file = "nagatha.log"
    
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
    - NAGATHA_LOG_LEVEL_FILE: Log level for file logging (default: DEBUG)
    - NAGATHA_LOG_LEVEL_CHAT: Log level for chat session display (default: WARNING)
    """
    logger = logging.getLogger("nagatha_assistant")
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Get log levels from environment
    file_log_level = os.getenv("NAGATHA_LOG_LEVEL_FILE", "DEBUG").upper()
    chat_log_level = os.getenv("NAGATHA_LOG_LEVEL_CHAT", "WARNING").upper()
    
    # Convert string levels to logging constants
    file_level = getattr(logging, file_log_level, logging.DEBUG)
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

def should_log_to_chat(level: int) -> bool:
    """Check if a log level should be displayed in chat."""
    logger = logging.getLogger("nagatha_assistant")
    chat_level = getattr(logger, 'chat_log_level', logging.WARNING)
    return level >= chat_level

def get_chat_log_level() -> int:
    """Get the current chat log level."""
    logger = logging.getLogger("nagatha_assistant")
    return getattr(logger, 'chat_log_level', logging.WARNING)