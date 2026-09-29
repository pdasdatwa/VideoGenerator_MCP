"""Speed-ramp video layers with FFmpeg. Constant rates stay on Remotion."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.renderer.ffmpeg import binaries, run_command
from app.renderer.scene_graph import canonical_json


def resolve_playback(
    source: Path,
    playback: Any,
    *,
    trim_start: float,
    layer_duration: float,
    cache_dir: Path,
) -> tuple[str, float, float]:
    """Return src, constant playback rate, and trim start.

    Keyframed rates are baked into a cached intermediate so Remotion plays them at 1x.
    """
    if not isinstance(playback, dict):
        rate = float(playback or 1)
        return str(source.resolve()), rate, trim_start
    samples = _integrate(playback, layer_duration)
    source_span = samples[-1][0]
    digest = hashlib.sha256(
        f"{source.resolve()}|{canonical_json(playback)}|{trim_start:.4f}|{layer_duration:.4f}".encode()
    ).hexdigest()[:24]
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{digest}.mp4"
    if not target.exists():
        expression = _setpts(samples)
        ffmpeg = binaries()["ffmpeg"]
        run_command(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{trim_start:.4f}",
                "-t",
                f"{max(source_span, 0.04):.4f}",
                "-i",
                str(source),
                "-an",
                "-vf",
                expression,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(target),
            ]
        )
    return str(target.resolve()), 1.0, 0.0


def _rate_at(spec: dict[str, Any], time: float, duration: float) -> float:
    if "keyframes" in spec:
        frames = spec["keyframes"]
        if time <= frames[0]["time"]:
            return float(frames[0]["value"])
        if time >= frames[-1]["time"]:
            return float(frames[-1]["value"])
        for left, right in zip(frames, frames[1:]):
            if left["time"] <= time <= right["time"]:
                span = right["time"] - left["time"] or 1
                local = (time - left["time"]) / span
                return float(left["value"]) + (float(right["value"]) - float(left["value"])) * local
        return float(frames[-1]["value"])
    if "from" in spec and "to" in spec:
        progress = 0 if duration == 0 else min(1, max(0, time / duration))
        return float(spec["from"]) + (float(spec["to"]) - float(spec["from"])) * progress
    return float(spec.get("value", 1))


def _integrate(spec: dict[str, Any], duration: float) -> list[tuple[float, float]]:
    step = 0.1
    clock = 0.0
    source = 0.0
    samples = [(0.0, 0.0)]
    while clock < duration - 1e-6:
        delta = min(step, duration - clock)
        rate = max(_rate_at(spec, clock, duration), 0.05)
        source += rate * delta
        clock += delta
        samples.append((round(source, 4), round(clock, 4)))
    return samples


def _setpts(samples: list[tuple[float, float]]) -> str:
    """Map source time T (seconds) onto output time, then convert with /TB."""
    pieces = []
    for index in range(len(samples) - 1):
        src0, out0 = samples[index]
        src1, out1 = samples[index + 1]
        span = src1 - src0 or 1
        linear = f"({out0}+({out1}-{out0})*(T-{src0})/{span})"
        pieces.append((src1, linear))
    expr = f"({samples[-1][1]})"
    for limit, linear in reversed(pieces):
        expr = f"if(lt(T,{limit}),{linear},{expr})"
    return f"setpts='({expr})/TB'"
