"""Strip scripts and event handlers from SVG before it reaches the renderer."""

from __future__ import annotations

import re

from app.errors import MarketingError

_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_FOREIGN = re.compile(r"<foreignObject\b[^>]*>.*?</foreignObject>", re.IGNORECASE | re.DOTALL)
_HANDLER = re.compile(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS = re.compile(r"javascript:", re.IGNORECASE)


def sanitize_svg(source: str) -> str:
    cleaned = _SCRIPT.sub("", source)
    cleaned = _FOREIGN.sub("", cleaned)
    cleaned = _HANDLER.sub("", cleaned)
    cleaned = _JS.sub("", cleaned)
    if "<svg" not in cleaned.lower():
        raise MarketingError(
            "UNSUPPORTED_FORMAT",
            "SVG asset does not contain an <svg> element.",
            suggested_action="Replace the file with a standalone SVG document.",
        )
    return cleaned
