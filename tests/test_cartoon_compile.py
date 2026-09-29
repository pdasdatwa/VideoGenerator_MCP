from __future__ import annotations

from pathlib import Path

from app.renderer.cartoon.compile import compile_cartoon_scene
from app.renderer.cartoon.names import ACTION_SPECS, CAMERA_MOVES
from app.renderer.cartoon.primitives import compose, resolve_action
from app.models.cartoon import CartoonAction
from tests.cartoonkit import (
    argument_scene,
    cartoon_project,
    register_backdrop,
    register_character,
    register_prop,
)


def _compile(ctx, project_id: str, scene_id: str):
    return compile_cartoon_scene(
        ctx.scenes.get_model(project_id, scene_id),
        ctx.projects.get(project_id),
        ctx.assets.map_assets(project_id),
        ctx.characters.map_characters(project_id),
    )


def _scene(ctx, tmp_path: Path, scene: dict) -> tuple[str, str]:
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    register_character(ctx, project_id, tmp_path, "sam", fill="#4A7FC9")
    ctx.scenes.create(project_id, scene)
    return project_id, scene["scene_id"]


def test_cartoon_scene_compiles_to_ordinary_layers(ctx, tmp_path: Path):
    project_id, scene_id = _scene(ctx, tmp_path, argument_scene())
    compiled = _compile(ctx, project_id, scene_id)

    ids = [layer.id for layer in compiled.scene.layers]
    assert "cbg_main" in ids
    assert "char_raj" in ids and "char_sam" in ids
    assert "dlg_d1_bubble" in ids and "dlg_d1_text" in ids
    assert compiled.scene.cartoon is None
    assert {layer.type for layer in compiled.scene.layers} <= {"image", "video", "svg", "text", "shape"}

    background = next(layer for layer in compiled.scene.layers if layer.id == "cbg_main")
    character = next(layer for layer in compiled.scene.layers if layer.id == "char_raj")
    dialogue = next(layer for layer in compiled.scene.layers if layer.id == "dlg_d1_text")
    assert background.z_index < character.z_index < dialogue.z_index
    assert dialogue.content == "WHO BROKE PRODUCTION?"
    assert dialogue.respect_safe_area is False


def test_actions_become_keyframes_and_walk_in_starts_off_frame(ctx, tmp_path: Path):
    project_id, scene_id = _scene(ctx, tmp_path, argument_scene())
    compiled = _compile(ctx, project_id, scene_id)

    raj = next(layer for layer in compiled.scene.layers if layer.id == "char_raj")
    frames = raj.position["keyframes"]
    assert len(frames) > 5
    assert frames[0]["value"]["x"] < 0
    assert abs(frames[-1]["value"]["x"] - 0.35) < 1e-6
    assert [frame["time"] for frame in frames] == sorted(frame["time"] for frame in frames)

    sam = next(layer for layer in compiled.scene.layers if layer.id == "char_sam")
    assert sam.position == {"x": 0.68, "y": 0.78}


def test_dialogue_stays_inside_what_a_zoomed_camera_shows(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "close",
            "duration": 3,
            "cartoon": {
                "characters": [{"character_id": "raj", "position": {"x": 0.12, "y": 0.8}}],
                "dialogue": [
                    {"dialogue_id": "d1", "character_id": "raj", "text": "Off to one side entirely.", "duration": 2}
                ],
                "camera": {"shot": "close_up", "animation": {"type": "push_in", "duration": 2}},
            },
        },
    )
    compiled = _compile(ctx, project_id, "close")
    bubble = next(layer for layer in compiled.scene.layers if layer.id == "dlg_d1_bubble")
    zoom = max(frame["value"] for frame in compiled.camera["zoom"]["keyframes"])
    half = 0.5 / zoom
    position = compiled.camera["position"]
    camera_x = position["value"]["x"] if position["mode"] == "static" else position["keyframes"][0]["value"]["x"]

    assert bubble.position["x"] - bubble.width / 2 >= camera_x - half - 1e-6
    assert bubble.position["x"] + bubble.width / 2 <= camera_x + half + 1e-6


def test_compiled_artwork_layers_are_sized_to_their_box(ctx, tmp_path: Path):
    """An SVG only fills its layer box when the layer asks for a fit, so every compiled one does."""
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    register_prop(ctx, project_id, tmp_path)
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "art",
            "duration": 2,
            "cartoon": {
                "background": {"asset_id": "office"},
                "characters": [{"character_id": "raj"}],
                "props": [{"prop_id": "box", "asset_id": "pizza_box"}],
            },
        },
    )
    compiled = _compile(ctx, project_id, "art")
    drawn = [layer for layer in compiled.scene.layers if layer.type in {"image", "svg"}]

    assert drawn
    for layer in drawn:
        assert layer.fit is not None, layer.id
        assert layer.width and layer.height


