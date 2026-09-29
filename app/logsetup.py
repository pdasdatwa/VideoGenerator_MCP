"""Structured logs for render and cache decisions."""

from __future__ import annotations

import json
import logging
from typing import Any


class _JsonFormatter(logging.Formatter):
    _FIELDS = (
        "project_id",
        "scene_id",
        "asset_id",
        "job_id",
        "cache_hit",
        "cache_miss",
        "render_duration",
        "render_error",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if getattr(root, "_reel_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    setattr(root, "_reel_configured", True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
