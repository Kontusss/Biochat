"""
Structured Logging for Biochat.

Replaces ad-hoc ``print()`` statements with proper Python logging.
Provides a consistent format, level control, and optional JSON output
for machine-readability.

Usage:
    from biochat.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Agent initialized", extra={"model": "claude-sonnet-4-5"})
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import ClassVar


# ═══════════════════════════════════════════════════════════════════
# Custom formatters
# ═══════════════════════════════════════════════════════════════════

class ConsoleFormatter(logging.Formatter):
    """Human-readable coloured console format."""

    _COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[35m",  # magenta
    }
    _RESET: str = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLORS.get(record.levelno, "")
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        prefix = f"{colour}[{timestamp}][{record.levelname}]{self._RESET}"
        name = f"\033[90m[{record.name}]\033[0m"
        return f"{prefix} {name} {record.getMessage()}"


class JsonFormatter(logging.Formatter):
    """JSON formatter for machine-readable logs."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

def configure_logging(
    level: int | str = logging.INFO,
    json_format: bool = False,
    capture_warnings: bool = True,
) -> None:
    """Configure the root Biochat logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, emit JSON lines (useful for file/shipping).
        capture_warnings: Redirect Python warnings into the logging system.
    """
    root = logging.getLogger("biochat")
    root.setLevel(_resolve_level(level))

    # Remove any existing handlers to avoid duplicates on re-config
    root.handlers.clear()

    handler: logging.Handler
    if json_format:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ConsoleFormatter())

    root.addHandler(handler)

    # Optionally configure child loggers
    for child in ("biochat.services", "biochat.ui", "biochat.agent"):
        logging.getLogger(child).setLevel(root.level)

    if capture_warnings:
        logging.captureWarnings(True)

    # Silence overly chatty third-party loggers
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "boto3",
        "botocore",
        "googleapiclient",
        "langchain_core",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name.

    Usage:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting agent task", extra={"task_id": "abc"})
    """
    return logging.getLogger(name)


def _resolve_level(level: int | str) -> int:
    """Resolve a level from string or int."""
    if isinstance(level, int):
        return level
    return getattr(logging, level.upper(), logging.INFO)


# ── Auto-configure on first import ────────────────────────────────
if os.getenv("BIOCHAT_LOG_LEVEL") or os.getenv("BIOMNI_LOG_LEVEL"):
    configure_logging(
        level=os.getenv("BIOCHAT_LOG_LEVEL") or os.getenv("BIOMNI_LOG_LEVEL") or "INFO",
        json_format=os.getenv("BIOCHAT_LOG_JSON", "").lower() in ("1", "true", "yes"),
    )
