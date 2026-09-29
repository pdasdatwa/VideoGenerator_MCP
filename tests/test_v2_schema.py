from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import ReelError
from app.renderer.assembly import _duck_expr, _transition_name, _volume_argument
from app.renderer.validator import parse_scene
from app.models.scene import AudioTrack, Transition
from app.services.asset_inspection_service import AssetInspectionService


def test_new_motion_and_effects_validate():
    scene = parse_scene(
        {
            "scene_id": "scene_01",
            "duration": 2,
            "layers": [
                {
                    "id": "hero",
                    "type": "text",
                    "content": "Hello",
                    "animation": {"type": "typewriter"},
                    "effects": {
                        "blur": {"keyframes": [{"time": 0, "value": 0}, {"time": 1, "value": 4}]},
                        "glow": 0.4,
                        "grain": 0.2,
                        "color_tint": {"color": "#FFCC88", "amount": 0.3},
                    },
                    "mask": {"shape": "circle", "x": 0.5, "y": 0.5, "width": 0.8, "height": 0.8},
                    "blend_mode": "screen",
                }
            ],
            "transition_out": {"type": "whip", "duration": 0.3, "direction": "left"},
        }
    )
    assert scene.layers[0].animation.type == "typewriter"
    assert scene.transition_out.type == "whip"


def test_transition_longer_than_scene_is_rejected():
    with pytest.raises(ReelError) as caught:
        parse_scene(
            {
                "scene_id": "scene_01",
                "duration": 1,
                "transition_out": {"type": "blur", "duration": 1},
                "layers": [],
            }
        )
    assert caught.value.code == "INVALID_DURATION"


def test_playback_and_volume_keyframes():
    scene = parse_scene(
        {
            "scene_id": "scene_01",
            "duration": 4,
            "layers": [
                {
                    "id": "clip",
                    "type": "text",
                    "content": "Rate",
                    "playback_rate": {"keyframes": [{"time": 0, "value": 1}, {"time": 2, "value": 0.5}, {"time": 4, "value": 1}]},
                }
            ],
            "audio": [
                {
                    "id": "bed",
                    "asset_id": "music",
                    "volume": {"keyframes": [{"time": 0, "value": 1}, {"time": 1, "value": 0.4}]},
                    "duck": {"when_role": "voiceover", "to_volume": 0.25, "attack": 0.1, "release": 0.2},
                }
            ],
        }
    )
    assert scene.audio[0].duck.to_volume == 0.25


def test_duck_expression_mentions_voiceover_window():
    music = AudioTrack(id="bed", asset_id="music", role="music", start=0, duration=4, volume=1, duck={"when_role": "voiceover", "to_volume": 0.25})
    voice = AudioTrack(id="vo", asset_id="voice", role="voiceover", start=1, duration=1, volume=1)
    expr = _duck_expr(music, [(music, Path("music.mp3")), (voice, Path("voice.wav"))])
    assert "0.2500" in expr
    argument = _volume_argument(music, [(music, Path("music.mp3")), (voice, Path("voice.wav"))], 4)
    assert argument.startswith("'")


def test_transition_names():
    assert _transition_name(Transition(type="zoom", direction="up")) == "zoomin"
    assert _transition_name(Transition(type="blur")) == "hblur"
    assert _transition_name(Transition(type="whip", direction="right")) == "wiperight"
    assert _transition_name(Transition(type="dip_to_color", color="#FFFFFF")) == "fadewhite"
    assert _transition_name(Transition(type="dip_to_color", color="#112233")) == "fadeblack"


def test_effect_and_playback_change_cache_key(ctx, tmp_path: Path):
    image = tmp_path / "imports" / "still.png"
    from PIL import Image

    Image.new("RGB", (8, 8), (10, 20, 30)).save(image)
    project = ctx.projects.create("Cache", preset="square", fps=12)
    project_id = project["project_id"]
    ctx.assets.register(project_id, str(image), asset_id="still")
    base = {
        "scene_id": "scene_01",
        "duration": 1,
        "layers": [{"id": "still", "type": "image", "asset_id": "still", "animation": {"type": "slow_push"}}],
    }
    ctx.scenes.create(project_id, base)
    stored = ctx.projects.get(project_id)
    scene = ctx.scenes.get_model(project_id, "scene_01")
    assets = ctx.assets.map_assets(project_id)
    first = ctx.cache.key(stored, scene, assets, profile="preview", width=100, height=100, crf=28)
    base["layers"][0]["effects"] = {"blur": 4}
    ctx.scenes.update(project_id, "scene_01", base)
    second = ctx.cache.key(stored, ctx.scenes.get_model(project_id, "scene_01"), assets, profile="preview", width=100, height=100, crf=28)
    assert first != second


def test_svg_viewbox_size(tmp_path: Path):
    path = tmp_path / "mark.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80"></svg>', encoding="utf-8")
    info = AssetInspectionService().inspect(path, "svg")
    assert info["width"] == 200
    assert info["height"] == 80
