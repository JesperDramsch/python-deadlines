"""Logging configuration for Python Deadlines project."""

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


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


class TqdmLoggingHandler(logging.Handler):
    """Custom logging handler that uses tqdm.write() for tqdm-compatible output."""

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            # Try to import and use tqdm.write, fallback to print
            try:
                from tqdm import tqdm

                tqdm.write(msg)
            except ImportError:
                print(msg)
        except Exception:
            self.handleError(record)


def setup_tqdm_logging(
    level: str = "INFO",
    log_file: str | None = None,
    include_timestamp: bool = True,
) -> logging.Logger:
    """Set up tqdm-compatible logging configuration for the project.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        include_timestamp: Whether to include timestamps in log messages

    Returns
    -------
        logging.Logger: Configured logger instance with tqdm-compatible output
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

    # Tqdm-compatible console handler
    tqdm_handler = TqdmLoggingHandler()
    tqdm_handler.setFormatter(formatter)
    logger.addHandler(tqdm_handler)

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
        return setup_tqdm_logging()

    return logger


def get_tqdm_logger(name: str | None = None, level: str = "INFO") -> logging.Logger:
    """Get a tqdm-compatible logger instance.

    Args:
        name: Logger name (defaults to calling module)
        level: Logging level

    Returns
    -------
        logging.Logger: Tqdm-compatible logger instance
    """
    if name is None:
        name = "python_deadlines"

    logger = logging.getLogger(name)

    # Set up tqdm-compatible configuration if not already configured
    if not logger.handlers:
        return setup_tqdm_logging(level=level)

    return logger
