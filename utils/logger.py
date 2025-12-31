"""Logger utility module for Polymarket copy bot.

This module provides a simple interface to get logger instances.
It wraps the standard logging module for consistency across the codebase.
"""

import logging
import os
from typing import Optional


def setup_logging(
    level: str = "INFO", log_dir: str = "logs", json_logging: bool = False
) -> None:
    """
    Set up logging configuration.

    Args:
        level: Logging level (default: INFO)
        log_dir: Directory for log files (default: logs)
        json_logging: Enable JSON format logging (default: False)
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"benchmark_{os.getenv('TEST_ENV', 'main')}.log")

    if json_logging:
        # JSON format logging
        import json_log_formatter

        formatter = json_log_formatter.JSONFormatter()
    else:
        # Standard format logging
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__). If None, returns root logger.

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
