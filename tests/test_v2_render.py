from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.renderer.ffmpeg import make_color_video, make_tone, probe

pytestmark = pytest.mark.integration


def _ready() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node is required")
    if not (Path("renderer") / "node_modules").exists():
        pytest.skip("Run npm install inside renderer/")
    from app.renderer.ffmpeg import binaries

    binaries()


def test_layer_motion_and_effect_previews(ctx, tmp_path: Path):
    _ready()
    image = tmp_path / "imports" / "still.png"
    Image.new("RGBA", (64, 64), (180, 90, 40, 255)).save(image)
    logo = tmp_path / "imports" / "mark.svg"
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40"><rect width="80" height="40" fill="#fff"/></svg>', encoding="utf-8")
    clip = tmp_path / "imports" / "clip.mp4"
    make_color_video(clip, width=64, height=64, duration=1, color="0x224466", fps=12)
    project = ctx.projects.create("Coverage", preset="square", fps=12, width=160, height=160)
    project_id = project["project_id"]
    ctx.projects.update(project_id, {"width": 160, "height": 160})
    ctx.assets.register(project_id, str(image), asset_id="still")
    ctx.assets.register(project_id, str(logo), asset_id="logo")
    ctx.assets.register(project_id, str(clip), asset_id="clip")
    frames = ctx.assets.keyframe_info(project_id, "clip")
    assert any(frame["name"] == "poster" for frame in frames["frames"])
    assert any(frame["name"] == "contact_sheet" for frame in frames["frames"])
    specs = [
        ("image", {"id": "still", "type": "image", "asset_id": "still", "animation": {"type": "slow_push"}, "effects": {"blur": 2, "brightness": 1.1}}),
        ("video", {"id": "clip", "type": "video", "asset_id": "clip", "playback_rate": 0.5, "animation": {"type": "pan_left"}}),
        ("svg", {"id": "logo", "type": "svg", "asset_id": "logo", "animation": {"type": "scale_in"}, "effects": {"glow": 0.4}}),
        ("text", {"id": "words", "type": "text", "content": "Hi", "animation": {"type": "typewriter"}, "effects": {"contrast": 1.2}}),
        ("shape", {"id": "box", "type": "shape", "shape": "ellipse", "fill": "#FFFFFF", "animation": {"type": "rotate"}, "effects": {"vignette": 0.4, "grain": 0.3}}),
        ("ken", {"id": "still", "type": "image", "asset_id": "still", "animation": {"type": "ken_burns"}, "effects": {"saturation": 1.3}}),
        ("para", {"id": "still", "type": "image", "asset_id": "still", "animation": {"type": "parallax"}}),
    ]
    for scene_id, layer in specs:
        ctx.scenes.create(
            project_id,
            {"scene_id": scene_id, "duration": 0.4, "layers": [{**layer, "start": 0, "duration": 0.4, "width": 0.6, "height": 0.4}]},
        )
    ramp = {
        "scene_id": "ramp",
        "duration": 0.5,
        "layers": [
            {
                "id": "clip",
                "type": "video",
                "asset_id": "clip",
                "start": 0,
                "duration": 0.5,
                "playback_rate": {"keyframes": [{"time": 0, "value": 1}, {"time": 0.25, "value": 0.5}, {"time": 0.5, "value": 1}]},
            }
        ],
    }
    ctx.scenes.create(project_id, ramp)
    job = ctx.renders.render_preview(project_id, wait=True)
    assert job["status"] == "completed", job.get("error")
    info = probe(Path(job["output_path"]))
    assert any(stream.get("codec_type") == "video" for stream in info["streams"])
    assert not any(stream.get("codec_type") == "audio" for stream in info["streams"])


def test_cinematic_reel_iteration(ctx, tmp_path: Path):
    _ready()
    product = tmp_path / "imports" / "product.png"
    Image.new("RGBA", (80, 80), (200, 160, 90, 255)).save(product)
    logo = tmp_path / "imports" / "logo.svg"
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 32"><rect width="64" height="32" fill="#F3C98B"/></svg>', encoding="utf-8")
    clip = tmp_path / "imports" / "hero.mp4"
    make_color_video(clip, width=96, height=160, duration=2, color="0x1a120c", fps=8)
    music = tmp_path / "imports" / "bed.mp3"
    make_tone(music, duration=4)
    project = ctx.projects.create("Cinematic", preset="instagram_reels", fps=8, description="15-second vertical reel")
    project_id = project["project_id"]
    ctx.assets.register(project_id, str(product), asset_id="product")
    ctx.assets.register(project_id, str(logo), asset_id="logo")
    ctx.assets.register(project_id, str(clip), asset_id="clip")
    ctx.assets.register(project_id, str(music), asset_id="music")
    ctx.projects.update(
        project_id,
        {"audio_tracks": [{"id": "bed", "asset_id": "music", "role": "music", "start": 0, "duration": 15, "volume": 0.4}]},
    )
    scenes = [
        {
            "scene_id": "scene_01",
            "duration": 5,
            "transition_out": {"type": "crossfade", "duration": 0.2},
            "layers": [
                {"id": "logo", "type": "svg", "asset_id": "logo", "animation": {"type": "fade"}},
                {"id": "title", "type": "text", "content": "Look closer", "position": {"x": 0.5, "y": 0.7}},
            ],
        },
        {
            "scene_id": "scene_02",
            "duration": 5,
            "transition_out": {"type": "fade", "duration": 0.2},
            "layers": [{"id": "clip", "type": "video", "asset_id": "clip", "playback_rate": 1, "animation": {"type": "slow_push"}}],
        },
        {
            "scene_id": "scene_03",
            "duration": 5,
            "layers": [{"id": "product", "type": "image", "asset_id": "product", "animation": {"type": "ken_burns"}}],
        },
    ]
    for scene in scenes:
        for layer in scene["layers"]:
            layer.setdefault("start", 0)
            layer.setdefault("duration", 5)
            layer.setdefault("width", 0.7)
            layer.setdefault("height", 0.4)
        ctx.scenes.create(project_id, scene)
    first = ctx.renders.render_preview(project_id, wait=True)
    assert first["status"] == "completed", first.get("error")
    scene_02 = ctx.scenes.get(project_id, "scene_02")
    scene_02["layers"][0]["playback_rate"] = 0.5
    ctx.scenes.update(project_id, "scene_02", scene_02)
    second = ctx.renders.render_preview(project_id, wait=True)
    assert second["status"] == "completed", second.get("error")
    report = second.get("report") or {}
    assert "scene_02" in report.get("rendered", [])
    assert "scene_01" in report.get("cached", [])
    assert "scene_03" in report.get("cached", [])
    ctx.projects.update(project_id, {"audio_tracks": []})
    assert ctx.scenes.validate_project(project_id)["valid"] is True
    silent = ctx.renders.render_preview(project_id, wait=True)
    assert silent["status"] == "completed", silent.get("error")
    info = probe(Path(silent["output_path"]))
    assert not any(stream.get("codec_type") == "audio" for stream in info["streams"])
