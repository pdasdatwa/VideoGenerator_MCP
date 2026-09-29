"""Stitch cached scene MP4s and mix audio. Does not rerender scenes."""

from __future__ import annotations

from pathlib import Path

from app.models.scene import AudioTrack, Scene
from app.renderer.ffmpeg import binaries, run_command

_XFADE = {
    ("fade", "left"): "fade",
    ("fade", "right"): "fade",
    ("fade", "up"): "fade",
    ("fade", "down"): "fade",
    ("crossfade", "left"): "dissolve",
    ("crossfade", "right"): "dissolve",
    ("crossfade", "up"): "dissolve",
    ("crossfade", "down"): "dissolve",
    ("slide", "left"): "slideleft",
    ("slide", "right"): "slideright",
    ("slide", "up"): "slideup",
    ("slide", "down"): "slidedown",
    ("zoom", "left"): "zoomin",
    ("zoom", "right"): "zoomin",
    ("zoom", "up"): "zoomin",
    ("zoom", "down"): "zoomin",
    ("blur", "left"): "hblur",
    ("blur", "right"): "hblur",
    ("blur", "up"): "hblur",
    ("blur", "down"): "hblur",
    ("whip", "left"): "wipeleft",
    ("whip", "right"): "wiperight",
    ("whip", "up"): "wipeup",
    ("whip", "down"): "wipedown",
}


