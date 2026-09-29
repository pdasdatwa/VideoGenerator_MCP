"""Actionable errors returned to MCP clients."""

from __future__ import annotations

from typing import Any


class ReelError(Exception):
    """Domain error with a stable code and a next step for the calling model."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        suggested_action: str | None = None,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggested_action = suggested_action
        self.details = {key: value for key, value in details.items() if value is not None}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
        }
        payload.update(self.details)
        if self.suggested_action:
            payload["suggested_action"] = self.suggested_action
        return payload


MarketingError = ReelError
