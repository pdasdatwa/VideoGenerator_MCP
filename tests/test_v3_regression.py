"""Standard mode must behave exactly as it did before cartoon mode existed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.mcp.catalog import CAPABILITIES
from app.models.scene import Scene
from app.renderer.cachekey import visual_cache_key
from app.renderer.scene_graph import build_scene_props, referenced_asset_ids, visual_dict
from app.renderer.version import RENDERER_VERSION
from tests.test_incremental import ColorRenderer


def _standard_scene(ctx, tmp_path: Path) -> tuple[str, Scene]:
    project = ctx.projects.create("Standard", preset="portrait", fps=24)
    project_id = project["project_id"]
    image = tmp_path / "imports" / "hero.png"
    Image.new("RGB", (32, 48), (120, 90, 60)).save(image)
    ctx.assets.register(project_id, str(image), asset_id="hero")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 2,
            "background": {"type": "color", "value": "#000000"},
            "layers": [
                {"id": "hero", "type": "image", "asset_id": "hero", "start": 0, "duration": 2},
                {"id": "line", "type": "text", "content": "Hello", "start": 0, "duration": 2},
            ],
        },
    )
    return project_id, ctx.scenes.get_model(project_id, "scene_01")


def test_a_standard_project_record_gains_only_a_mode_field(ctx, tmp_path: Path):
    project = ctx.projects.create("Standard", preset="square", fps=12)
    assert project["mode"] == "standard"
    assert {"project_id", "name", "preset", "fps", "width", "height"} <= set(project)


def test_standard_scene_records_carry_no_cartoon_payload(ctx, tmp_path: Path):
    project_id, model = _standard_scene(ctx, tmp_path)
    stored = ctx.scenes.get(project_id, "scene_01")

    assert stored["cartoon"] is None
    assert "cartoon" not in visual_dict(model)
    assert referenced_asset_ids(model) == ["hero"]


def test_standard_scene_props_have_no_camera(ctx, tmp_path: Path):
    project_id, model = _standard_scene(ctx, tmp_path)
    project = ctx.projects.get(project_id)
    props = build_scene_props(
        project,
        model,
        ctx.assets.map_assets(project_id),
        width=project.width,
        height=project.height,
        renderer_version=RENDERER_VERSION,
        crf=20,
        data_root=ctx.settings.data_dir,
    )

    assert "camera" not in props
    assert props["sceneId"] == "scene_01"
    assert [layer["id"] for layer in props["layers"]] == ["hero", "line"]


def test_the_standard_cache_key_depends_only_on_v2_inputs(ctx, tmp_path: Path):
    project_id, model = _standard_scene(ctx, tmp_path)
    project = ctx.projects.get(project_id)
    assets = ctx.assets.map_assets(project_id)
    fixed = {"profile": "final", "width": project.width, "height": project.height, "crf": 20}
    baseline = visual_cache_key(project, model, assets, **fixed)

    # Registering a character elsewhere on the project must not move a standard scene's key.
    ctx.projects.update(project_id, {"mode": "cartoon"})
    ctx.characters.create(project_id, {"character_id": "raj", "name": "Raj"})
    assert visual_cache_key(ctx.projects.get(project_id), model, assets, **fixed) == baseline


def test_standard_scenes_render_and_cache_the_way_they_always_did(ctx, tmp_path: Path):
    ctx.renders.renderer = ColorRenderer()
    project = ctx.projects.create("Standard", preset="square", fps=12)
    project_id = project["project_id"]
    for index in range(2):
        ctx.scenes.create(
            project_id,
            {
                "scene_id": f"scene_0{index + 1}",
                "duration": 0.5,
                "transition_out": {"type": "cut", "duration": 0},
                "layers": [
                    {"id": "line", "type": "text", "content": str(index), "start": 0, "duration": 0.5}
                ],
            },
        )

    first = ctx.renders.render_project(project_id, wait=True)
    assert first["report"]["rendered"] == ["scene_01", "scene_02"]
    assert first["report"]["warnings"] == []

    second = ctx.renders.render_project(project_id, wait=True)
    assert second["report"]["rendered"] == []
    assert second["report"]["cached"] == ["scene_01", "scene_02"]


def test_capabilities_keep_every_v2_key_and_add_cartoon_additively():
    for key in (
        "supported_layer_types",
        "supported_assets",
        "animations",
        "easing",
        "transitions",
        "effects",
    ):
        assert key in CAPABILITIES

    assert CAPABILITIES["default_mode"] == "standard"
    assert CAPABILITIES["modes"]["standard"] is True
    assert CAPABILITIES["cartoon"]["requires"] == "project mode='cartoon'"


def test_versions_of_a_standard_project_carry_an_empty_cast(ctx, tmp_path: Path):
    project_id, _ = _standard_scene(ctx, tmp_path)
    version = ctx.versions.create(project_id, label="v1")
    full = ctx.versions.get(project_id, version["version_id"])

    assert full["characters"] == {}
    assert "scene_01" in full["scenes"]
    ctx.versions.restore(project_id, version["version_id"])
    assert ctx.scenes.get(project_id, "scene_01")["scene_id"] == "scene_01"


def test_existing_scene_files_without_a_mode_or_cartoon_field_still_load(ctx, tmp_path: Path):
    """A project saved by V2 has no mode and its scenes have no cartoon key."""
    project_id, _ = _standard_scene(ctx, tmp_path)
    project_file = ctx.settings.data_dir / "projects" / project_id / "project.json"
    payload = json.loads(project_file.read_text(encoding="utf-8"))
    payload.pop("mode", None)
    project_file.write_text(json.dumps(payload), encoding="utf-8")

    scene_file = ctx.settings.data_dir / "projects" / project_id / "scenes" / "scene_01.json"
    scene_payload = json.loads(scene_file.read_text(encoding="utf-8"))
    scene_payload.pop("cartoon", None)
    scene_file.write_text(json.dumps(scene_payload), encoding="utf-8")

    assert ctx.projects.get(project_id).mode == "standard"
    assert ctx.scenes.get_model(project_id, "scene_01").cartoon is None
    assert ctx.scenes.validate_project(project_id)["valid"] is True


def test_cartoon_tools_refuse_a_standard_project_rather_than_switching_it(ctx, tmp_path: Path):
    from app.errors import MarketingError

    project_id, _ = _standard_scene(ctx, tmp_path)
    for call in (
        lambda: ctx.characters.list_characters(project_id),
        lambda: ctx.cartoon.list_dialogue(project_id, "scene_01"),
        lambda: ctx.cartoon.set_scene_camera(project_id, "scene_01", {"shot": "close_up"}),
    ):
        with pytest.raises(MarketingError) as excinfo:
            call()
        assert excinfo.value.code == "CARTOON_MODE_REQUIRED"
    assert ctx.projects.get(project_id).mode == "standard"
