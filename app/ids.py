"""Prefixed time-sortable identifiers."""

from __future__ import annotations

import re
import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_id(prefix: str) -> str:
    """Return an id like ``project_01J...`` (Crockford time + random)."""
    value = int(time.time() * 1000)
    chars: list[str] = []
    for _ in range(10):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    stamp = "".join(reversed(chars))
    random_part = "".join(_ALPHABET[secrets.randbelow(32)] for _ in range(16))
    return f"{prefix}_{stamp}{random_part}"


def validate_client_id(value: str, *, field: str = "id") -> str:
    if not _ID_RE.match(value):
        from app.errors import MarketingError

        raise MarketingError(
            "INVALID_ID",
            f"{field} must match ^[A-Za-z0-9_-]{{1,64}}$.",
            suggested_action="Use letters, numbers, underscores, or hyphens, up to 64 characters.",
            field=field,
        )
    return value
