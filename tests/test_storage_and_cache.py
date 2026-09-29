from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.renderer.cachekey import visual_cache_key
from app.renderer.validator import parse_scene


def _image(path: Path) -> None:
    Image.new("RGBA", (8, 8), (255, 255, 255, 255)).save(path)


def test_project_asset_scene_and_version_roundtrip(ctx, tmp_path: Path):
    project = ctx.projects.create("Spot", preset="square", fps=24)
    project_id = project["project_id"]
    image = tmp_path / "imports" / "logo.png"
    _image(image)
    asset = ctx.assets.register(project_id, str(image), asset_id="logo")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 2,
            "layers": [
                {
                    "id": "logo",
                    "type": "image",
                    "asset_id": "logo",
                    "start": 0,
                    "duration": 2,
                    "position": {"x": 0.5, "y": 0.5},
                }
            ],
        },
    )
    version = ctx.versions.create(project_id, label="v1")
    loaded = ctx.versions.get(project_id, version["version_id"])
    assert loaded["scenes"]["scene_01"]["layers"][0]["asset_id"] == "logo"
    assert asset["sha256"]
    assert ctx.projects.get(project_id).duration == 2


def test_cache_key_changes_when_scene_or_asset_changes(ctx, tmp_path: Path):
    project = ctx.projects.create("Keys", preset="square")
    project_id = project["project_id"]
    image = tmp_path / "imports" / "a.png"
    _image(image)
    ctx.assets.register(project_id, str(image), asset_id="logo")
    scene = parse_scene(
        {
            "scene_id": "scene_01",
            "duration": 1,
            "layers": [{"id": "logo", "type": "image", "asset_id": "logo", "start": 0, "duration": 1}],
        }
    )
    model = ctx.projects.get(project_id)
    assets = ctx.assets.map_assets(project_id)
    first = visual_cache_key(model, scene, assets, profile="preview", width=100, height=100, crf=28)
    again = visual_cache_key(model, scene, assets, profile="preview", width=100, height=100, crf=28)
    assert first == again
    edited = scene.model_copy(deep=True)
    edited.layers[0].opacity = 0.5
    changed = visual_cache_key(model, edited, assets, profile="preview", width=100, height=100, crf=28)
    assert changed != first
    other = tmp_path / "imports" / "b.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 255)).save(other)
    ctx.assets.register(project_id, str(other), asset_id="logo", replace=True)
    assets = ctx.assets.map_assets(project_id)
    replaced = visual_cache_key(model, scene, assets, profile="preview", width=100, height=100, crf=28)
    assert replaced != first
