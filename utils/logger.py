#!/usr/bin/env python3
"""
EMSN 2.0 - Unified Logging Utility

Provides consistent logging across all EMSN sync scripts with:
- USB-first logging (primary log location)
- Fallback to local directory if USB unavailable
- Console output for manual runs
- Structured log format with timestamps
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# USB log directory (primary)
USB_LOG_DIR = Path("/mnt/usb/logs")
# Fallback log directory (if USB not mounted)
FALLBACK_LOG_DIR = Path("/home/ronny/emsn2/logs")


def setup_logger(name: str, log_file: str = None, level=logging.INFO) -> logging.Logger:
    """
    Setup a logger with USB-first file logging and console output.

    Args:
        name: Logger name (usually __name__ from calling module)
        log_file: Log filename (e.g., 'lifetime_sync.log')
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (always enabled for manual runs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (USB-first with fallback)
    if log_file:
        log_path = _get_log_path(log_file)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path, mode='a')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f"Logging to: {log_path}")
        except Exception as e:
            logger.warning(f"Could not setup file logging to {log_path}: {e}")

    return logger


def _get_log_path(log_file: str) -> Path:
    """
    Determine log file path with USB-first fallback.

    Returns USB path if available, otherwise local fallback.
    """
    usb_path = USB_LOG_DIR / log_file

    # Check if USB mount is available
    if USB_LOG_DIR.exists() and USB_LOG_DIR.is_dir():
        return usb_path
    else:
        # Fallback to local logs directory
        FALLBACK_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return FALLBACK_LOG_DIR / log_file


def log_separator(logger: logging.Logger, title: str = ""):
    """
    Log a visual separator for better log readability.

    Args:
        logger: Logger instance
        title: Optional title for the separator section
    """
    separator = "=" * 60
    if title:
        logger.info(separator)
        logger.info(f"  {title}")
        logger.info(separator)
    else:
        logger.info(separator)


def log_exception(logger: logging.Logger, message: str, exc: Exception):
    """
    Log an exception with context message.

    Args:
        logger: Logger instance
        message: Context message describing what failed
        exc: The exception that was caught
    """
    logger.error(f"{message}: {type(exc).__name__}: {exc}", exc_info=True)


# Convenience function for quick logger setup
def get_logger(script_name: str) -> logging.Logger:
    """
    Quick setup for a logger with standard EMSN configuration.

    Args:
        script_name: Name of the script (e.g., 'lifetime_sync')

    Returns:
        Configured logger

    Example:
        logger = get_logger('lifetime_sync')
        logger.info('Starting sync...')
    """
    log_file = f"{script_name}.log"
    return setup_logger(script_name, log_file)


if __name__ == "__main__":
    # Test the logger
    test_logger = get_logger('test_logger')
    log_separator(test_logger, "Logger Test")
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")

    try:
        raise ValueError("Test exception")
    except Exception as e:
        log_exception(test_logger, "Test exception handling", e)

    log_separator(test_logger)
    print("\nLogger test complete. Check logs at:")
    print(f"  USB: {USB_LOG_DIR}/test_logger.log")
    print(f"  Fallback: {FALLBACK_LOG_DIR}/test_logger.log")
