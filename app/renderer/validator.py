"""Validate declarative scenes against registered assets."""

from __future__ import annotations

import math
import re
from typing import Any

from pydantic import ValidationError

from app.errors import MarketingError
from app.models.scene import Scene

MOTION = {
    "fade",
    "fade_up",
    "fade_down",
    "fade_left",
    "fade_right",
    "scale_in",
    "scale_out",
    "slide_left",
    "slide_right",
    "slide_up",
    "slide_down",
    "rotate",
    "ken_burns",
    "parallax",
    "slow_push",
    "slow_pull",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "orbit",
    "float",
    "drift",
    "shake",
    "handheld",
    "word_reveal",
    "character_reveal",
    "typewriter",
}
EASING = {"linear", "ease_in", "ease_out", "ease_in_out", "spring"}
TEXT_ONLY = {"word_reveal", "character_reveal", "typewriter"}
_EFFECT_RANGES = {
    "blur": (0, 40),
    "brightness": (0, 3),
    "contrast": (0, 3),
    "saturation": (0, 3),
}
_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
_LAYER_ASSET = {"image": {"image"}, "video": {"video"}, "svg": {"svg"}}


def parse_scene(payload: dict[str, Any]) -> Scene:
    try:
        scene = Scene.model_validate(payload)
    except ValidationError as exc:
        raise MarketingError(
            "INVALID_SCENE",
            "Scene specification failed schema validation.",
            suggested_action="Compare the scene with rendering://scene-schema and fix the listed fields.",
            details=_pydantic_details(exc),
        ) from exc
    _check_structure(scene)
    return scene


