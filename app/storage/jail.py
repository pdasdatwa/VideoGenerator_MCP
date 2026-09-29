"""Local filesystem jail for asset registration."""

from __future__ import annotations

from pathlib import Path

from app.errors import MarketingError


def resolve_allowed_file(user_path: str, roots: list[Path]) -> Path:
    """Resolve a user path and require the real file to sit inside an allowed root."""
    raw = Path(user_path)
    if any(part == ".." for part in raw.parts):
        raise MarketingError(
            "PATH_NOT_ALLOWED",
            "Asset paths cannot contain '..'.",
            suggested_action="Pass a path inside an allowed import directory, without parent segments.",
            path=user_path,
        )
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MarketingError(
            "ASSET_NOT_FOUND",
            f"No file at {user_path}.",
            suggested_action="Check the path. It must already exist inside an allowed directory.",
            path=user_path,
        ) from exc
    if not resolved.is_file():
        raise MarketingError(
            "PATH_NOT_ALLOWED",
            "Asset path must be a file.",
            suggested_action="Point register_asset at a media file, not a directory.",
            path=str(resolved),
        )
    allowed: list[Path] = []
    for root in roots:
        root_path = root if root.is_absolute() else Path.cwd() / root
        try:
            allowed.append(root_path.resolve())
        except FileNotFoundError:
            root_path.mkdir(parents=True, exist_ok=True)
            allowed.append(root_path.resolve())
    if not any(_is_relative_to(resolved, root) for root in allowed):
        raise MarketingError(
            "PATH_NOT_ALLOWED",
            "Asset path is outside the configured source directories.",
            suggested_action="Copy the file into imports/ or demos/assets/ and register that path.",
            path=str(resolved),
            allowed_roots=[str(root) for root in allowed],
        )
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