def test_compilation_is_deterministic(ctx, tmp_path: Path):
    project_id, scene_id = _scene(ctx, tmp_path, argument_scene())
    first = _compile(ctx, project_id, scene_id)
    second = _compile(ctx, project_id, scene_id)
    assert first.scene.model_dump(mode="json") == second.scene.model_dump(mode="json")
    assert first.camera == second.camera


def test_every_action_and_camera_move_produces_finite_numbers(ctx, tmp_path: Path):
    for name in ACTION_SPECS:
        action = CartoonAction(type=name, to="angry" if name == "expression_change" else None)
        resolved = resolve_action(action, scene_duration=4.0)
        for step in range(0, 41):
            deltas = compose([resolved], step / 10)
            for value in (deltas.dx, deltas.dy, deltas.rotation, deltas.scale, deltas.opacity):
                assert value == value and abs(value) < 100, name
            assert deltas.scale > 0, name

    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    for index, move in enumerate(CAMERA_MOVES):
        scene = {
            "scene_id": f"cam_{index}",
            "duration": 3,
            "cartoon": {
                "characters": [{"character_id": "raj"}],
                "camera": {"shot": "close_up", "animation": {"type": move, "duration": 2}},
            },
        }
        ctx.scenes.create(project_id, scene)
        compiled = _compile(ctx, project_id, f"cam_{index}")
        assert compiled.camera is not None
        assert compiled.camera["zoom"]["mode"] in {"static", "keyframes"}


def test_props_and_parallax_backgrounds_compile(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_backdrop(ctx, project_id, tmp_path, asset_id="sky")
    register_character(ctx, project_id, tmp_path, "raj")
    register_prop(ctx, project_id, tmp_path)
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "props",
            "duration": 3,
            "cartoon": {
                "background": {"background": "sky", "midground": "office", "parallax": 0.6},
                "characters": [{"character_id": "raj"}],
                "props": [
                    {
                        "prop_id": "pizza_box",
                        "asset_id": "pizza_box",
                        "position": {"x": 0.7, "y": 0.75},
                        "animation": {"type": "bounce", "repeat": 2},
                    }
                ],
                "camera": {"animation": {"type": "pan_right", "duration": 2}},
            },
        },
    )
    compiled = _compile(ctx, project_id, "props")
    ids = [layer.id for layer in compiled.scene.layers]
    assert "cbg_bg" in ids and "cbg_mid" in ids and "prop_pizza_box" in ids

    prop = next(layer for layer in compiled.scene.layers if layer.id == "prop_pizza_box")
    assert "keyframes" in prop.position
    plate = next(layer for layer in compiled.scene.layers if layer.id == "cbg_bg")
    assert "keyframes" in plate.position


def test_mixed_cartoon_and_standard_layers_render_together(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "mixed",
            "duration": 3,
            "layers": [
                {"id": "caption", "type": "text", "content": "Friday, 4pm", "start": 0, "duration": 3},
                {"id": "badge", "type": "shape", "shape": "ellipse", "fill": "#FFFFFF", "start": 0, "duration": 3},
            ],
            "cartoon": {
                "background": {"asset_id": "office"},
                "characters": [{"character_id": "raj", "expression": "angry"}],
            },
        },
    )
    compiled = _compile(ctx, project_id, "mixed")
    ids = [layer.id for layer in compiled.scene.layers]
    assert {"caption", "badge", "char_raj", "cbg_main"} <= set(ids)


def test_talk_without_mouth_parts_warns_but_still_compiles(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "talk",
            "duration": 3,
            "cartoon": {
                "characters": [{"character_id": "raj", "actions": [{"type": "talk", "duration": 2}]}],
            },
        },
    )
    compiled = _compile(ctx, project_id, "talk")
    assert any("mouth_open" in warning for warning in compiled.warnings)
    assert "char_raj" in [layer.id for layer in compiled.scene.layers]


def test_mouth_parts_produce_overlay_layers(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj", parts=("mouth_open", "mouth_closed"))
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "talk",
            "duration": 3,
            "cartoon": {
                "characters": [{"character_id": "raj", "actions": [{"type": "talk", "duration": 2}]}],
            },
        },
    )
    compiled = _compile(ctx, project_id, "talk")
    ids = [layer.id for layer in compiled.scene.layers]
    assert "char_raj_mouth_open" in ids and "char_raj_mouth_closed" in ids
    assert compiled.warnings == []


def test_standard_scene_passes_through_the_compiler_untouched(ctx, tmp_path: Path):
    project = ctx.projects.create("Plain", preset="square", fps=12)
    project_id = project["project_id"]
    scene = ctx.scenes.create(
        project_id,
        {
            "scene_id": "plain",
            "duration": 2,
            "layers": [{"id": "line", "type": "text", "content": "Hello", "start": 0, "duration": 2}],
        },
    )
    model = ctx.scenes.get_model(project_id, "plain")
    compiled = compile_cartoon_scene(model, ctx.projects.get(project_id), ctx.assets.map_assets(project_id), {})
    assert compiled.camera is None
    assert compiled.scene is model
    assert scene["layers"][0]["id"] == "line"
