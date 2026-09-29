"""Runtime configuration. Environment variables use the REEL_ prefix.

MARKETING_ is still read when the matching REEL_ variable is unset.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PRESETS: dict[str, tuple[int, int, str]] = {
    "instagram_reels": (1080, 1920, "9:16"),
    "youtube_shorts": (1080, 1920, "9:16"),
    "youtube": (1920, 1080, "16:9"),
    "landscape": (1920, 1080, "16:9"),
    "square": (1080, 1080, "1:1"),
    "portrait": (1080, 1350, "4:5"),
}

ASPECT_RATIOS = ("9:16", "16:9", "1:1", "4:5")

# Fractions of the frame. Text defaults to this inset.
SAFE_AREAS: dict[str, dict[str, float]] = {
    "instagram_reels": {"top": 0.12, "bottom": 0.16, "left": 0.06, "right": 0.06},
    "youtube_shorts": {"top": 0.12, "bottom": 0.16, "left": 0.06, "right": 0.06},
    "youtube": {"top": 0.06, "bottom": 0.08, "left": 0.05, "right": 0.05},
    "landscape": {"top": 0.06, "bottom": 0.08, "left": 0.05, "right": 0.05},
    "square": {"top": 0.06, "bottom": 0.08, "left": 0.06, "right": 0.06},
    "portrait": {"top": 0.08, "bottom": 0.10, "left": 0.06, "right": 0.06},
    "custom": {"top": 0.06, "bottom": 0.08, "left": 0.05, "right": 0.05},
}

ALLOWED_EXTENSIONS = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".svg": "svg",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".aac": "audio",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REEL_", extra="ignore")

    data_dir: Path = Path("data")
    asset_source_dirs: list[Path] = Field(default_factory=lambda: [Path("imports"), Path("demos/assets")])
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    node_path: str = "node"
    renderer_dir: Path = Path("renderer")
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    preview_long_edge: int = 540
    preview_crf: int = 28
    final_crf: int = 18


def get_settings() -> Settings:
    fallback: dict[str, str] = {}
    for key, value in os.environ.items():
        if not key.startswith("MARKETING_"):
            continue
        reel_key = "REEL_" + key[len("MARKETING_") :]
        if reel_key in os.environ:
            continue
        fallback[key[len("MARKETING_") :].lower()] = value
    return Settings(**fallback) if fallback else Settings()
