"""
Centralized logging configuration.

All modules import get_logger() to obtain a logger that writes
both to console and to a rotating file in the application directory.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from utils.paths import app_data_dir


def setup_logging(log_dir: Path | None = None, level: int = logging.DEBUG) -> None:
    """Configure root logger with console and file handlers.

    Should be called once at application startup.

    Args:
        log_dir: Directory for log files. Defaults to app root / 'logs'.
        level: Minimum log level to capture.
    """
    if log_dir is None:
        log_dir = app_data_dir("logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = log_dir / f"screen_translator_{timestamp}.log"
    file_handler = logging.FileHandler(str(file_path), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info("Logging initialized. Log file: %s", file_path)


def get_logger(name: str) -> logging.Logger:
    """Obtain a logger for a specific module.

    Args:
        name: Typically __name__ from the calling module.

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)
