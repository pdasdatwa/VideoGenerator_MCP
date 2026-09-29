"""MCP resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.mcp.catalog import (
    CAPABILITIES,
    CARTOON_SCENE_EXAMPLE,
    CHARACTER_EXAMPLE,
    EFFECTS,
    SCENE_EXAMPLE,
)
from app.renderer.cartoon.names import ACTION_SPECS, CAMERA_MOVES, CAMERA_SHOTS
from app.services import AppContext


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2)


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.resource("rendering://capabilities")
    def capabilities() -> str:
        return _json(CAPABILITIES)

    @mcp.resource("rendering://scene-schema")
    def scene_schema() -> str:
        return _json(
            {
                "description": "Submit this shape to create_scene and update_scene. Coordinates are normalized.",
                "example": SCENE_EXAMPLE,
                "layer_types": CAPABILITIES["supported_layer_types"],
                "transform_forms": ["static number or {x,y}", "{from, to}", "{keyframes: [{time, value}]}"],
            }
        )

    @mcp.resource("rendering://animation-primitives")
    def animation_primitives() -> str:
        return _json({"animations": CAPABILITIES["animations"], "easing": CAPABILITIES["easing"]})

    @mcp.resource("rendering://cartoon-schema")
    def cartoon_schema() -> str:
        return _json(
            {
                "description": (
                    "The cartoon block attaches to an ordinary scene on a project with mode='cartoon'. "
                    "It compiles into standard layers plus a camera track, so the renderer, cache, and "
                    "versioning are the same ones standard mode uses."
                ),
                "example": CARTOON_SCENE_EXAMPLE,
                "fields": {
                    "background": "asset_id, or background/midground/foreground plates with parallax 0 to 1, plus color and fit.",
                    "characters": "Placements of registered characters: character_id, pose, expression, position, scale, size, anchor, rotation, opacity, z_index, start, duration, accessories, actions.",
                    "dialogue": "Editable lines: dialogue_id, character_id, text, start, duration, style, animation. Omit character_id for a narrator caption.",
                    "camera": "shot, zoom, position, focus, rotation, animation, keyframes.",
                    "props": "prop_id, asset_id, placement fields, and an optional animation action.",
                },
                "capabilities": CAPABILITIES["cartoon"],
                "notes": [
                    "A cartoon scene may also carry ordinary layers. They render above the compiled cartoon layers unless you set z_index.",
                    "Compiled layer ids use the prefixes cbg_, char_, prop_, and dlg_. Do not use those for your own layers.",
                    "Call validate_cartoon_scene to prove a scene compiles before saving it.",
                ],
            }
        )

    @mcp.resource("rendering://character-schema")
    def character_schema() -> str:
        return _json(
            {
                "description": (
                    "A character is an identity that persists across scenes. Scenes reference character_id "
                    "and describe only that appearance."
                ),
                "example": CHARACTER_EXAMPLE,
                "asset_roles": CAPABILITIES["cartoon"]["asset_roles"],
                "character_parts": CAPABILITIES["cartoon"]["character_parts"],
                "asset_resolution_order": CAPABILITIES["cartoon"]["asset_resolution_order"],
                "notes": [
                    "Register artwork with register_character_asset. This server generates no images.",
                    "name, description, traits, visual_style, and metadata are your text and are not verified.",
                    "Register mouth_open and mouth_closed parts to get mouth movement from the talk action.",
                ],
            }
        )

    @mcp.resource("rendering://cartoon-animation-primitives")
    def cartoon_animation_primitives() -> str:
        return _json(
            {
                "description": (
                    "Named, deterministic cartoon actions. Direct with these instead of writing keyframes. "
                    "The compiler samples them at a fixed rate independent of project fps."
                ),
                "actions": {
                    name: {
                        "family": spec["family"],
                        "parameters": ["start", "duration", *spec["parameters"]],
                        "summary": spec["summary"],
                    }
                    for name, spec in sorted(ACTION_SPECS.items())
                },
                "families": CAPABILITIES["cartoon"]["action_families"],
                "directions": CAPABILITIES["cartoon"]["directions"],
                "camera_shots": CAMERA_SHOTS,
                "camera_animations": CAMERA_MOVES,
                "compiler_version": CAPABILITIES["cartoon"]["compiler_version"],
                "notes": [
                    "intensity scales the amount, default 1. repeat sets cycle count for loops.",
                    "Actions on the same character compose: offsets add, scale and opacity multiply.",
                    "An action must finish inside the scene duration.",
                ],
            }
        )

    @mcp.resource("rendering://effects")
    def effects() -> str:
        return _json(EFFECTS)

    @mcp.resource("rendering://supported-assets")
    def supported_assets() -> str:
        return _json(
            {
                "extensions": CAPABILITIES["supported_assets"],
                "note": "Inspection is local. This server does not describe image or video content.",
            }
        )

    @mcp.resource("rendering://project/{project_id}")
    def project_resource(project_id: str) -> str:
        return _json(ctx.projects.get_dict(project_id))

    @mcp.resource("rendering://project/{project_id}/scene/{scene_id}")
    def scene_resource(project_id: str, scene_id: str) -> str:
        return _json(ctx.scenes.get(project_id, scene_id))

    @mcp.resource("rendering://project/{project_id}/character/{character_id}")
    def character_resource(project_id: str, character_id: str) -> str:
        return _json(ctx.characters.get_dict(project_id, character_id))

    @mcp.resource("rendering://asset/{asset_id}")
    def asset_resource(asset_id: str) -> str:
        matches = []
        for project in ctx.projects.list_projects():
            folder = ctx.settings.data_dir / "projects" / project["project_id"] / "assets" / f"{asset_id}.json"
            if folder.exists():
                matches.append(ctx.assets.public(ctx.assets.get(project["project_id"], asset_id)))
        if not matches:
            return _json({"error": "ASSET_NOT_FOUND", "asset_id": asset_id})
        return _json(matches[0] if len(matches) == 1 else {"matches": matches})

    @mcp.resource("rendering://asset/{asset_id}/keyframes")
    def asset_keyframes(asset_id: str) -> str:
        return _json(_keyframe_index(ctx, asset_id))

    @mcp.resource("rendering://asset/{asset_id}/preview/{name}")
    def asset_preview(asset_id: str, name: str) -> bytes:
        path = _preview_file(ctx, asset_id, name)
        return path.read_bytes()


def _keyframe_index(ctx: AppContext, asset_id: str) -> dict[str, Any]:
    for project in ctx.projects.list_projects():
        project_id = project["project_id"]
        record = ctx.settings.data_dir / "projects" / project_id / "assets" / f"{asset_id}.json"
        if not record.exists():
            continue
        asset = ctx.assets.get(project_id, asset_id)
        names = [name for name in asset.preview if name == "poster" or name.startswith("keyframe_") or name == "contact_sheet"]
        return {
            "asset_id": asset_id,
            "project_id": project_id,
            "frames": [
                {"name": name, "resource": f"rendering://asset/{asset_id}/preview/{name}"}
                for name in names
            ],
        }
    return {"error": "ASSET_NOT_FOUND", "asset_id": asset_id}


def _preview_file(ctx: AppContext, asset_id: str, name: str) -> Path:
    from app.errors import MarketingError

    for project in ctx.projects.list_projects():
        project_id = project["project_id"]
        record = ctx.settings.data_dir / "projects" / project_id / "assets" / f"{asset_id}.json"
        if not record.exists():
            continue
        asset = ctx.assets.get(project_id, asset_id)
        if name == "original":
            return ctx.settings.data_dir / asset.blob_path
        relative = asset.preview.get(name)
        if relative:
            return ctx.settings.data_dir / relative
        raise MarketingError(
            "PREVIEW_NOT_FOUND",
            f"Preview '{name}' does not exist for {asset_id}.",
            suggested_action="Call get_asset_preview and use one of the returned resource names.",
            asset_id=asset_id,
        )
    raise MarketingError(
        "ASSET_NOT_FOUND",
        f"Asset {asset_id} does not exist.",
        suggested_action="Register the asset first.",
        asset_id=asset_id,
    )
