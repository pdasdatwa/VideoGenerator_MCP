"""Turn domain errors into tool payloads."""

from __future__ import annotations

from typing import Any, Callable

from app.errors import MarketingError


def call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        result = func(*args, **kwargs)
        if isinstance(result, dict) and "error" in result and "message" in result:
            return result
        return result
    except MarketingError as exc:
        return exc.to_dict()
