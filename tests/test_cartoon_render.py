"""Renders a real cartoon scene through Remotion and FFmpeg."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.renderer.ffmpeg import probe
from tests.cartoonkit import cartoon_project, register_backdrop, register_character, register_prop

pytestmark = pytest.mark.integration


def test_a_cartoon_scene_renders_to_a_real_video(ctx, tmp_path: Path):
    if shutil.which("node") is None:
        pytest.skip("Node is required for Remotion")
    if not (Path("renderer") / "node_modules").exists():
        pytest.skip("Run npm install inside renderer/ before the Remotion integration test")

    project_id = cartoon_project(ctx, tmp_path)
    ctx.projects.update(project_id, {"width": 320, "height": 320})
    register_backdrop(ctx, project_id, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj", parts=("mouth_open", "mouth_closed"))
    register_character(ctx, project_id, tmp_path, "sam", fill="#4A7FC9")
    register_prop(ctx, project_id, tmp_path)
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 1.0,
            "cartoon": {
                "background": {"asset_id": "office"},
                "characters": [
                    {
                        "character_id": "raj",
                        "expression": "angry",
                        "position": {"x": 0.34, "y": 0.8},
                        "actions": [
                            {"action_id": "act_1", "type": "walk_in", "direction": "left", "duration": 0.5},
                            {"action_id": "act_2", "type": "talk", "start": 0.5, "duration": 0.5},
                        ],
                    },
                    {
                        "character_id": "sam",
                        "expression": "happy",
                        "position": {"x": 0.68, "y": 0.8},
                        "actions": [{"action_id": "act_1", "type": "shake_head", "start": 0.5, "duration": 0.5}],
                    },
                ],
                "dialogue": [
                    {
                        "dialogue_id": "d1",
                        "character_id": "raj",
                        "text": "Who broke production?",
                        "start": 0.5,
                        "duration": 0.5,
                    }
                ],
                "camera": {"shot": "two_shot", "animation": {"type": "push_in", "duration": 1.0}},
                "props": [{"prop_id": "box", "asset_id": "pizza_box", "position": {"x": 0.5, "y": 0.9}}],
            },
        },
    )

    job = ctx.renders.render_preview(project_id, wait=True)
    assert job["status"] == "completed", job.get("error")
    output = Path(job["output_path"])
    assert output.stat().st_size > 0
    info = probe(output)
    assert any(stream.get("codec_name") == "h264" for stream in info["streams"])

    # A second render of an unchanged cartoon scene comes straight from the cache.
    again = ctx.renders.render_preview(project_id, wait=True)
    assert again["report"]["cached"] == ["scene_01"]

    # Rewriting the line rerenders only that scene.
    ctx.cartoon.update_dialogue(project_id, "scene_01", "d1", {"text": "Own up, please."})
    third = ctx.renders.render_preview(project_id, wait=True)
    assert third["report"]["rendered"] == ["scene_01"]
    assert third["status"] == "completed", third.get("error")


def test_a_standard_scene_still_renders_after_the_camera_wrapper(ctx, tmp_path: Path):
    if shutil.which("node") is None:
        pytest.skip("Node is required for Remotion")
    if not (Path("renderer") / "node_modules").exists():
        pytest.skip("Run npm install inside renderer/ before the Remotion integration test")

    project = ctx.projects.create("Plain", preset="square", fps=12, width=320, height=320)
    project_id = project["project_id"]
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 0.5,
            "background": {"type": "color", "value": "#101820"},
            "layers": [
                {
                    "id": "line",
                    "type": "text",
                    "content": "Standard mode",
                    "start": 0,
                    "duration": 0.5,
                    "position": {"x": 0.5, "y": 0.5},
                    "animation": {"type": "fade", "duration": 0.3},
                }
            ],
        },
    )
    job = ctx.renders.render_preview(project_id, wait=True)
    assert job["status"] == "completed", job.get("error")
    assert Path(job["output_path"]).stat().st_size > 0
