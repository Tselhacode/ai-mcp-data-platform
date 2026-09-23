"""Structured JSON logging configuration for the AI MCP Data Platform backend.

Sets up Python's standard logging with a JSON formatter so every log line
is a parseable JSON object. This format is compatible with CloudWatch Logs
and any structured log aggregator.

Usage:
    from logging_config import configure_logging
    configure_logging()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("tool_call", extra={"tool": "list_buildings", "duration_ms": 42})
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class _JSONFormatter(logging.Formatter):
    """Formats each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "backend",
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any extra fields passed via `extra={...}`
        standard_keys = {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in standard_keys:
                log_entry[key] = value

        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for the entire application.

    Must be called once at application startup before any loggers are used.

    Args:
        level: Python log level string (e.g. "INFO", "DEBUG", "WARNING").
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Suppress overly verbose third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
