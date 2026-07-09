"""
Production Logging Configuration — Task 2 Production Hardening

Provides:
  - JSON-structured log formatter (machine-parseable by log aggregators)
  - RotatingFileHandler wired to settings.LOG_FILE
  - Thread-local trace context so every log record carries trace_id,
    execution_id, and pipeline_stage automatically
  - setup_logging() replaces the plain-text basicConfig in utils.py
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

# ---------------------------------------------------------------------------
# Thread-local trace context
# ---------------------------------------------------------------------------

_ctx = threading.local()


def set_trace_context(
    trace_id: str = "",
    execution_id: str = "",
    pipeline_stage: str = "",
) -> None:
    """Attach trace identifiers to the current thread/async context."""
    _ctx.trace_id = trace_id
    _ctx.execution_id = execution_id
    _ctx.pipeline_stage = pipeline_stage


def clear_trace_context() -> None:
    """Remove trace identifiers from the current thread/async context."""
    _ctx.trace_id = ""
    _ctx.execution_id = ""
    _ctx.pipeline_stage = ""


def get_trace_context() -> dict:
    return {
        "trace_id": getattr(_ctx, "trace_id", ""),
        "execution_id": getattr(_ctx, "execution_id", ""),
        "pipeline_stage": getattr(_ctx, "pipeline_stage", ""),
    }


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """
    Emits one JSON object per log line.

    Every record includes:
      timestamp, level, logger, message,
      trace_id, execution_id, pipeline_stage,
      module, funcName, lineno
    and optionally exc_info when an exception is attached.
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_trace_context()
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": ctx["trace_id"],
            "execution_id": ctx["execution_id"],
            "pipeline_stage": ctx["pipeline_stage"],
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "environment": settings.ENVIRONMENT,
            "service": "design_engine_api",
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup_logging() -> None:
    """
    Configure the root logger with:
      - StreamHandler  → JSON to stdout
      - RotatingFileHandler → JSON to settings.LOG_FILE
        (10 MB per file, 5 backups — approximates the "1 day / 30 days"
         rotation intent from settings without requiring loguru)

    Call once at application startup (replaces the basicConfig in utils.py).
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    formatter = JsonFormatter()

    # --- console handler ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # --- file handler ---
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_path),
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # --- root logger ---
    root = logging.getLogger()
    root.setLevel(log_level)
    # Remove any handlers added by earlier basicConfig calls
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Keep uvicorn logs visible at the same level
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).setLevel(log_level)


__all__ = [
    "setup_logging",
    "set_trace_context",
    "clear_trace_context",
    "get_trace_context",
    "JsonFormatter",
]
