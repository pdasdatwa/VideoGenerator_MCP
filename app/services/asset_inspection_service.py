"""Technical inspection with Pillow and FFprobe. No model calls."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from app.errors import MarketingError
from app.renderer.ffmpeg import probe

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
}


class AssetInspectionService:
    def inspect(self, path: Path, asset_type: str) -> dict:
        if asset_type == "svg":
            return self._svg(path)
        if asset_type == "image":
            return self._image(path)
        if asset_type == "video":
            return self._video(path)
        if asset_type == "audio":
            return self._audio(path)
        raise MarketingError(
            "UNSUPPORTED_FORMAT",
            f"Unsupported asset type {asset_type}.",
            suggested_action="Use PNG, JPEG, WebP, SVG, MP4, MOV, WebM, MP3, WAV, or AAC.",
        )

    def _image(self, path: Path) -> dict:
        self._check_magic(path, "image")
        with Image.open(path) as image:
            bands = image.getbands()
            has_alpha = "A" in bands or (image.mode == "P" and "transparency" in image.info)
            return {
                "mime_type": _MIME[path.suffix.lower()],
                "width": image.size[0],
                "height": image.size[1],
                "has_alpha": has_alpha,
                "technical_metadata": {
                    "format": image.format,
                    "mode": image.mode,
                    "width": image.size[0],
                    "height": image.size[1],
                    "has_alpha": has_alpha,
                },
            }

    def _svg(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "<svg" not in text.lower():
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                "File extension is .svg but the contents are not SVG.",
                suggested_action="Provide a real SVG document.",
            )
        width, height = _svg_size(text)
        return {
            "mime_type": "image/svg+xml",
            "width": width,
            "height": height,
            "technical_metadata": {"format": "svg", "width": width, "height": height},
        }

    def _video(self, path: Path) -> dict:
        self._check_magic(path, "video")
        info = probe(path)
        video = _stream(info, "video")
        audio = _stream(info, "audio")
        if video is None:
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                "No video stream found.",
                suggested_action="Register a file that contains a video track.",
            )
        duration = _float(info.get("format", {}).get("duration"))
        fps = _fps(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        frames = video.get("nb_frames")
        return {
            "mime_type": _MIME.get(path.suffix.lower(), "video/mp4"),
            "width": int(video.get("width") or 0) or None,
            "height": int(video.get("height") or 0) or None,
            "duration": duration,
            "technical_metadata": {
                "format": info.get("format", {}).get("format_name"),
                "width": video.get("width"),
                "height": video.get("height"),
                "duration": duration,
                "fps": fps,
                "codec": video.get("codec_name"),
                "bitrate": _int(info.get("format", {}).get("bit_rate")),
                "frame_count": int(frames) if frames and str(frames).isdigit() else None,
                "has_audio": audio is not None,
                "audio_codec": None if audio is None else audio.get("codec_name"),
                "audio_channels": None if audio is None else audio.get("channels"),
                "audio_sample_rate": None if audio is None else _int(audio.get("sample_rate")),
            },
        }

    def _audio(self, path: Path) -> dict:
        info = probe(path)
        audio = _stream(info, "audio")
        if audio is None:
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                "No audio stream found.",
                suggested_action="Register an MP3, WAV, or AAC file.",
            )
        duration = _float(info.get("format", {}).get("duration"))
        return {
            "mime_type": _MIME.get(path.suffix.lower(), "audio/mpeg"),
            "duration": duration,
            "technical_metadata": {
                "format": info.get("format", {}).get("format_name"),
                "duration": duration,
                "sample_rate": _int(audio.get("sample_rate")),
                "channels": audio.get("channels"),
                "codec": audio.get("codec_name"),
                "bitrate": _int(info.get("format", {}).get("bit_rate")),
            },
        }

    def _check_magic(self, path: Path, kind: str) -> None:
        header = path.read_bytes()[:16]
        suffix = path.suffix.lower()
        ok = False
        if suffix == ".png":
            ok = header.startswith(b"\x89PNG")
        elif suffix in {".jpg", ".jpeg"}:
            ok = header.startswith(b"\xff\xd8\xff")
        elif suffix == ".webp":
            ok = header[:4] == b"RIFF" and header[8:12] == b"WEBP"
        elif suffix in {".mp4", ".mov"}:
            ok = b"ftyp" in header
        elif suffix == ".webm":
            ok = header.startswith(b"\x1a\x45\xdf\xa3")
        elif kind == "audio":
            ok = True
        if not ok:
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                f"File contents do not match the {suffix} extension.",
                suggested_action="Register the original file, not a renamed copy.",
            )


def _svg_size(text: str) -> tuple[int | None, int | None]:
    width = re.search(r"""\bwidth=["']([\d.]+)""", text, re.IGNORECASE)
    height = re.search(r"""\bheight=["']([\d.]+)""", text, re.IGNORECASE)
    if width and height:
        return int(float(width.group(1))), int(float(height.group(1)))
    viewbox = re.search(
        r"""viewBox=["']\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)""",
        text,
        re.IGNORECASE,
    )
    if viewbox:
        return int(float(viewbox.group(1))), int(float(viewbox.group(2)))
    return None, None


def _stream(info: dict, codec_type: str) -> dict | None:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == codec_type:
            return stream
    return None


def _fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        if float(den) == 0:
            return None
        return round(float(num) / float(den), 4)
    return float(value)


def _float(value: object) -> float | None:
    if value in (None, "N/A"):
        return None
    return round(float(value), 4)


def _int(value: object) -> int | None:
    if value in (None, "N/A"):
        return None
    return int(value)