def stitch_scenes(
    scene_files: list[tuple[Scene, Path]],
    output: Path,
    *,
    fps: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(scene_files) == 1:
        _copy_video(scene_files[0][1], output)
        return
    if all(scene.transition_out.type == "cut" or scene.transition_out.duration == 0 for scene, _ in scene_files[:-1]):
        _concat_copy(scene_files, output)
        return
    _xfade(scene_files, output, fps=fps)


def mix_audio(
    video: Path,
    tracks: list[tuple[AudioTrack, Path]],
    output: Path,
    *,
    duration: float,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not tracks:
        _copy_video(video, output)
        return
    ffmpeg = binaries()["ffmpeg"]
    command = [ffmpeg, "-y", "-i", str(video)]
    filters: list[str] = []
    for index, (track, path) in enumerate(tracks):
        command.extend(["-i", str(path)])
        parts = []
        end = f":end={track.trim_end}" if track.trim_end is not None else ""
        parts.append(f"atrim=start={track.trim_start}{end}")
        parts.append("asetpts=PTS-STARTPTS")
        if track.fade_in > 0:
            parts.append(f"afade=t=in:st=0:d={track.fade_in}")
        clip_duration = track.duration
        if clip_duration is None and track.trim_end is not None:
            clip_duration = track.trim_end - track.trim_start
        if track.fade_out > 0 and clip_duration and clip_duration > track.fade_out:
            start = clip_duration - track.fade_out
            parts.append(f"afade=t=out:st={start}:d={track.fade_out}")
        delay = int(track.start * 1000)
        parts.append(f"adelay={delay}|{delay}")
        parts.append(f"volume={_volume_argument(track, tracks, duration)}")
        chain = f"[{index + 1}:a]" + ",".join(parts) + f"[a{index}]"
        filters.append(chain)
    labels = "".join(f"[a{index}]" for index in range(len(tracks)))
    filters.append(f"{labels}amix=inputs={len(tracks)}:duration=longest:normalize=0,apad=whole_dur={duration}[aout]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-color_range",
            "tv",
            "-c:a",
            "aac",
            "-t",
            f"{duration:.3f}",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run_command(command)


def _copy_video(source: Path, output: Path) -> None:
    """Re-encode to yuv420p so Windows players accept the file. Remotion can emit yuvj420p."""
    ffmpeg = binaries()["ffmpeg"]
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-color_range",
            "tv",
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def _concat_copy(scene_files: list[tuple[Scene, Path]], output: Path) -> None:
    ffmpeg = binaries()["ffmpeg"]
    listing = output.with_suffix(".concat.txt")
    lines = []
    for _, path in scene_files:
        escaped = path.resolve().as_posix().replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines), encoding="utf-8")
    try:
        run_command(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-colorspace",
                "bt709",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-color_range",
                "tv",
                "-an",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
    finally:
        if listing.exists():
            listing.unlink()


def _xfade(scene_files: list[tuple[Scene, Path]], output: Path, *, fps: int) -> None:
    ffmpeg = binaries()["ffmpeg"]
    command = [ffmpeg, "-y"]
    for _, path in scene_files:
        command.extend(["-i", str(path)])
    filters: list[str] = []
    offset = scene_files[0][0].duration
    previous = "[0:v]"
    for index in range(1, len(scene_files)):
        left = scene_files[index - 1][0]
        transition = left.transition_out
        duration = transition.duration if transition.type != "cut" else 0.0
        name = _transition_name(transition)
        if duration <= 0:
            name = "fade"
            duration = 0.001
        offset = offset - duration
        out = f"[v{index}]" if index < len(scene_files) - 1 else "[vout]"
        filters.append(
            f"{previous}[{index}:v]xfade=transition={name}:duration={duration:.3f}:offset={max(offset, 0):.3f}{out}"
        )
        previous = out
        offset += scene_files[index][0].duration
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run_command(command)


def _transition_name(transition) -> str:
    if transition.type == "dip_to_color":
        color = (transition.color or "#000000").lower()
        if color in {"#fff", "#ffffff"}:
            return "fadewhite"
        return "fadeblack"
    return _XFADE.get((transition.type, transition.direction), "fade")


def _volume_argument(track: AudioTrack, tracks: list[tuple[AudioTrack, Path]], duration: float) -> str:
    del duration
    base = _level_expr(track)
    if track.duck is None and not isinstance(track.volume, dict):
        return f"{float(track.volume or 1):.4f}"
    duck = "1" if track.duck is None else _duck_expr(track, tracks)
    return f"'({base})*({duck})'"


def _level_expr(track: AudioTrack) -> str:
    volume = track.volume
    if not isinstance(volume, dict):
        return f"{float(volume or 1):.4f}"
    if "keyframes" in volume:
        return _keyframe_expr(volume["keyframes"], track.start)
    if "from" in volume and "to" in volume:
        span = track.duration or 1
        return (
            f"({float(volume['from']):.4f}+({float(volume['to']):.4f}-{float(volume['from']):.4f})"
            f"*min(max((t-{track.start:.4f})/{span:.4f},0),1))"
        )
    return "1"


def _keyframe_expr(frames: list[dict], start: float) -> str:
    expr = f"{float(frames[-1]['value']):.4f}"
    for left, right in reversed(list(zip(frames, frames[1:]))):
        t0 = start + float(left["time"])
        t1 = start + float(right["time"])
        v0 = float(left["value"])
        v1 = float(right["value"])
        span = (t1 - t0) or 1
        linear = f"({v0:.4f}+({v1:.4f}-{v0:.4f})*(t-{t0:.4f})/{span:.4f})"
        expr = f"if(lt(t,{t1:.4f}),{linear},{expr})"
    first = start + float(frames[0]["time"])
    expr = f"if(lt(t,{first:.4f}),{float(frames[0]['value']):.4f},{expr})"
    return expr


def _duck_expr(track: AudioTrack, tracks: list[tuple[AudioTrack, Path]]) -> str:
    duck = track.duck
    if duck is None:
        return "1"
    expr = "1"
    for other, _path in tracks:
        if other.role != duck.when_role or other.id == track.id or not other.duration:
            continue
        begin = other.start
        end = other.start + other.duration
        attack = max(duck.attack, 0.001)
        release = max(duck.release, 0.001)
        low = duck.to_volume
        a1 = begin + duck.attack
        r1 = end + duck.release
        down = f"(1+({low:.4f}-1)*(t-{begin:.4f})/{attack:.4f})"
        up = f"({low:.4f}+(1-{low:.4f})*(t-{end:.4f})/{release:.4f})"
        piece = (
            f"if(lt(t,{begin:.4f}),1,if(lt(t,{a1:.4f}),{down},"
            f"if(lt(t,{end:.4f}),{low:.4f},if(lt(t,{r1:.4f}),{up},1))))"
        )
        expr = f"({expr})*({piece})"
    return expr
