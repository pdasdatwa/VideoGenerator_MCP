"""Cache keys for visual scene renders."""

from __future__ import annotations

import hashlib
from typing import Any

from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.renderer.scene_graph import canonical_json, referenced_asset_ids, visual_dict
from app.renderer.version import RENDERER_VERSION


def visual_cache_key(
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
    """Hash of everything that changes the picture.

    A cartoon scene is keyed on its compiled layers, the compiled asset hashes, and the compiler
    version, so a dialogue edit or a swapped character asset invalidates exactly the scenes that
    draw it. A standard scene is keyed exactly as it was before cartoon mode existed.
    """
    visual_ids = referenced_asset_ids(scene)
    hashes = {asset_id: assets[asset_id].sha256 for asset_id in visual_ids if asset_id in assets}
    payload: dict[str, Any] = {
        "scene": visual_dict(scene),
        "assets": hashes,
        "renderer_version": RENDERER_VERSION,
        "profile": {
            "name": profile,
            "width": width,
            "height": height,
            "fps": project.fps,
            "crf": crf,
        },
        "global_effects": project.global_effects.model_dump(),
        "safe_area": project.safe_area.model_dump(),
    }
    if scene.cartoon is not None and compiled is not None:
        payload["cartoon"] = {
            "compiler_version": compiled.compiler_version,
            "compiled": visual_dict(compiled.scene),
            "camera": compiled.camera,
            "assets": {
                asset_id: assets[asset_id].sha256
                for asset_id in compiled.asset_ids
                if asset_id in assets
            },
        }
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return digest
