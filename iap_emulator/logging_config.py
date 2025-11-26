"""Structured logging configuration using structlog.

Provides JSON-formatted logging with:
- Request/response correlation IDs
- Contextual information (user_id, token, subscription_id)
- Timestamp and log level
- Structured fields for easy parsing
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, Processor


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application-wide context to log events."""
    event_dict["app"] = "iap-local-emulator"
    return event_dict


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to event dict if not present."""
    if "level" not in event_dict:
        event_dict["level"] = method_name.upper()
    return event_dict


def drop_debug_in_production(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Drop DEBUG logs if not in debug mode."""
    if method_name == "debug" and not is_debug_mode():
        raise structlog.DropEvent
    return event_dict


def is_debug_mode() -> bool:
    """Check if debug mode is enabled via LOG_LEVEL environment variable."""
    import os

    return os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"


def configure_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    include_timestamp: bool = True,
) -> None:
    """Configure structlog for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output JSON; if False, use colored console output
        include_timestamp: Include ISO8601 timestamps in logs
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_app_context,
        add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add timestamp if requested
    if include_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))

    # Drop debug logs if not in debug mode (performance optimization)
    if numeric_level > logging.DEBUG:
        processors.append(drop_debug_in_production)

    # Add appropriate renderer based on format
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    exception_formatter=structlog.dev.plain_traceback,
                )
            ]
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Convenience function for adding context
def bind_context(**kwargs: Any) -> None:
    """Bind context variables that will be included in all subsequent logs.

    Example:
        bind_context(request_id="abc123", user_id="user-456")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Unbind context variables.

    Example:
        unbind_context("request_id", "user_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()
