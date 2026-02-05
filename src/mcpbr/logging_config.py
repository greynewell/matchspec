"""Structured logging configuration for mcpbr.

Provides JSON-structured and human-readable log formatting, log file rotation,
environment variable overrides, and contextual log fields for benchmark runs.
"""

import json
import logging
import logging.handlers
import os
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter.

    Produces one JSON object per log record, including optional context fields
    like task_id and benchmark when they are attached to the record.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A JSON-encoded string representing the log entry.
        """
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id
        if hasattr(record, "benchmark"):
            log_data["benchmark"] = record.benchmark
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


class HumanFormatter(logging.Formatter):
    """Human-readable log formatter.

    Produces log lines in the format: [LEVEL] logger.name: message
    """

    FORMAT = "[%(levelname)s] %(name)s: %(message)s"

    def __init__(self) -> None:
        """Initialize the formatter with the human-readable format string."""
        super().__init__(self.FORMAT)


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    structured: bool = False,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    debug: bool = False,
    quiet: bool = False,
) -> None:
    """Configure mcpbr logging.

    Sets up the 'mcpbr' root logger with console and optional file handlers.
    Supports structured JSON output, log rotation, and environment variable
    overrides via MCPBR_LOG_LEVEL.

    Args:
        level: Default log level string (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').
        log_file: Optional path to a log file. If provided, a rotating file handler
            is added. Parent directories are created automatically.
        structured: If True, use JSON-structured formatting. Otherwise use
            human-readable formatting.
        max_bytes: Maximum log file size in bytes before rotation (default 10 MB).
        backup_count: Number of rotated backup files to keep (default 5).
        debug: If True, override level to DEBUG.
        quiet: If True, override level to WARNING (suppresses INFO and below).
    """
    mcpbr_logger = logging.getLogger("mcpbr")

    # Clear existing handlers to allow reconfiguration
    mcpbr_logger.handlers.clear()

    # Determine effective log level
    # Priority: env var > debug/quiet flags > level parameter
    env_level = os.environ.get("MCPBR_LOG_LEVEL")
    if env_level:
        effective_level = getattr(logging, env_level.upper(), logging.INFO)
    elif debug:
        effective_level = logging.DEBUG
    elif quiet:
        effective_level = logging.WARNING
    else:
        effective_level = getattr(logging, level.upper(), logging.INFO)

    mcpbr_logger.setLevel(effective_level)

    # Choose formatter
    if structured:
        formatter: logging.Formatter = StructuredFormatter()
    else:
        formatter = HumanFormatter()

    # Console handler (always added)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    mcpbr_logger.addHandler(console_handler)

    # File handler (optional, with rotation)
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setFormatter(formatter)
        mcpbr_logger.addHandler(file_handler)

    # Prevent propagation to the root logger to avoid duplicate output
    mcpbr_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a named mcpbr logger.

    Returns a logger under the 'mcpbr' namespace. For example,
    get_logger('evaluation') returns the logger 'mcpbr.evaluation'.

    Args:
        name: The logger name suffix (will be prefixed with 'mcpbr.').

    Returns:
        A logging.Logger instance.
    """
    return logging.getLogger(f"mcpbr.{name}")


class _ContextFilter(logging.Filter):
    """A logging filter that injects context fields into log records."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the filter with context key-value pairs.

        Args:
            **kwargs: Arbitrary context fields to add to every log record.
        """
        super().__init__()
        self.context = kwargs

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to the log record.

        Args:
            record: The log record being processed.

        Returns:
            Always returns True (never filters out records).
        """
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class LogContext:
    """Add structured context fields to log records via a filter.

    Use as a context manager to temporarily inject fields like task_id and
    benchmark into all log records produced by the given logger.

    Example:
        logger = get_logger("evaluation")
        with LogContext(logger, task_id="django-12345", benchmark="swebench"):
            logger.info("Starting evaluation")
            # Log record will include task_id and benchmark fields
    """

    def __init__(self, logger: logging.Logger, **kwargs: Any) -> None:
        """Initialize the log context.

        Args:
            logger: The logger to attach context fields to.
            **kwargs: Context fields to add (e.g., task_id, benchmark).
        """
        self.logger = logger
        self.kwargs = kwargs
        self._filter: _ContextFilter | None = None

    def __enter__(self) -> "LogContext":
        """Enter the context and attach the filter to the logger."""
        self._filter = _ContextFilter(**self.kwargs)
        self.logger.addFilter(self._filter)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit the context and remove the filter from the logger."""
        if self._filter is not None:
            self.logger.removeFilter(self._filter)
            self._filter = None
