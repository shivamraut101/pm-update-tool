"""Centralized logging configuration for the PM Update Tool.

Provides structured logging with different levels for development and production.
All logs are sent to stdout (captured by Render logs).
"""
import logging
import sys
from datetime import datetime


# Configure root logger
def setup_logging(level: str = "INFO"):
    """Setup logging configuration for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter with timestamp, level, module, and message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler (stdout → Render logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)

    return root_logger


# Module-specific loggers (use these in each module)
def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Usage in modules:
        from backend.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)


# Initialize default logging on import
setup_logging()
