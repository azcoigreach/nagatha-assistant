import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = __name__) -> logging.Logger:
    """
    Set up logging with RotatingFileHandler.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    logger.setLevel(getattr(logging, log_level, logging.DEBUG))

    log_file = os.getenv("LOG_FILE", "nagatha.log")
    handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger