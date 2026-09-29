"""Local poster frames and contact sheets. Nothing is sent to an external service."""

from __future__ import annotations

from pathlib import Path

from app.models.asset import Asset
from app.renderer.ffmpeg import contact_sheet, extract_frame
from app.storage.paths import DataPaths


class AssetPreviewService:
    def __init__(self, paths: DataPaths) -> None:
        self.paths = paths

    def generate(self, asset: Asset) -> dict[str, str]:
        if asset.type != "video" or not asset.duration:
            return {}
        folder = self.paths.preview_dir(asset.project_id, asset.id)
        folder.mkdir(parents=True, exist_ok=True)
        source = self.paths.root / asset.blob_path
        duration = max(asset.duration, 0.1)
        stamps = [duration * fraction for fraction in (0.08, 0.3, 0.55, 0.8)]
        names = ["keyframe_01.jpg", "keyframe_02.jpg", "keyframe_03.jpg", "keyframe_04.jpg"]
        frames: list[Path] = []
        previews: dict[str, str] = {}
        for name, stamp in zip(names, stamps, strict=True):
            target = folder / name
            extract_frame(source, min(stamp, max(duration - 0.05, 0)), target)
            frames.append(target)
            previews[name.removesuffix(".jpg")] = str(target.relative_to(self.paths.root).as_posix())
        poster = folder / "poster.jpg"
        extract_frame(source, min(duration * 0.08, max(duration - 0.05, 0)), poster)
        previews["poster"] = str(poster.relative_to(self.paths.root).as_posix())
        sheet = folder / "contact_sheet.jpg"
        contact_sheet(frames, sheet)
        previews["contact_sheet"] = str(sheet.relative_to(self.paths.root).as_posix())
        return previews
