"""Path layout under the data directory."""

from __future__ import annotations

from pathlib import Path


class DataPaths:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure(self) -> None:
        for relative in (
            "projects",
            "blobs",
            "jobs",
            "cache",
            "temp",
            "imports",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        return self.root / "projects" / project_id

    def project_file(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project.json"

    def asset_file(self, project_id: str, asset_id: str) -> Path:
        return self.project_dir(project_id) / "assets" / f"{asset_id}.json"

    def assets_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "assets"

    def character_file(self, project_id: str, character_id: str) -> Path:
        return self.project_dir(project_id) / "characters" / f"{character_id}.json"

    def characters_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "characters"

    def scene_file(self, project_id: str, scene_id: str) -> Path:
        return self.project_dir(project_id) / "scenes" / f"{scene_id}.json"

    def scenes_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "scenes"

    def version_file(self, project_id: str, version_id: str) -> Path:
        return self.project_dir(project_id) / "versions" / f"{version_id}.json"

    def versions_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "versions"

    def preview_dir(self, project_id: str, asset_id: str) -> Path:
        return self.project_dir(project_id) / "previews" / asset_id

    def scene_cache(self, project_id: str, cache_key: str) -> Path:
        return self.project_dir(project_id) / "cache" / "scenes" / f"{cache_key}.mp4"

    def cache_manifest(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "cache" / "manifest.json"

    def render_output(self, project_id: str, job_id: str) -> Path:
        return self.project_dir(project_id) / "renders" / f"{job_id}.mp4"

    def job_file(self, job_id: str) -> Path:
        return self.root / "jobs" / f"{job_id}.json"

    def blob_path(self, sha256: str, suffix: str) -> Path:
        return self.root / "blobs" / sha256[:2] / f"{sha256}{suffix}"

    def temp_dir(self, job_id: str) -> Path:
        return self.root / "temp" / job_id

    def remotion_bundle(self) -> Path:
        return self.root / "cache" / "remotion-bundle"

    def ensure_project(self, project_id: str) -> None:
        base = self.project_dir(project_id)
        for name in ("assets", "characters", "scenes", "versions", "previews", "renders", "cache", "cache/scenes"):
            (base / name).mkdir(parents=True, exist_ok=True)
