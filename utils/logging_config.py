"""Logging configuration for Python Deadlines project."""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str | None = None, include_timestamp: bool = True) -> logging.Logger:
    """Set up logging configuration for the project.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        include_timestamp: Whether to include timestamps in log messages

    Returns
    -------
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("python_deadlines")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    if include_timestamp:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter("%(levelname)s - %(message)s")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance with the project configuration.

    Args:
        name: Logger name (defaults to calling module)

    Returns
    -------
        logging.Logger: Logger instance
    """
    if name is None:
        name = "python_deadlines"

    logger = logging.getLogger(name)

    # Set up basic configuration if not already configured
    if not logger.handlers:
        return setup_logging()

    return logger
