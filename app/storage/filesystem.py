"""JSON file store. Callers pass paths from DataPaths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def delete_tree(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file():
        path.unlink()
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        else:
            child.rmdir()
    path.rmdir()
