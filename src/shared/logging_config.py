"""
Structured Logging Configuration

@spec Shared infrastructure - observability

Configures JSON logging for production and human-readable logging for development.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any
import os


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.

    Outputs logs as JSON lines for easy parsing by log aggregators
    like Elasticsearch, Splunk, or CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "message", "taskName",
            }:
                log_data[key] = value

        return json.dumps(log_data, default=str)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable log formatter for development.

    Uses colors and formatting for easy reading in terminal.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",   # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        base_msg = f"{timestamp} | {record.levelname:8} | {record.name}:{record.lineno} | {record.getMessage()}"

        if record.exc_info:
            base_msg += f"\n{self.formatException(record.exc_info)}"

        return f"{color}{base_msg}{self.RESET}"


def setup_logging() -> None:
    """
    Configure application logging based on environment.

    Call this once at application startup.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Select formatter based on environment
    if environment.lower() == "production":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = DevelopmentFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiosmtplib").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Usage:
        logger = get_logger(__name__)
        logger.info("Message", extra={"key": "value"})
    """
    return logging.getLogger(name)
