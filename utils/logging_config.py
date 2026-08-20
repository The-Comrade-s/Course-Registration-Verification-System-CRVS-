"""
Application logging configuration.

Provides a single, centrally configured logger for the whole application.
Sensitive information (passwords, authentication secrets) must never be
passed to these loggers.
"""

from __future__ import annotations

import logging
import os

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "crvs.log")

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root application logger exactly once."""
    global _configured
    if _configured:
        return

    os.makedirs(_LOG_DIR, exist_ok=True)

    logger = logging.getLogger("crvs")
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the 'crvs' hierarchy."""
    configure_logging()
    return logging.getLogger(f"crvs.{name}")
