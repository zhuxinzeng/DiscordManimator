"""Logging configuration with support for structured logging (extra fields)."""

from __future__ import annotations

import logging


class ExtraFormatter(logging.Formatter):
    """Formatter that includes extra fields in log output.

    Extra fields passed via logger.info("msg", extra={...}) will be
    appended to the log message in a structured format.
    """

    # Standard logging fields that should not be treated as "extra"
    STANDARD_FIELDS = {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "asctime",
        "taskName",  # Added in Python 3.12+
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, appending any extra fields."""
        # Get base formatted message
        base_message = super().format(record)

        # Find extra fields (anything not in standard fields)
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self.STANDARD_FIELDS
        }

        # If there are extra fields, append them
        if extra_fields:
            # Format extra fields as key=value pairs
            extra_str = " ".join(
                f"{key}={value}" for key, value in extra_fields.items()
            )
            return f"{base_message} | {extra_str}"

        return base_message


def setup_logging_with_extra_fields(level: int = logging.INFO) -> None:
    """Configure logging to display extra fields.

    Args:
        level: Logging level (default: INFO)
    """
    # Create handler with our custom formatter
    handler = logging.StreamHandler()
    formatter = ExtraFormatter(
        fmt="[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add our handler
    root_logger.addHandler(handler)
