"""Shared cartoon fixtures: tiny deterministic artwork and a two character project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 200" width="100" height="200">'
    '<rect width="100" height="200" rx="12" fill="{fill}"/>'
    '<circle cx="50" cy="45" r="30" fill="#F6E0C8"/>'
    "</svg>"
)


def write_svg(path: Path, fill: str) -> Path:
    path.write_text(SVG.format(fill=fill), encoding="utf-8")
    return path


def write_png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (64, 96)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def cartoon_project(ctx, tmp_path: Path, *, name: str = "Cartoon", fps: int = 12) -> str:
    project = ctx.projects.create(name, preset="square", fps=fps, width=160, height=160, mode="cartoon")
    return project["project_id"]


def register_character(
    ctx,
    project_id: str,
    tmp_path: Path,
    character_id: str,
    *,
    expressions: tuple[str, ...] = ("angry", "happy"),
    poses: tuple[str, ...] = ("standing",),
    parts: tuple[str, ...] = (),
    fill: str = "#C96D4A",
) -> dict[str, Any]:
    imports = tmp_path / "imports"
    ctx.characters.create(
        project_id,
        {
            "character_id": character_id,
            "name": character_id.title(),
            "description": f"{character_id} the developer",
            "traits": ["sarcastic"],
            "visual_style": "2D comic",
        },
    )
    base = write_svg(imports / f"{character_id}_base.svg", fill)
    ctx.characters.register_asset(
        project_id, character_id, str(base), role="character_base", asset_id=f"{character_id}_base"
    )
    for expression in expressions:
        path = write_svg(imports / f"{character_id}_{expression}.svg", fill)
        ctx.characters.register_asset(
            project_id,
            character_id,
            str(path),
            role="character_expression",
            key=expression,
            asset_id=f"{character_id}_{expression}",
        )
    for pose in poses:
        path = write_svg(imports / f"{character_id}_{pose}.svg", fill)
        ctx.characters.register_asset(
            project_id,
            character_id,
            str(path),
            role="character_pose",
            key=pose,
            asset_id=f"{character_id}_{pose}",
        )
    for part in parts:
        path = write_svg(imports / f"{character_id}_{part}.svg", fill)
        ctx.characters.register_asset(
            project_id,
            character_id,
            str(path),
            role="character_part",
            key=part,
            asset_id=f"{character_id}_{part}",
        )
    return ctx.characters.get_dict(project_id, character_id)


def register_backdrop(ctx, project_id: str, tmp_path: Path, asset_id: str = "office") -> str:
    path = write_png(tmp_path / "imports" / f"{asset_id}.png", (46, 58, 76), size=(160, 160))
    ctx.assets.register(project_id, str(path), asset_id=asset_id, semantic_type="background")
    return asset_id


def register_prop(ctx, project_id: str, tmp_path: Path, asset_id: str = "pizza_box") -> str:
    path = write_svg(tmp_path / "imports" / f"{asset_id}.svg", "#D8B24C")
    ctx.assets.register(project_id, str(path), asset_id=asset_id, semantic_type="prop")
    return asset_id


def argument_scene(scene_id: str = "scene_01", duration: float = 4.0) -> dict[str, Any]:
    """Raj accuses Sam. Used by several tests."""
    return {
        "scene_id": scene_id,
        "duration": duration,
        "cartoon": {
            "background": {"asset_id": "office"},
            "characters": [
                {
                    "character_id": "raj",
                    "expression": "angry",
                    "position": {"x": 0.35, "y": 0.78},
                    "actions": [{"type": "walk_in", "direction": "left", "duration": 1.5}],
                },
                {
                    "character_id": "sam",
                    "expression": "happy",
                    "position": {"x": 0.68, "y": 0.78},
                },
            ],
            "dialogue": [
                {
                    "dialogue_id": "d1",
                    "character_id": "raj",
                    "text": "WHO BROKE PRODUCTION?",
                    "start": 1.5,
                    "duration": 1.5,
                }
            ],
            "camera": {"shot": "medium", "focus": "raj"},
        },
    }
