"""Provider protocols. V1 ships filesystem and local render implementations only."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageProvider(Protocol):
    def write_json(self, path: Path, payload: object) -> None: ...

    def read_json(self, path: Path) -> object: ...


class AssetProvider(Protocol):
    def register(self, project_id: str, source: Path) -> dict: ...


class RenderProvider(Protocol):
    def render_scene(self, props: dict, output: Path) -> None: ...
