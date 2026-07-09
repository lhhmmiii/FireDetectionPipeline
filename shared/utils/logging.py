"""Structured logging setup for all pipeline services.

Provides a consistent JSON-formatted logging configuration so that
every service produces machine-parseable log output.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "service"):
            log_entry["service"] = record.service

        # Build JSON string manually to avoid import overhead
        parts = [f'"{k}": "{v}"' for k, v in log_entry.items()]
        return "{" + ", ".join(parts) + "}"


class SimpleFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


def setup_logging(service_name: str = "pipeline") -> logging.Logger:
    """Configure logging for a pipeline service.

    Args:
        service_name: Name of the service (used in log output).

    Returns:
        A configured logger instance for the service.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "json").lower()

    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level, logging.INFO))

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(SimpleFormatter())

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    logger.info("Logging initialized for service '%s' (level=%s)", service_name, log_level)
    return logger
