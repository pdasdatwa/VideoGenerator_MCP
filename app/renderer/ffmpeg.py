"""Locate FFmpeg and run file-based media commands. Never loads a whole video into RAM."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.errors import MarketingError

_BINARIES: dict[str, str] | None = None


def binaries(ffmpeg_path: str | None = None, ffprobe_path: str | None = None) -> dict[str, str]:
    global _BINARIES
    if ffmpeg_path or ffprobe_path:
        return {
            "ffmpeg": ffmpeg_path or _which("ffmpeg"),
            "ffprobe": ffprobe_path or _which("ffprobe"),
        }
    if _BINARIES is None:
        _BINARIES = {"ffmpeg": _which("ffmpeg"), "ffprobe": _which("ffprobe")}
    return _BINARIES


def _which(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
    except Exception as exc:  # pragma: no cover - dependency missing
        raise MarketingError(
            "FFMPEG_NOT_AVAILABLE",
            f"Could not find {name}.",
            suggested_action="Install FFmpeg or add the static-ffmpeg package.",
        ) from exc
    found = shutil.which(name)
    if not found:
        raise MarketingError(
            "FFMPEG_NOT_AVAILABLE",
            f"Could not find {name} after adding static-ffmpeg paths.",
            suggested_action="Install FFmpeg and ensure it is on PATH.",
        )
    return found


def run_command(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise MarketingError(
            "FFMPEG_FAILURE",
            "FFmpeg timed out.",
            suggested_action="Retry with a shorter scene or the preview profile.",
        ) from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-1200:]
        raise MarketingError(
            "FFMPEG_FAILURE",
            "FFmpeg failed.",
            suggested_action="Check the media file and the scene timing. The FFmpeg log is included.",
            ffmpeg_stderr=tail,
        )
    return completed


def probe(path: Path, ffprobe_path: str | None = None) -> dict:
    ffprobe = binaries(ffprobe_path=ffprobe_path)["ffprobe"]
    completed = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MarketingError(
            "FFMPEG_FAILURE",
            "FFprobe returned data that was not JSON.",
            suggested_action="Confirm the file is a media file FFmpeg can read.",
        ) from exc


def extract_frame(source: Path, time_seconds: float, output: Path, ffmpeg_path: str | None = None) -> None:
    ffmpeg = binaries(ffmpeg_path=ffmpeg_path)["ffmpeg"]
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{max(0.0, time_seconds):.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output),
        ]
    )


def contact_sheet(frames: list[Path], output: Path, ffmpeg_path: str | None = None) -> None:
    ffmpeg = binaries(ffmpeg_path=ffmpeg_path)["ffmpeg"]
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y"]
    for frame in frames:
        command.extend(["-i", str(frame)])
    count = len(frames)
    if count == 1:
        command.extend(["-frames:v", "1", str(output)])
    elif count == 4:
        command.extend(
            [
                "-filter_complex",
                "[0][1]hstack=inputs=2[top];[2][3]hstack=inputs=2[bottom];[top][bottom]vstack=inputs=2",
                "-frames:v",
                "1",
                str(output),
            ]
        )
    else:
        inputs = "".join(f"[{index}:v]" for index in range(count))
        command.extend(
            [
                "-filter_complex",
                f"{inputs}hstack=inputs={count}",
                "-frames:v",
                "1",
                str(output),
            ]
        )
    run_command(command)


def make_color_video(
    output: Path,
    *,
    width: int,
    height: int,
    duration: float,
    color: str = "black",
    fps: int = 30,
    ffmpeg_path: str | None = None,
) -> None:
    ffmpeg = binaries(ffmpeg_path=ffmpeg_path)["ffmpeg"]
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def make_tone(output: Path, *, duration: float, ffmpeg_path: str | None = None) -> None:
    ffmpeg = binaries(ffmpeg_path=ffmpeg_path)["ffmpeg"]
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "7",
            str(output),
        ]
    )
