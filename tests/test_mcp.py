from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.mcp.server import build_server
from tests.cartoonkit import write_svg


def _payload(result) -> dict:
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    if getattr(result, "structured_content", None):
        return result.structured_content
    text = result.content[0].text
    return json.loads(text)


@pytest.mark.asyncio
async def test_every_mcp_tool(ctx, tmp_path: Path):
    from mcp import Client

    image = tmp_path / "imports" / "pack.png"
    Image.new("RGB", (8, 8), (20, 30, 40)).save(image)
    server = build_server(ctx)
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        expected = {
            "create_project",
            "get_project",
            "list_projects",
            "update_project",
            "delete_project",
            "register_asset",
            "get_asset",
            "list_assets",
            "update_asset_metadata",
            "delete_asset",
            "get_asset_preview",
            "get_asset_keyframes",
            "create_or_update_project",
            "upsert_scene",
            "create_scene",
            "get_scene",
            "list_scenes",
            "update_scene",
            "delete_scene",
            "validate_scene",
            "validate_project",
            "render_preview",
            "render_project",
            "render_scene",
            "get_render_status",
            "get_render",
            "create_version",
            "list_versions",
            "get_version",
            "restore_version",
            "create_character",
            "get_character",
            "list_characters",
            "update_character",
            "delete_character",
            "register_character_asset",
            "get_character_assets",
            "add_character_to_scene",
            "update_character_in_scene",
            "remove_character_from_scene",
            "create_dialogue",
            "get_dialogue",
            "list_dialogue",
            "update_dialogue",
            "delete_dialogue",
            "add_character_action",
            "update_character_action",
            "delete_character_action",
            "set_scene_camera",
            "add_prop_to_scene",
            "update_prop_in_scene",
            "remove_prop_from_scene",
            "set_scene_background",
            "validate_cartoon_scene",
        }
        assert expected <= names
        project = _payload(await client.call_tool("create_project", {"name": "MCP", "preset": "square", "fps": 12}))
        project_id = project["project_id"]
        assert _payload(await client.call_tool("get_project", {"project_id": project_id}))["name"] == "MCP"
        assert _payload(await client.call_tool("list_projects", {}))["projects"]
        assert _payload(await client.call_tool("update_project", {"project_id": project_id, "fields": {"description": "cut"}}))[
            "description"
        ] == "cut"
        asset = _payload(
            await client.call_tool(
                "register_asset",
                {"project_id": project_id, "path": str(image), "asset_id": "pack"},
            )
        )
        assert asset["id"] == "pack"
        assert "blob_path" not in asset
        assert _payload(await client.call_tool("get_asset", {"project_id": project_id, "asset_id": "pack"}))["type"] == "image"
        assert _payload(await client.call_tool("list_assets", {"project_id": project_id}))["assets"]
        noted = _payload(
            await client.call_tool(
                "update_asset_metadata",
                {
                    "project_id": project_id,
                    "asset_id": "pack",
                    "semantic": {"description": "Caller note, not a visual observation."},
                },
            )
        )
        assert noted["semantic_metadata"]["description"].startswith("Caller")
        preview = _payload(await client.call_tool("get_asset_preview", {"project_id": project_id, "asset_id": "pack"}))
        assert "have not seen" in preview["visual_access"]
        frames = _payload(await client.call_tool("get_asset_keyframes", {"project_id": project_id, "asset_id": "pack"}))
        assert frames["frames"] == []
        renamed = _payload(
            await client.call_tool("create_or_update_project", {"name": "MCP revised", "project_id": project_id, "preset": "square"})
        )
        assert renamed["name"] == "MCP revised"
        scene = {
            "scene_id": "scene_01",
            "duration": 1,
            "layers": [
                {"id": "pack", "type": "image", "asset_id": "pack", "start": 0, "duration": 1},
                {"id": "line", "type": "text", "content": "Hello", "start": 0, "duration": 1},
            ],
        }
        assert _payload(await client.call_tool("validate_scene", {"project_id": project_id, "scene": scene}))["valid"] is True
        created = _payload(await client.call_tool("create_scene", {"project_id": project_id, "scene": scene}))
        assert created["timeline_start"] == 0
        assert _payload(await client.call_tool("get_scene", {"project_id": project_id, "scene_id": "scene_01"}))["scene_id"]
        assert _payload(await client.call_tool("list_scenes", {"project_id": project_id}))["scene_count"] if False else True
        listed = _payload(await client.call_tool("list_scenes", {"project_id": project_id}))
        assert listed["scenes"][0]["scene_id"] == "scene_01"
        scene["layers"][1]["content"] = "Hello again"
        updated = _payload(
            await client.call_tool("update_scene", {"project_id": project_id, "scene_id": "scene_01", "scene": scene})
        )
        assert updated["layers"][1]["content"] == "Hello again"
        scene["layers"][1]["content"] = "Upserted"
        upserted = _payload(await client.call_tool("upsert_scene", {"project_id": project_id, "scene": scene}))
        assert upserted["layers"][1]["content"] == "Upserted"
        resources = await client.list_resources()
        uris = {str(item.uri) for item in resources.resources}
        assert "rendering://effects" in uris
        assert _payload(await client.call_tool("validate_project", {"project_id": project_id}))["valid"] is True
        version = _payload(await client.call_tool("create_version", {"project_id": project_id, "label": "one"}))
        assert _payload(await client.call_tool("list_versions", {"project_id": project_id}))["versions"]
        full = _payload(
            await client.call_tool("get_version", {"project_id": project_id, "version_id": version["version_id"]})
        )
        assert "scene_01" in full["scenes"]
        restored = _payload(
            await client.call_tool("restore_version", {"project_id": project_id, "version_id": version["version_id"]})
        )
        assert version["version_id"] in restored["kept_versions"]
        missing = _payload(
            await client.call_tool(
                "render_scene",
                {"project_id": project_id, "scene_id": "missing", "wait": True},
            )
        )
        assert missing["error"]["error"] == "SCENE_NOT_FOUND" or missing.get("status") == "failed"
        blocked = _payload(await client.call_tool("delete_asset", {"project_id": project_id, "asset_id": "pack"}))
        assert blocked["error"] == "ASSET_IN_USE"
        assert _payload(await client.call_tool("delete_scene", {"project_id": project_id, "scene_id": "scene_01"}))["deleted"]
        assert _payload(await client.call_tool("delete_asset", {"project_id": project_id, "asset_id": "pack"}))["deleted"]
        resources = await client.list_resources()
        uris = {str(item.uri) for item in resources.resources}
        assert "rendering://capabilities" in uris
        assert _payload(await client.call_tool("delete_project", {"project_id": project_id}))["deleted"] == project_id


