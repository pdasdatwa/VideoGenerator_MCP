from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.renderer.ffmpeg import make_color_video, make_tone
from app.services.asset_inspection_service import AssetInspectionService


def test_png_and_jpeg_metadata(tmp_path: Path):
    inspector = AssetInspectionService()
    png = tmp_path / "dot.png"
    Image.new("RGBA", (12, 8), (255, 0, 0, 128)).save(png)
    jpeg = tmp_path / "dot.jpg"
    Image.new("RGB", (10, 6), (1, 2, 3)).save(jpeg, format="JPEG")
    png_info = inspector.inspect(png, "image")
    jpeg_info = inspector.inspect(jpeg, "image")
    assert png_info["width"] == 12 and png_info["has_alpha"] is True
    assert jpeg_info["width"] == 10 and jpeg_info["has_alpha"] is False


def test_svg_metadata(tmp_path: Path):
    path = tmp_path / "mark.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
    info = AssetInspectionService().inspect(path, "svg")
    assert info["mime_type"] == "image/svg+xml"


def test_mp4_and_audio_metadata(tmp_path: Path):
    video = tmp_path / "clip.mp4"
    audio = tmp_path / "tone.mp3"
    make_color_video(video, width=64, height=64, duration=0.4, fps=10)
    make_tone(audio, duration=0.4)
    video_info = AssetInspectionService().inspect(video, "video")
    audio_info = AssetInspectionService().inspect(audio, "audio")
    assert video_info["width"] == 64
    assert video_info["technical_metadata"]["codec"]
    assert audio_info["duration"] > 0
    assert audio_info["technical_metadata"]["codec"]
