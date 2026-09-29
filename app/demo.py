"""Four local demos that share one renderer. No external AI APIs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from app.renderer.ffmpeg import make_color_video, make_tone
from app.services import AppContext

DEMOS = ("demo_product", "demo_travel", "demo_photo_montage", "demo_cinematic")


def build_demo(ctx: AppContext, *, name: str = "demo_product", wait: bool = True, profile: str = "preview") -> dict:
    if name not in DEMOS:
        raise ValueError(f"Unknown demo '{name}'. Use one of: {', '.join(DEMOS)}.")
    root = Path("demos") / "assets" / name
    files = _assets(root, name)
    spec = _SPECS[name]
    project = ctx.projects.create(spec["title"], description=spec["description"], preset=spec["preset"], fps=12)
    project_id = project["project_id"]
    ids = {}
    for key, path in files.items():
        ids[key] = ctx.assets.register(project_id, str(path), asset_id=key)["id"]
    if "music" in ids:
        ctx.projects.update(
            project_id,
            {
                "audio_tracks": [
                    {
                        "id": "bed",
                        "asset_id": ids["music"],
                        "role": "music",
                        "start": 0,
                        "duration": spec["duration"],
                        "volume": 0.35,
                        "fade_in": 0.2,
                        "fade_out": 0.4,
                    }
                ]
            },
        )
    for scene in spec["scenes"](ids):
        ctx.scenes.create(project_id, scene)
    ctx.versions.create(project_id, label=name, note=spec["description"])
    if profile == "final":
        job = ctx.renders.render_project(project_id, wait=wait)
    else:
        job = ctx.renders.render_preview(project_id, wait=wait)
    output = Path("demos") / "output"
    output.mkdir(parents=True, exist_ok=True)
    if job.get("output_path"):
        target = output / f"{name}.mp4"
        shutil.copyfile(job["output_path"], target)
        job = {**job, "demo_output": str(target.resolve())}
    summary = {"demo": name, "project_id": project_id, "job": job}
    (output / f"{name}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _assets(folder: Path, name: str) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    still = folder / "still.png"
    _photo(still, (40, 70, 90) if name != "demo_product" else (90, 50, 30))
    second = folder / "second.png"
    _photo(second, (120, 80, 40))
    logo = folder / "logo.svg"
    logo.write_text(_logo_svg(), encoding="utf-8")
    clip = folder / "clip.mp4"
    make_color_video(clip, width=320, height=568, duration=2, color="0x1c2430", fps=12)
    music = folder / "music.mp3"
    make_tone(music, duration=8)
    return {"still": still, "second": second, "logo": logo, "clip": clip, "music": music}


def _layer(layer_id: str, **fields: object) -> dict:
    payload = {"id": layer_id, "start": 0, "duration": 2, "width": 0.7, "height": 0.45, "position": {"x": 0.5, "y": 0.5}}
    payload.update(fields)
    return payload


def _product(ids: dict[str, str]) -> list[dict]:
    return [
        {
            "scene_id": "open",
            "duration": 2,
            "transition_out": {"type": "crossfade", "duration": 0.3},
            "layers": [
                _layer("logo", type="svg", asset_id=ids["logo"], animation={"type": "fade"}),
                _layer("title", type="text", content="A quieter object", position={"x": 0.5, "y": 0.72}, animation={"type": "fade_up"}),
            ],
        },
        {
            "scene_id": "hero",
            "duration": 2,
            "layers": [_layer("still", type="image", asset_id=ids["still"], animation={"type": "slow_push"}, effects={"glow": 0.2})],
        },
    ]


def _travel(ids: dict[str, str]) -> list[dict]:
    return [
        {
            "scene_id": "coast",
            "duration": 2,
            "transition_out": {"type": "fade", "duration": 0.3},
            "layers": [_layer("still", type="image", asset_id=ids["still"], animation={"type": "ken_burns"}, effects={"color_tint": {"color": "#E8B86D", "amount": 0.25}})],
        },
        {
            "scene_id": "road",
            "duration": 2,
            "layers": [_layer("second", type="image", asset_id=ids["second"], animation={"type": "pan_right"})],
        },
    ]


def _montage(ids: dict[str, str]) -> list[dict]:
    return [
        {
            "scene_id": "one",
            "duration": 2,
            "transition_out": {"type": "slide", "duration": 0.25, "direction": "left"},
            "layers": [_layer("still", type="image", asset_id=ids["still"], animation={"type": "scale_in"})],
        },
        {
            "scene_id": "two",
            "duration": 2,
            "layers": [_layer("second", type="image", asset_id=ids["second"], animation={"type": "fade"})],
        },
    ]


def _cinematic(ids: dict[str, str]) -> list[dict]:
    return [
        {
            "scene_id": "hold",
            "duration": 2,
            "transition_out": {"type": "dip_to_color", "duration": 0.3, "color": "#000000"},
            "layers": [_layer("clip", type="video", asset_id=ids["clip"], playback_rate=0.5, animation={"type": "slow_pull"})],
        },
        {
            "scene_id": "title",
            "duration": 2,
            "layers": [_layer("line", type="text", content="After dark", animation={"type": "typewriter"}, effects={"vignette": 0.45, "grain": 0.25})],
        },
    ]


_SPECS = {
    "demo_product": {"title": "Product reel", "description": "A short product reel.", "preset": "instagram_reels", "duration": 4, "scenes": _product},
    "demo_travel": {"title": "Travel reel", "description": "A short travel reel.", "preset": "instagram_reels", "duration": 4, "scenes": _travel},
    "demo_photo_montage": {"title": "Photo montage", "description": "A photo montage.", "preset": "square", "duration": 4, "scenes": _montage},
    "demo_cinematic": {"title": "Cinematic reel", "description": "A slow cinematic reel.", "preset": "landscape", "duration": 4, "scenes": _cinematic},
}


def _photo(path: Path, color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (640, 800), color)
    draw = ImageDraw.Draw(image)
    draw.ellipse((180, 220, 460, 520), fill=(245, 236, 220))
    image.save(path)


def _logo_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80">
      <rect x="1" y="1" width="198" height="78" rx="8" fill="none" stroke="#F3C98B" stroke-width="3"/>
    </svg>
    """