def _check_structure(scene: Scene) -> None:
    ids = [layer.id for layer in scene.layers]
    if len(ids) != len(set(ids)):
        raise MarketingError(
            "INVALID_LAYER",
            f"Scene {scene.scene_id} has duplicate layer ids.",
            suggested_action="Give every layer a unique id.",
            scene_id=scene.scene_id,
        )
    for layer in scene.layers:
        end = layer.start + (layer.duration if layer.duration is not None else scene.duration - layer.start)
        if layer.start >= scene.duration or end - layer.start <= 0:
            raise MarketingError(
                "INVALID_DURATION",
                f"Layer {layer.id} in {scene.scene_id} does not overlap the scene.",
                suggested_action="Set start within the scene and a positive duration.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        if end > scene.duration + 1e-6:
            raise MarketingError(
                "INVALID_DURATION",
                f"Layer {layer.id} extends past the end of {scene.scene_id}.",
                suggested_action="Shorten the layer or increase the scene duration.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        if layer.type in _LAYER_ASSET and not layer.asset_id:
            raise MarketingError(
                "INVALID_LAYER",
                f"Layer {layer.id} of type {layer.type} requires asset_id.",
                suggested_action="Register an asset and set asset_id.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        if layer.type == "text" and not (layer.content and layer.content.strip()):
            raise MarketingError(
                "INVALID_LAYER",
                f"Text layer {layer.id} needs content.",
                suggested_action="Set content to the words that should appear on screen.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        if layer.type == "shape" and not layer.shape:
            raise MarketingError(
                "INVALID_LAYER",
                f"Shape layer {layer.id} needs shape set to rect, ellipse, or gradient.",
                suggested_action="Set the shape field.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        if layer.trim_start is not None and layer.trim_end is not None and layer.trim_end <= layer.trim_start:
            raise MarketingError(
                "INVALID_DURATION",
                f"Layer {layer.id} has trim_end at or before trim_start.",
                suggested_action="Make trim_end greater than trim_start.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        if layer.animation:
            kind = layer.animation.type
            if kind not in MOTION and kind not in EASING:
                raise MarketingError(
                    "INVALID_ANIMATION",
                    f"Animation '{kind}' on layer {layer.id} is not supported.",
                    suggested_action="Use a primitive from rendering://animation-primitives, or an easing name.",
                    scene_id=scene.scene_id,
                    layer_id=layer.id,
                    animation=kind,
                )
            if kind in TEXT_ONLY and layer.type != "text":
                raise MarketingError(
                    "INVALID_ANIMATION",
                    f"Animation '{kind}' is only valid on text layers.",
                    suggested_action="Move word_reveal, character_reveal, or typewriter onto a text layer.",
                    scene_id=scene.scene_id,
                    layer_id=layer.id,
                )
        for field in ("position", "scale", "rotation", "opacity", "anchor", "crop"):
            _check_anim(getattr(layer, field), field, scene.scene_id, layer.id, layer.duration or scene.duration)
        _check_playback(layer.playback_rate, scene.scene_id, layer.id, layer.duration or scene.duration)
        if layer.effects:
            for name, bounds in _EFFECT_RANGES.items():
                _check_effect(getattr(layer.effects, name), name, bounds, scene.scene_id, layer.id, layer.duration or scene.duration)
            if layer.effects.color_tint and not _HEX.match(layer.effects.color_tint.color):
                raise MarketingError(
                    "INVALID_LAYER",
                    f"color_tint on layer {layer.id} must use a hex color.",
                    suggested_action="Set color_tint.color to a value like #FFCC88.",
                    scene_id=scene.scene_id,
                    layer_id=layer.id,
                )
        if layer.mask:
            span = layer.duration or scene.duration
            for field in ("x", "y", "width", "height", "radius"):
                _check_anim(getattr(layer.mask, field), "opacity", scene.scene_id, layer.id, span)
        if layer.fill and not _HEX.match(layer.fill):
            raise MarketingError(
                "INVALID_LAYER",
                f"Layer {layer.id} fill must be a hex color.",
                suggested_action="Use a color like #FFFFFF.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
    if scene.background.type == "color":
        if not scene.background.value or not _HEX.match(scene.background.value):
            raise MarketingError(
                "INVALID_SCENE",
                f"Scene {scene.scene_id} background color must be hex.",
                suggested_action="Set background.value to a color like #000000.",
                scene_id=scene.scene_id,
            )
    elif not scene.background.asset_id:
        raise MarketingError(
            "INVALID_SCENE",
            f"Scene {scene.scene_id} background requires asset_id.",
            suggested_action="Point the background at a registered image or video.",
            scene_id=scene.scene_id,
        )
    if scene.transition_out.type != "cut" and scene.transition_out.duration >= scene.duration:
        raise MarketingError(
            "INVALID_DURATION",
            f"Transition on {scene.scene_id} is longer than the scene.",
            suggested_action="Shorten transition_out.duration so it is less than the scene duration.",
            scene_id=scene.scene_id,
        )
    if scene.transition_out.color and not _HEX.match(scene.transition_out.color):
        raise MarketingError(
            "INVALID_SCENE",
            f"Transition color on {scene.scene_id} must be hex.",
            suggested_action="Use a color like #000000.",
            scene_id=scene.scene_id,
        )
    for track in scene.audio:
        _check_volume(track.volume, scene.scene_id, track.id, track.duration or scene.duration)
        if track.trim_end is not None and track.trim_end <= track.trim_start:
            raise MarketingError(
                "INVALID_DURATION",
                f"Audio {track.id} has trim_end at or before trim_start.",
                suggested_action="Increase trim_end or omit it.",
                scene_id=scene.scene_id,
                audio_id=track.id,
            )


def _check_anim(value: Any, field: str, scene_id: str, layer_id: str, layer_duration: float) -> None:
    if value is None:
        return
    if isinstance(value, bool) or isinstance(value, (int, float)):
        if isinstance(value, bool) or not math.isfinite(float(value)):
            _bad_coord(field, scene_id, layer_id)
        _check_range(field, float(value), scene_id, layer_id)
        return
    if not isinstance(value, dict):
        raise MarketingError(
            "INVALID_LAYER",
            f"{field} on layer {layer_id} must be a number or an object.",
            suggested_action="Use a static number, {from, to}, or {keyframes: [...]}.",
            scene_id=scene_id,
            layer_id=layer_id,
        )
    if "keyframes" in value:
        frames = value["keyframes"]
        if not isinstance(frames, list) or not frames:
            raise MarketingError(
                "INVALID_LAYER",
                f"{field} keyframes on layer {layer_id} must be a non-empty list.",
                suggested_action="Add keyframes with time and value.",
                scene_id=scene_id,
                layer_id=layer_id,
            )
        last = -1.0
        for frame in frames:
            if not isinstance(frame, dict) or "time" not in frame or "value" not in frame:
                raise MarketingError(
                    "INVALID_LAYER",
                    f"A {field} keyframe on layer {layer_id} is missing time or value.",
                    suggested_action="Each keyframe needs time and value.",
                    scene_id=scene_id,
                    layer_id=layer_id,
                )
            time_value = float(frame["time"])
            if time_value < last or time_value > layer_duration + 1e-6:
                raise MarketingError(
                    "INVALID_DURATION",
                    f"{field} keyframe time {time_value} on layer {layer_id} is out of order or past the layer.",
                    suggested_action="Sort keyframe times from 0 through the layer duration.",
                    scene_id=scene_id,
                    layer_id=layer_id,
                )
            last = time_value
            _check_value(field, frame["value"], scene_id, layer_id)
        return
    if "from" in value and "to" in value:
        _check_value(field, value["from"], scene_id, layer_id)
        _check_value(field, value["to"], scene_id, layer_id)
        return
    if field in {"position", "anchor", "crop"} or "x" in value:
        _check_value(field, value, scene_id, layer_id)
        return
    raise MarketingError(
        "INVALID_LAYER",
        f"{field} on layer {layer_id} is not a static value, from/to pair, or keyframe list.",
        suggested_action="Use one of those three forms.",
        scene_id=scene_id,
        layer_id=layer_id,
    )


def _check_value(field: str, value: Any, scene_id: str, layer_id: str) -> None:
    if isinstance(value, dict):
        if field == "crop":
            for key in ("x", "y", "width", "height"):
                if key not in value:
                    raise MarketingError(
                        "INVALID_LAYER",
                        f"crop on layer {layer_id} needs x, y, width, and height.",
                        suggested_action="Provide all four normalized crop values.",
                        scene_id=scene_id,
                        layer_id=layer_id,
                    )
                _check_range(key if key in {"x", "y"} else "scale", float(value[key]), scene_id, layer_id)
            return
        if "x" not in value or "y" not in value:
            raise MarketingError(
                "INVALID_LAYER",
                f"{field} on layer {layer_id} needs x and y.",
                suggested_action="Use normalized coordinates from 0 to 1.",
                scene_id=scene_id,
                layer_id=layer_id,
            )
        _check_range("position", float(value["x"]), scene_id, layer_id)
        _check_range("position", float(value["y"]), scene_id, layer_id)
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _bad_coord(field, scene_id, layer_id)
    _check_range(field, float(value), scene_id, layer_id)


def _check_range(field: str, number: float, scene_id: str, layer_id: str) -> None:
    if field in {"position", "anchor", "opacity", "x", "y"} and not 0 <= number <= 1:
        raise MarketingError(
            "INVALID_COORDINATES",
            f"{field} value {number} on layer {layer_id} is outside 0..1.",
            suggested_action="Use normalized coordinates. x=0 is left, y=0 is top.",
            scene_id=scene_id,
            layer_id=layer_id,
        )
    if field == "scale" and not 0 < number <= 8:
        raise MarketingError(
            "INVALID_LAYER",
            f"scale value {number} on layer {layer_id} must be between 0 and 8.",
            suggested_action="Use a positive scale, typically around 1.",
            scene_id=scene_id,
            layer_id=layer_id,
        )


def _check_playback(value: Any, scene_id: str, layer_id: str, layer_duration: float) -> None:
    _check_bounded_anim(value, "playback_rate", (0, 8), scene_id, layer_id, layer_duration, lower_exclusive=True)


def _check_volume(value: Any, scene_id: str, track_id: str, duration: float) -> None:
    _check_bounded_anim(value, "volume", (0, 2), scene_id, track_id, duration, lower_exclusive=False)


def _check_effect(value: Any, name: str, bounds: tuple[float, float], scene_id: str, layer_id: str, layer_duration: float) -> None:
    _check_bounded_anim(value, name, bounds, scene_id, layer_id, layer_duration, lower_exclusive=False)


def _check_bounded_anim(
    value: Any,
    field: str,
    bounds: tuple[float, float],
    scene_id: str,
    layer_id: str,
    layer_duration: float,
    *,
    lower_exclusive: bool,
) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        _bad_coord(field, scene_id, layer_id)
    if isinstance(value, (int, float)):
        _in_bounds(field, float(value), bounds, scene_id, layer_id, lower_exclusive=lower_exclusive)
        return
    if isinstance(value, dict) and "keyframes" in value:
        frames = value["keyframes"]
        if not isinstance(frames, list) or not frames:
            raise MarketingError(
                "INVALID_LAYER",
                f"{field} keyframes on layer {layer_id} must be a non-empty list.",
                suggested_action="Add keyframes with time and value.",
                scene_id=scene_id,
                layer_id=layer_id,
            )
        last = -1.0
        for frame in frames:
            time_value = float(frame["time"])
            if time_value < last or time_value > layer_duration + 1e-6:
                raise MarketingError(
                    "INVALID_DURATION",
                    f"{field} keyframe time {time_value} on layer {layer_id} is out of order or past the layer.",
                    suggested_action="Sort keyframe times from 0 through the layer duration.",
                    scene_id=scene_id,
                    layer_id=layer_id,
                )
            last = time_value
            _in_bounds(field, float(frame["value"]), bounds, scene_id, layer_id, lower_exclusive=lower_exclusive)
        return
    if isinstance(value, dict) and "from" in value and "to" in value:
        _in_bounds(field, float(value["from"]), bounds, scene_id, layer_id, lower_exclusive=lower_exclusive)
        _in_bounds(field, float(value["to"]), bounds, scene_id, layer_id, lower_exclusive=lower_exclusive)
        return
    raise MarketingError(
        "INVALID_LAYER",
        f"{field} on layer {layer_id} must be a number, from/to pair, or keyframe list.",
        suggested_action="Use one of those three forms.",
        scene_id=scene_id,
        layer_id=layer_id,
    )


def _in_bounds(
    field: str,
    number: float,
    bounds: tuple[float, float],
    scene_id: str,
    layer_id: str,
    *,
    lower_exclusive: bool,
) -> None:
    low, high = bounds
    ok = (low < number <= high) if lower_exclusive else (low <= number <= high)
    if not ok or not math.isfinite(number):
        raise MarketingError(
            "INVALID_LAYER",
            f"{field} value {number} on layer {layer_id} is outside {low}..{high}.",
            suggested_action="Use a value inside the documented range.",
            scene_id=scene_id,
            layer_id=layer_id,
        )


def _bad_coord(field: str, scene_id: str, layer_id: str) -> None:
    raise MarketingError(
        "INVALID_COORDINATES",
        f"{field} on layer {layer_id} is not a finite number.",
        suggested_action="Replace the value with a finite number or keyframe list.",
        scene_id=scene_id,
        layer_id=layer_id,
    )


def _pydantic_details(exc: ValidationError) -> list[dict[str, Any]]:
    details = []
    for error in exc.errors():
        details.append({"loc": [str(part) for part in error["loc"]], "msg": error["msg"]})
    return details
