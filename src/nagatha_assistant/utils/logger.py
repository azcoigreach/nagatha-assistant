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