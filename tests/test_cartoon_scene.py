"""Granular cartoon editing and the structured errors the validator raises."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import MarketingError
from tests.cartoonkit import (
    argument_scene,
    cartoon_project,
    register_backdrop,
    register_character,
    register_prop,
)


def _project(ctx, tmp_path: Path) -> str:
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    register_character(ctx, project_id, tmp_path, "sam", fill="#4A7FC9")
    return project_id


def _spec(ctx, project_id: str, scene_id: str = "scene_01") -> dict:
    return ctx.scenes.get(project_id, scene_id)["cartoon"]


def test_editing_dialogue_changes_only_that_line(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    ctx.scenes.create(project_id, argument_scene())
    ctx.cartoon.create_dialogue(
        project_id,
        "scene_01",
        {"dialogue_id": "d2", "character_id": "sam", "text": "It was a small change.", "start": 3, "duration": 1},
    )
    ctx.cartoon.update_dialogue(project_id, "scene_01", "d1", {"text": "You deployed on Friday?!"})

    lines = ctx.cartoon.list_dialogue(project_id, "scene_01")["dialogue"]
    assert [item["dialogue_id"] for item in lines] == ["d1", "d2"]
    assert lines[0]["text"] == "You deployed on Friday?!"
    assert lines[0]["start"] == 1.5
    assert lines[1]["text"] == "It was a small change."

    ctx.cartoon.delete_dialogue(project_id, "scene_01", "d2")
    assert [item["dialogue_id"] for item in ctx.cartoon.list_dialogue(project_id, "scene_01")["dialogue"]] == ["d1"]


def test_dialogue_is_data_and_never_touches_the_character_assets(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    ctx.scenes.create(project_id, argument_scene())
    before = ctx.characters.get_dict(project_id, "raj")["assets"]
    ctx.cartoon.update_dialogue(project_id, "scene_01", "d1", {"text": "Completely different line."})
    assert ctx.characters.get_dict(project_id, "raj")["assets"] == before


def test_scene_character_edits_keep_identity_and_drop_dialogue_on_removal(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    ctx.scenes.create(project_id, argument_scene())

    ctx.cartoon.update_character_in_scene(project_id, "scene_01", "sam", {"expression": "angry"})
    spec = _spec(ctx, project_id)
    sam = next(item for item in spec["characters"] if item["character_id"] == "sam")
    assert sam["expression"] == "angry"
    assert ctx.characters.get_dict(project_id, "sam")["name"] == "Sam"

    ctx.cartoon.remove_character_from_scene(project_id, "scene_01", "raj")
    spec = _spec(ctx, project_id)
    assert [item["character_id"] for item in spec["characters"]] == ["sam"]
    assert spec["dialogue"] == []

    with pytest.raises(MarketingError) as excinfo:
        ctx.cartoon.update_character_in_scene(project_id, "scene_01", "raj", {"expression": "angry"})
    assert excinfo.value.code == "CHARACTER_NOT_IN_SCENE"


def test_adding_a_character_twice_is_rejected(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    ctx.scenes.create(project_id, argument_scene())
    with pytest.raises(MarketingError) as excinfo:
        ctx.cartoon.add_character_to_scene(project_id, "scene_01", {"character_id": "raj"})
    assert excinfo.value.code == "DUPLICATE_CHARACTER"


def test_actions_are_addressable_after_they_are_added(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    ctx.scenes.create(
        project_id,
        {"scene_id": "s1", "duration": 4, "cartoon": {"characters": [{"character_id": "raj"}]}},
    )
    ctx.cartoon.add_character_action(project_id, "s1", "raj", {"type": "walk_in", "direction": "left"})
    ctx.cartoon.add_character_action(project_id, "s1", "raj", {"type": "wave", "start": 2})

    actions = _spec(ctx, project_id, "s1")["characters"][0]["actions"]
    assert [item["action_id"] for item in actions] == ["act_1", "act_2"]

    ctx.cartoon.update_character_action(project_id, "s1", "raj", "act_1", {"duration": 2.5})
    assert _spec(ctx, project_id, "s1")["characters"][0]["actions"][0]["duration"] == 2.5

    ctx.cartoon.delete_character_action(project_id, "s1", "raj", "act_1")
    assert [item["action_id"] for item in _spec(ctx, project_id, "s1")["characters"][0]["actions"]] == ["act_2"]

    with pytest.raises(MarketingError) as excinfo:
        ctx.cartoon.delete_character_action(project_id, "s1", "raj", "act_1")
    assert excinfo.value.code == "ACTION_NOT_FOUND"


def test_camera_props_and_background_can_be_set_and_cleared(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    register_prop(ctx, project_id, tmp_path)
    ctx.scenes.create(
        project_id,
        {"scene_id": "s1", "duration": 4, "cartoon": {"characters": [{"character_id": "raj"}]}},
    )

    ctx.cartoon.set_scene_camera(
        project_id, "s1", {"shot": "close_up", "focus": "raj", "animation": {"type": "push_in", "duration": 2}}
    )
    assert _spec(ctx, project_id, "s1")["camera"]["shot"] == "close_up"
    ctx.cartoon.set_scene_camera(project_id, "s1", None)
    assert _spec(ctx, project_id, "s1")["camera"] is None

    ctx.cartoon.add_prop_to_scene(project_id, "s1", {"prop_id": "box", "asset_id": "pizza_box"})
    ctx.cartoon.update_prop_in_scene(project_id, "s1", "box", {"position": {"x": 0.7, "y": 0.8}})
    assert _spec(ctx, project_id, "s1")["props"][0]["position"] == {"x": 0.7, "y": 0.8}
    ctx.cartoon.remove_prop_from_scene(project_id, "s1", "box")
    assert _spec(ctx, project_id, "s1")["props"] == []

    ctx.cartoon.set_scene_background(project_id, "s1", {"asset_id": "office"})
    assert _spec(ctx, project_id, "s1")["background"]["asset_id"] == "office"


def test_cartoon_scenes_are_refused_on_a_standard_project(ctx, tmp_path: Path):
    project = ctx.projects.create("Plain", preset="square", fps=12)
    with pytest.raises(MarketingError) as excinfo:
        ctx.scenes.create(
            project["project_id"],
            {"scene_id": "s1", "duration": 2, "cartoon": {"characters": [{"character_id": "raj"}]}},
        )
    assert excinfo.value.code == "CARTOON_MODE_REQUIRED"


@pytest.mark.parametrize(
    "code, cartoon",
    [
        ("CHARACTER_NOT_FOUND", {"characters": [{"character_id": "nobody"}]}),
        ("INVALID_EXPRESSION", {"characters": [{"character_id": "raj", "expression": "smug"}]}),
        ("INVALID_POSE", {"characters": [{"character_id": "raj", "pose": "crouching"}]}),
        (
            "INVALID_ACTION",
            {"characters": [{"character_id": "raj", "actions": [{"type": "moonwalk"}]}]},
        ),
        (
            "INVALID_DURATION",
            {"characters": [{"character_id": "raj", "actions": [{"type": "wave", "start": 3, "duration": 4}]}]},
        ),
        (
            "INVALID_DIALOGUE",
            {
                "characters": [{"character_id": "raj"}],
                "dialogue": [{"dialogue_id": "d1", "character_id": "ghost", "text": "Hi", "duration": 1}],
            },
        ),
        (
            "INVALID_DIALOGUE",
            {
                "characters": [{"character_id": "raj"}],
                "dialogue": [
                    {"dialogue_id": "d1", "text": "a", "duration": 1},
                    {"dialogue_id": "d1", "text": "b", "duration": 1},
                ],
            },
        ),
        ("INVALID_CAMERA", {"characters": [{"character_id": "raj"}], "camera": {"shot": "dolly_zoom"}}),
        (
            "INVALID_ASSET_REFERENCE",
            {"characters": [{"character_id": "raj"}], "props": [{"prop_id": "box", "asset_id": "missing"}]},
        ),
        (
            "INVALID_PROP",
            {
                "characters": [{"character_id": "raj"}],
                "props": [
                    {"prop_id": "box", "asset_id": "pizza_box"},
                    {"prop_id": "box", "asset_id": "pizza_box"},
                ],
            },
        ),
    ],
)
def test_validator_reports_structured_errors(ctx, tmp_path: Path, code: str, cartoon: dict):
    project_id = _project(ctx, tmp_path)
    register_prop(ctx, project_id, tmp_path)
    with pytest.raises(MarketingError) as excinfo:
        ctx.scenes.validate_cartoon_scene(project_id, {"scene_id": "s1", "duration": 4, "cartoon": cartoon})
    assert excinfo.value.code == code
    assert excinfo.value.to_dict()["suggested_action"]


def test_validate_cartoon_scene_reports_compiled_layers_without_saving(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    result = ctx.scenes.validate_cartoon_scene(project_id, argument_scene())

    assert result["valid"] is True
    assert "char_raj" in result["compiled_layers"]
    assert result["camera"] is not None
    assert ctx.scenes.list_scenes(project_id)["scenes"] == []


def test_compiled_layer_id_prefixes_are_reserved(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    with pytest.raises(MarketingError) as excinfo:
        ctx.scenes.create(
            project_id,
            {
                "scene_id": "s1",
                "duration": 3,
                "layers": [{"id": "char_raj", "type": "text", "content": "x", "start": 0, "duration": 1}],
                "cartoon": {"characters": [{"character_id": "raj"}]},
            },
        )
    assert excinfo.value.code == "INVALID_CARTOON_SCENE"


def test_mixed_scenes_keep_ordinary_layers_and_audio(ctx, tmp_path: Path):
    project_id = _project(ctx, tmp_path)
    scene = argument_scene()
    scene["layers"] = [{"id": "stamp", "type": "text", "content": "4:58 PM", "start": 0, "duration": 2}]
    created = ctx.scenes.create(project_id, scene)

    assert [layer["id"] for layer in created["layers"]] == ["stamp"]
    assert created["cartoon"]["characters"][0]["character_id"] == "raj"
    assert ctx.scenes.validate_project(project_id)["valid"] is True
