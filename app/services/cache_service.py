"""Remember which scene renders already exist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.renderer.cachekey import visual_cache_key
from app.storage.filesystem import read_json, write_json
from app.storage.paths import DataPaths


class CacheService:
    def __init__(self, paths: DataPaths) -> None:
        self.paths = paths

    def key(
        self,
        project: Project,
        scene: Scene,
        assets: dict[str, Asset],
        *,
        profile: str,
        width: int,
        height: int,
        crf: int,
        compiled: Any | None = None,
    ) -> str:
        return visual_cache_key(
            project,
            scene,
            assets,
            profile=profile,
            width=width,
            height=height,
            crf=crf,
            compiled=compiled,
        )

    def path_for(self, project_id: str, cache_key: str) -> Path:
        return self.paths.scene_cache(project_id, cache_key)

    def has(self, project_id: str, cache_key: str) -> bool:
        path = self.path_for(project_id, cache_key)
        return path.exists() and path.stat().st_size > 0

    def remember(self, project_id: str, scene_id: str, cache_key: str) -> None:
        manifest_path = self.paths.cache_manifest(project_id)
        manifest = read_json(manifest_path) if manifest_path.exists() else {"scenes": {}}
        manifest.setdefault("scenes", {})[scene_id] = cache_key
        write_json(manifest_path, manifest)