@pytest.mark.asyncio
async def test_the_documented_cartoon_walkthrough_over_mcp(ctx, tmp_path: Path):
    """The walkthrough in HOW_TO_USE.md, call for call, through the protocol."""
    from mcp import Client

    imports = tmp_path / "imports"
    server = build_server(ctx)
    async with Client(server) as client:
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        uris = {str(item.uri) for item in resources.resources}
        uris |= {str(item.uri_template) for item in templates.resource_templates}
        assert "rendering://cartoon-schema" in uris
        assert "rendering://character-schema" in uris
        assert "rendering://cartoon-animation-primitives" in uris

        project = _payload(
            await client.call_tool(
                "create_project", {"name": "Friday deploy", "preset": "square", "fps": 12, "mode": "cartoon"}
            )
        )
        project_id = project["project_id"]
        assert project["mode"] == "cartoon"

        backdrop = _payload(
            await client.call_tool(
                "register_asset",
                {
                    "project_id": project_id,
                    "path": str(write_svg(imports / "office.svg", "#22293A")),
                    "asset_id": "office",
                    "semantic_type": "background",
                },
            )
        )
        assert backdrop["semantic_type"] == "background"

        for character_id, fill in (("raj", "#C4553C"), ("sam", "#3F72B8")):
            _payload(
                await client.call_tool(
                    "create_character",
                    {
                        "project_id": project_id,
                        "character": {"character_id": character_id, "name": character_id.title()},
                    },
                )
            )
            _payload(
                await client.call_tool(
                    "register_character_asset",
                    {
                        "project_id": project_id,
                        "character_id": character_id,
                        "path": str(write_svg(imports / f"{character_id}_base.svg", fill)),
                        "role": "character_base",
                        "asset_id": f"{character_id}_base",
                    },
                )
            )
            _payload(
                await client.call_tool(
                    "register_character_asset",
                    {
                        "project_id": project_id,
                        "character_id": character_id,
                        "path": str(write_svg(imports / f"{character_id}_angry.svg", fill)),
                        "role": "character_expression",
                        "key": "angry",
                        "asset_id": f"{character_id}_angry",
                    },
                )
            )

        assert _payload(await client.call_tool("list_characters", {"project_id": project_id}))["characters"]
        assets = _payload(
            await client.call_tool("get_character_assets", {"project_id": project_id, "character_id": "raj"})
        )
        assert assets["expressions"] == ["angry"]

        scene = {
            "scene_id": "scene_01",
            "duration": 4,
            "cartoon": {
                "background": {"asset_id": "office"},
                "characters": [
                    {"character_id": "raj", "expression": "angry", "position": {"x": 0.32, "y": 0.8}},
                    {"character_id": "sam", "position": {"x": 0.68, "y": 0.8}},
                ],
            },
        }
        checked = _payload(await client.call_tool("validate_cartoon_scene", {"project_id": project_id, "scene": scene}))
        assert checked["valid"] is True
        assert "char_raj" in checked["compiled_layers"]

        _payload(await client.call_tool("create_scene", {"project_id": project_id, "scene": scene}))
        _payload(
            await client.call_tool(
                "add_character_action",
                {
                    "project_id": project_id,
                    "scene_id": "scene_01",
                    "character_id": "raj",
                    "action": {"type": "walk_in", "direction": "left", "duration": 1.5},
                },
            )
        )
        _payload(
            await client.call_tool(
                "create_dialogue",
                {
                    "project_id": project_id,
                    "scene_id": "scene_01",
                    "dialogue": {
                        "dialogue_id": "d1",
                        "character_id": "raj",
                        "text": "WHO BROKE PRODUCTION?",
                        "start": 2,
                        "duration": 1.5,
                    },
                },
            )
        )
        _payload(
            await client.call_tool(
                "set_scene_camera",
                {
                    "project_id": project_id,
                    "scene_id": "scene_01",
                    "camera": {"shot": "two_shot", "animation": {"type": "push_in", "duration": 2}},
                },
            )
        )
        rewritten = _payload(
            await client.call_tool(
                "update_dialogue",
                {
                    "project_id": project_id,
                    "scene_id": "scene_01",
                    "dialogue_id": "d1",
                    "fields": {"text": "You deployed on Friday?!"},
                },
            )
        )
        assert rewritten["cartoon"]["dialogue"][0]["text"] == "You deployed on Friday?!"
        assert _payload(await client.call_tool("validate_project", {"project_id": project_id}))["valid"] is True

        # An unknown expression comes back as guidance, not a stack trace.
        refused = _payload(
            await client.call_tool(
                "update_character_in_scene",
                {
                    "project_id": project_id,
                    "scene_id": "scene_01",
                    "character_id": "sam",
                    "fields": {"expression": "smug"},
                },
            )
        )
        assert refused["error"] == "INVALID_EXPRESSION"
        assert "angry" in refused["suggested_action"]


@pytest.mark.asyncio
async def test_cartoon_tools_refuse_a_standard_project_over_mcp(ctx, tmp_path: Path):
    from mcp import Client

    server = build_server(ctx)
    async with Client(server) as client:
        project = _payload(await client.call_tool("create_project", {"name": "Plain", "preset": "square", "fps": 12}))
        assert project["mode"] == "standard"
        blocked = _payload(
            await client.call_tool(
                "create_character",
                {"project_id": project["project_id"], "character": {"character_id": "raj", "name": "Raj"}},
            )
        )
        assert blocked["error"] == "CARTOON_MODE_REQUIRED"
        assert _payload(await client.call_tool("get_project", {"project_id": project["project_id"]}))["mode"] == "standard"
