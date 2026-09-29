"""Dependency-aware caching and versioning for cartoon scenes."""

from __future__ import annotations

from pathlib import Path

from app.renderer.cachekey import visual_cache_key
from app.renderer.cartoon.compile import compile_cartoon_scene
from tests.cartoonkit import cartoon_project, register_backdrop, register_character, write_svg
from tests.test_incremental import ColorRenderer


def _key(ctx, project_id: str, scene_id: str) -> str:
    project = ctx.projects.get(project_id)
    scene = ctx.scenes.get_model(project_id, scene_id)
    assets = ctx.assets.map_assets(project_id)
    compiled = compile_cartoon_scene(scene, project, assets, ctx.characters.map_characters(project_id))
    return visual_cache_key(
        project,
        scene,
        assets,
        profile="final",
        width=project.width,
        height=project.height,
        crf=20,
        compiled=compiled,
    )


def _two_scenes(ctx, tmp_path: Path) -> str:
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    register_character(ctx, project_id, tmp_path, "sam", fill="#4A7FC9")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 0.5,
            "transition_out": {"type": "cut", "duration": 0},
            "cartoon": {
                "background": {"asset_id": "office"},
                "characters": [{"character_id": "raj", "expression": "angry"}],
                "dialogue": [{"dialogue_id": "d1", "character_id": "raj", "text": "Who did this?", "duration": 0.5}],
            },
        },
    )
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_02",
            "duration": 0.5,
            "cartoon": {
                "background": {"asset_id": "office"},
                "characters": [{"character_id": "sam", "expression": "happy"}],
            },
        },
    )
    return project_id


def test_the_cache_key_is_stable_for_an_unchanged_cartoon_scene(ctx, tmp_path: Path):
    project_id = _two_scenes(ctx, tmp_path)
    assert _key(ctx, project_id, "scene_01") == _key(ctx, project_id, "scene_01")


def test_editing_dialogue_invalidates_only_that_scene(ctx, tmp_path: Path):
    project_id = _two_scenes(ctx, tmp_path)
    before = _key(ctx, project_id, "scene_01"), _key(ctx, project_id, "scene_02")
    ctx.cartoon.update_dialogue(project_id, "scene_01", "d1", {"text": "Who deployed this?"})
    after = _key(ctx, project_id, "scene_01"), _key(ctx, project_id, "scene_02")

    assert after[0] != before[0]
    assert after[1] == before[1]


def test_replacing_a_character_asset_invalidates_only_the_scenes_that_draw_it(ctx, tmp_path: Path):
    project_id = _two_scenes(ctx, tmp_path)
    before = _key(ctx, project_id, "scene_01"), _key(ctx, project_id, "scene_02")

    replacement = write_svg(tmp_path / "imports" / "raj_angry_v2.svg", "#7A1F1F")
    ctx.characters.register_asset(
        project_id, "raj", str(replacement), role="character_expression", key="angry", asset_id="raj_angry", replace=True
    )
    after = _key(ctx, project_id, "scene_01"), _key(ctx, project_id, "scene_02")

    assert after[0] != before[0]
    assert after[1] == before[1]


def test_editing_the_character_record_invalidates_the_scenes_that_place_it(ctx, tmp_path: Path):
    project_id = _two_scenes(ctx, tmp_path)
    before = _key(ctx, project_id, "scene_01"), _key(ctx, project_id, "scene_02")
    ctx.characters.update(project_id, "raj", {"default_size": 0.7})
    after = _key(ctx, project_id, "scene_01"), _key(ctx, project_id, "scene_02")

    assert after[0] != before[0]
    assert after[1] == before[1]


def test_the_dependency_graph_links_characters_scenes_and_assets(ctx, tmp_path: Path):
    project_id = _two_scenes(ctx, tmp_path)
    scenes = ctx.scenes.map_scenes(project_id)
    characters = ctx.characters.map_characters(project_id)
    graph = ctx.dependencies.character_graph(scenes)

    assert graph["raj"] == ["scene_01"]
    assert graph["sam"] == ["scene_02"]
    assert ctx.dependencies.scenes_for_character(scenes, "raj") == ["scene_01"]
    assert ctx.dependencies.scenes_for_character_asset(scenes, characters, "raj_angry") == ["scene_01"]
    assert ctx.asset_users(project_id, "office") == ["scene_01", "scene_02"]
    assert ctx.character_users(project_id, "sam") == ["scene_02"]


def test_a_cartoon_project_renders_incrementally(ctx, tmp_path: Path):
    ctx.renders.renderer = ColorRenderer()
    project_id = _two_scenes(ctx, tmp_path)

    first = ctx.renders.render_project(project_id, wait=True)
    assert first["report"]["rendered"] == ["scene_01", "scene_02"]

    ctx.cartoon.update_dialogue(project_id, "scene_01", "d1", {"text": "Own up, please."})
    second = ctx.renders.render_project(project_id, wait=True)
    assert second["report"]["rendered"] == ["scene_01"]
    assert second["report"]["cached"] == ["scene_02"]


def test_versions_capture_and_restore_characters(ctx, tmp_path: Path):
    project_id = _two_scenes(ctx, tmp_path)
    version = ctx.versions.create(project_id, label="cast-locked")
    assert "raj" in ctx.versions.get(project_id, version["version_id"])["characters"]

    ctx.characters.update(project_id, "raj", {"name": "Rajesh"})
    ctx.characters.create(project_id, {"character_id": "extra", "name": "Extra"})
    assert ctx.characters.get_dict(project_id, "raj")["name"] == "Rajesh"

    ctx.versions.restore(project_id, version["version_id"])
    assert ctx.characters.get_dict(project_id, "raj")["name"] == "Raj"
    assert [item["character_id"] for item in ctx.characters.list_characters(project_id)["characters"]] == ["raj", "sam"]


def test_standard_scene_cache_keys_ignore_cartoon_support(ctx, tmp_path: Path):
    project = ctx.projects.create("Plain", preset="square", fps=12)
    project_id = project["project_id"]
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "plain",
            "duration": 1,
            "layers": [{"id": "line", "type": "text", "content": "Hello", "start": 0, "duration": 1}],
        },
    )
    scene = ctx.scenes.get_model(project_id, "plain")
    assets = ctx.assets.map_assets(project_id)
    compiled = compile_cartoon_scene(scene, ctx.projects.get(project_id), assets, {})

    fixed = {"profile": "final", "width": project["width"], "height": project["height"], "crf": 20}
    # Passing the compiler result for a standard scene must not perturb the key.
    assert visual_cache_key(ctx.projects.get(project_id), scene, assets, **fixed) == visual_cache_key(
        ctx.projects.get(project_id), scene, assets, compiled=compiled, **fixed
    )
