from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.dependency_service import DependencyService


def test_asset_edges_and_unrelated_scene(ctx, tmp_path: Path):
    project = ctx.projects.create("Deps", preset="square")
    project_id = project["project_id"]
    logo = tmp_path / "imports" / "logo.png"
    product = tmp_path / "imports" / "product.png"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(logo)
    Image.new("RGB", (4, 4), (4, 5, 6)).save(product)
    ctx.assets.register(project_id, str(logo), asset_id="logo")
    ctx.assets.register(project_id, str(product), asset_id="product")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 1,
            "layers": [{"id": "mark", "type": "image", "asset_id": "logo", "start": 0, "duration": 1}],
        },
    )
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_02",
            "duration": 1,
            "layers": [{"id": "hero", "type": "image", "asset_id": "product", "start": 0, "duration": 1}],
        },
    )
    scenes = ctx.scenes.map_scenes(project_id)
    deps = DependencyService()
    assert deps.visual_scenes_for_asset(scenes, "logo") == ["scene_01"]
    assert "scene_02" not in deps.visual_scenes_for_asset(scenes, "logo")
    graph = deps.graph(scenes)
    assert graph["logo"][0]["layer_id"] == "mark"
