from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.renderer.ffmpeg import make_color_video, probe


class ColorRenderer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def render_scene(self, props: dict, output: Path) -> None:
        self.calls.append(props["sceneId"])
        make_color_video(
            output,
            width=props["width"],
            height=props["height"],
            duration=props["duration"],
            fps=props["fps"],
            color="0x224466",
        )


def _still(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (16, 16), color).save(path)


def _three_scenes(ctx, tmp_path: Path):
    project = ctx.projects.create("Incremental", preset="square", fps=12)
    project_id = project["project_id"]
    logo = tmp_path / "imports" / "logo.png"
    product = tmp_path / "imports" / "product.png"
    _still(logo, (10, 10, 10))
    _still(product, (200, 180, 160))
    ctx.assets.register(project_id, str(logo), asset_id="logo")
    ctx.assets.register(project_id, str(product), asset_id="product")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 0.5,
            "transition_out": {"type": "cut", "duration": 0},
            "layers": [
                {"id": "logo", "type": "image", "asset_id": "logo", "start": 0, "duration": 0.5},
                {"id": "title", "type": "text", "content": "One", "start": 0, "duration": 0.5},
            ],
        },
    )
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_02",
            "duration": 0.5,
            "transition_out": {"type": "cut", "duration": 0},
            "layers": [
                {"id": "product", "type": "image", "asset_id": "product", "start": 0, "duration": 0.5},
                {"id": "title", "type": "text", "content": "Two", "start": 0, "duration": 0.5},
            ],
        },
    )
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_03",
            "duration": 0.5,
            "layers": [
                {"id": "logo", "type": "image", "asset_id": "logo", "start": 0, "duration": 0.5},
                {"id": "title", "type": "text", "content": "Three", "start": 0, "duration": 0.5},
            ],
        },
    )
    return project_id


def test_incremental_render_and_logo_replace(ctx, tmp_path: Path):
    renderer = ColorRenderer()
    ctx.renders.renderer = renderer
    project_id = _three_scenes(ctx, tmp_path)
    first = ctx.renders.render_project(project_id, wait=True)
    assert first["status"] == "completed"
    assert first["report"]["rendered"] == ["scene_01", "scene_02", "scene_03"]
    assert first["report"]["cached"] == []
    output = Path(first["output_path"])
    info = probe(output)
    assert info["streams"][0]["codec_name"] == "h264"

    scene = ctx.scenes.get(project_id, "scene_02")
    scene["layers"][1]["content"] = "Two, louder"
    ctx.scenes.update(project_id, "scene_02", scene)
    second = ctx.renders.render_project(project_id, wait=True)
    assert second["report"]["rendered"] == ["scene_02"]
    assert second["report"]["cached"] == ["scene_01", "scene_03"]
    assert second["report"]["cache_hit_rate"] == 0.6667

    replacement = tmp_path / "imports" / "logo-2.png"
    _still(replacement, (255, 0, 0))
    ctx.assets.register(project_id, str(replacement), asset_id="logo", replace=True)
    third = ctx.renders.render_project(project_id, wait=True)
    assert set(third["report"]["rendered"]) == {"scene_01", "scene_03"}
    assert third["report"]["cached"] == ["scene_02"]

    version = ctx.versions.create(project_id, label="after-logo")
    ctx.scenes.update(
        project_id,
        "scene_02",
        {**ctx.scenes.get(project_id, "scene_02"), "layers": ctx.scenes.get(project_id, "scene_02")["layers"]},
    )
    restored = ctx.versions.restore(project_id, version["version_id"])
    assert version["version_id"] in restored["kept_versions"]
    assert restored["new_version"]["version_id"] in restored["kept_versions"]
    final = ctx.renders.render_project(project_id, wait=True)
    assert Path(final["output_path"]).stat().st_size > 0
