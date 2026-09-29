from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.renderer.ffmpeg import probe


pytestmark = pytest.mark.integration


def test_real_remotion_scene(ctx, tmp_path: Path):
    if shutil.which("node") is None:
        pytest.skip("Node is required for Remotion")
    if not (Path("renderer") / "node_modules").exists():
        pytest.skip("Run npm install inside renderer/ before the Remotion integration test")
    image = tmp_path / "imports" / "mark.png"
    Image.new("RGBA", (64, 64), (240, 220, 180, 255)).save(image)
    project = ctx.projects.create("Remotion", preset="square", fps=12, width=320, height=320)
    project_id = project["project_id"]
    ctx.projects.update(project_id, {"width": 320, "height": 320})
    ctx.assets.register(project_id, str(image), asset_id="mark")
    ctx.scenes.create(
        project_id,
        {
            "scene_id": "scene_01",
            "duration": 0.5,
            "layers": [
                {
                    "id": "mark",
                    "type": "image",
                    "asset_id": "mark",
                    "start": 0,
                    "duration": 0.5,
                    "position": {"x": 0.5, "y": 0.5},
                    "width": 0.4,
                    "height": 0.4,
                    "animation": {"type": "fade", "duration": 0.3},
                },
                {
                    "id": "line",
                    "type": "text",
                    "content": "Northline",
                    "start": 0,
                    "duration": 0.5,
                    "position": {"x": 0.5, "y": 0.8},
                    "style": {"font_size": 28, "color": "#FFFFFF", "align": "center"},
                },
            ],
        },
    )
    job = ctx.renders.render_preview(project_id, wait=True)
    assert job["status"] == "completed", job.get("error")
    info = probe(Path(job["output_path"]))
    assert any(stream.get("codec_name") == "h264" for stream in info["streams"])
