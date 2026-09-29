"""Compile a cartoon block into ordinary layers plus a camera track.

Nothing cartoon specific reaches the renderer: a compiled scene is the same Scene model that
standard mode produces, so validation, cache keys, Remotion, stitching, mixing, and versioning
all stay on one path. The camera is the single extra prop, and it is omitted for standard scenes.

Compiled layers are deliberately allowed outside the 0..1 frame box, which is how a character
walks in from off screen. The client facing coordinate check in app.renderer.validator still
guards everything a caller writes by hand.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from app.errors import MarketingError
from app.models.asset import Asset
from app.models.cartoon import CartoonAction, Dialogue, SceneCharacter
from app.models.character import Character, Point
from app.models.project import Project
from app.models.scene import Scene
from app.renderer.cartoon.names import CAMERA_SHOTS, CARTOON_COMPILER_VERSION
from app.renderer.cartoon.primitives import (
    Deltas,
    ResolvedAction,
    compose,
    resolve_action,
    sample_times,
)
from app.renderer.cartoon.resolve import resolve_character_asset

# Layer stacking, lowest first. Manual layers keep whatever z_index the caller chose.
Z_BACKGROUND = 0
Z_MIDGROUND = 5
Z_PROP = 15
Z_CHARACTER = 20
Z_FOREGROUND = 50
Z_DIALOGUE = 60

_LINEAR = {"type": "linear", "duration": None, "easing": "linear"}
_EPSILON = 1e-6
_STEP = 1.0 / 96
_BUBBLE_PAD = 1.12


@dataclass
class CompiledScene:
    """The renderable form of a scene."""

    scene: Scene
    camera: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    compiler_version: str = CARTOON_COMPILER_VERSION


def compile_cartoon_scene(
    scene: Scene,
    project: Project,
    assets: dict[str, Asset],
    characters: dict[str, Character],
) -> CompiledScene:
    """Return the scene the renderer should draw. Standard scenes pass straight through."""
    if scene.cartoon is None:
        return CompiledScene(scene=scene, camera=None, asset_ids=_manual_asset_ids(scene))
    builder = _Builder(scene, project, assets, characters)
    return builder.build()


class _Builder:
    def __init__(
        self,
        scene: Scene,
        project: Project,
        assets: dict[str, Asset],
        characters: dict[str, Character],
    ) -> None:
        self.scene = scene
        self.spec = scene.cartoon
        self.project = project
        self.assets = assets
        self.characters = characters
        self.frame_aspect = project.width / project.height if project.height else 1.0
        self.warnings: list[str] = []
        self.layers: list[dict[str, Any]] = []
        self.used_assets: list[str] = []
        # Resting placement and sampled motion per character, reused by dialogue and camera.
        self.tracks: dict[str, _CharacterTrack] = {}
        self._camera_cache: list[tuple[float, float, float, float, float]] | None = None

    def build(self) -> CompiledScene:
        # Characters first: dialogue placement, camera focus, and parallax all read their tracks.
        self._characters()
        self._background()
        self._props()
        self._dialogue()
        camera = self._camera()
        payload = self.scene.model_dump(mode="json")
        payload["cartoon"] = None
        compiled_layers = sorted(self.layers, key=lambda item: (item["z_index"], item["id"]))
        payload["layers"] = compiled_layers + payload.get("layers", [])
        compiled = Scene.model_validate(payload)
        _check_compiled(compiled)
        asset_ids = _dedupe(self.used_assets + _manual_asset_ids(self.scene))
        return CompiledScene(scene=compiled, camera=camera, warnings=self.warnings, asset_ids=asset_ids)

    # Background ------------------------------------------------------------

    def _background(self) -> None:
        background = self.spec.background
        if background is None:
            return
        plates = [
            ("cbg_main", background.asset_id, Z_BACKGROUND, 1.0),
            ("cbg_bg", background.background, Z_BACKGROUND, 1.0),
            ("cbg_mid", background.midground, Z_MIDGROUND, 0.5),
            ("cbg_fg", background.foreground, Z_FOREGROUND, 0.0),
        ]
        for layer_id, asset_id, z_index, depth in plates:
            if not asset_id:
                continue
            asset = self._asset(asset_id)
            layer = {
                "id": layer_id,
                "type": "svg" if asset.type == "svg" else "image",
                "asset_id": asset_id,
                "start": 0,
                "duration": self.scene.duration,
                "z_index": z_index,
                "width": 1.0,
                "height": 1.0,
                "position": {"x": 0.5, "y": 0.5},
                "anchor": {"x": 0.5, "y": 0.5},
                "fit": background.fit,
                "animation": dict(_LINEAR),
            }
            drift = background.parallax * depth
            if drift > 0:
                layer["position"] = self._parallax_track(drift)
            self.layers.append(layer)

    def _parallax_track(self, depth: float) -> dict[str, Any]:
        """A plate that follows the camera moves less against the frame, so it reads as distant."""
        camera = self._camera_samples()
        if camera is None:
            return {"x": 0.5, "y": 0.5}
        frames = [
            {"time": round(time, 6), "value": {"x": 0.5 + (x - 0.5) * depth, "y": 0.5 + (y - 0.5) * depth}}
            for time, x, y, _zoom, _rotation in camera
        ]
        return _compress_vector(frames, {"x": 0.5, "y": 0.5})

    # Characters ------------------------------------------------------------

    def _characters(self) -> None:
        for placement in self.spec.characters:
            character = self.characters.get(placement.character_id)
            if character is None:
                raise MarketingError(
                    "CHARACTER_NOT_FOUND",
                    f"Scene {self.scene.scene_id} references character '{placement.character_id}'.",
                    suggested_action="Call create_character before placing the character in a scene.",
                    scene_id=self.scene.scene_id,
                    character_id=placement.character_id,
                )
            track = self._build_track(placement, character)
            self.tracks[placement.character_id] = track
            asset_id = resolve_character_asset(character, placement.pose, placement.expression)
            if not asset_id:
                raise MarketingError(
                    "MISSING_CHARACTER_ASSET",
                    f"Character '{placement.character_id}' has no artwork to draw.",
                    suggested_action="Register at least a base asset with register_character_asset(role='character_base').",
                    scene_id=self.scene.scene_id,
                    character_id=placement.character_id,
                )
            swap = _expression_swap(placement, character)
            base_opacity = track.opacity
            if swap is not None:
                base_opacity = _multiply_track(track.opacity, _fade(swap, track, out=True))
            self.layers.append(
                self._sprite(
                    _layer_id("char", placement.character_id),
                    asset_id,
                    track,
                    z_index=placement.z_index,
                    opacity=base_opacity,
                )
            )
            if swap is not None:
                target = character.assets.expressions[swap.to]  # validated earlier
                self.layers.append(
                    self._sprite(
                        _layer_id("char", placement.character_id, "expr"),
                        target,
                        track,
                        z_index=placement.z_index,
                        opacity=_multiply_track(track.opacity, _fade(swap, track, out=False)),
                    )
                )
            self._parts(placement, character, track)

    def _parts(self, placement: SceneCharacter, character: Character, track: "_CharacterTrack") -> None:
        """Mouth and eye overlays. Part artwork is expected to sit on the character's own canvas."""
        talk = [action for action in track.actions if action.type == "talk"]
        blink = [action for action in track.actions if action.type == "blink"]
        parts = character.assets.parts
        if talk:
            if "mouth_open" in parts and "mouth_closed" in parts:
                windows = _flutter(talk, track, cycles_per_second=5.0)
                self._overlay(placement, track, parts["mouth_closed"], "mouth_closed", _invert(windows, track))
                self._overlay(placement, track, parts["mouth_open"], "mouth_open", windows)
            else:
                self.warnings.append(
                    f"Character '{placement.character_id}' has no mouth_open and mouth_closed parts, so talk only bobs the body."
                )
        if blink:
            if "eyes_closed" in parts:
                windows = _flutter(blink, track, cycles_per_second=1.6, duty=0.12)
                self._overlay(placement, track, parts["eyes_closed"], "eyes_closed", windows)
            else:
                self.warnings.append(
                    f"Character '{placement.character_id}' has no eyes_closed part, so blink does nothing."
                )
        for accessory in placement.accessories:
            asset_id = character.assets.accessories.get(accessory)
            if asset_id:
                self._overlay(placement, track, asset_id, f"acc_{accessory}", track.opacity)

    def _overlay(
        self,
        placement: SceneCharacter,
        track: "_CharacterTrack",
        asset_id: str,
        name: str,
        opacity: Any,
    ) -> None:
        self.layers.append(
            self._sprite(
                _layer_id("char", placement.character_id, name),
                asset_id,
                track,
                z_index=placement.z_index + 1,
                opacity=opacity,
            )
        )

    def _sprite(
        self,
        layer_id: str,
        asset_id: str,
        track: "_CharacterTrack",
        *,
        z_index: int,
        opacity: Any,
    ) -> dict[str, Any]:
        asset = self._asset(asset_id)
        width, height = self._box(asset, track.size)
        layer: dict[str, Any] = {
            "id": layer_id,
            "type": "svg" if asset.type == "svg" else "image",
            "asset_id": asset_id,
            "start": round(track.start, 6),
            "duration": round(track.duration, 6),
            "z_index": z_index,
            "width": width,
            "height": height,
            "anchor": {"x": track.anchor.x, "y": track.anchor.y},
            "fit": "contain",
            "animation": dict(_LINEAR),
            "position": track.position,
            "scale": track.scale,
            "rotation": track.rotation,
            "opacity": opacity,
        }
        return layer

    def _build_track(self, placement: SceneCharacter, character: Character) -> "_CharacterTrack":
        base_position = placement.position or character.default_position
        anchor = placement.anchor or character.default_anchor
        base_scale = placement.scale if placement.scale is not None else character.default_scale
        size = placement.size if placement.size is not None else character.default_size
        start = min(placement.start, max(0.0, self.scene.duration - _EPSILON))
        duration = placement.duration if placement.duration is not None else self.scene.duration - start
        duration = max(_STEP, min(duration, self.scene.duration - start))
        actions = [
            resolve_action(action, scene_duration=self.scene.duration, target=self._target(action))
            for action in placement.actions
        ]
        asset = self._asset(resolve_character_asset(character, placement.pose, placement.expression) or "")
        _, height = self._box(asset, size)
        times = sample_times(actions, start=start, duration=duration)
        positions: list[dict[str, Any]] = []
        scales: list[dict[str, Any]] = []
        rotations: list[dict[str, Any]] = []
        opacities: list[dict[str, Any]] = []
        for time in times:
            deltas = compose(actions, start + time)
            scale = base_scale * deltas.scale
            # Uniform scale happens around the box centre, so a bottom anchored character would
            # slide off the floor. Compensate so the anchor point stays where it was placed.
            lift = -(scale - base_scale) * (anchor.y - 0.5) * height
            positions.append(
                {
                    "time": round(time, 6),
                    "value": {
                        "x": round(base_position.x + deltas.dx, 6),
                        "y": round(base_position.y + deltas.dy + lift, 6),
                    },
                }
            )
            scales.append({"time": round(time, 6), "value": round(scale, 6)})
            rotations.append({"time": round(time, 6), "value": round(placement.rotation + deltas.rotation, 6)})
            opacities.append({"time": round(time, 6), "value": round(_clamp01(placement.opacity * deltas.opacity), 6)})
        return _CharacterTrack(
            character_id=placement.character_id,
            start=start,
            duration=duration,
            size=size,
            anchor=anchor,
            base_position=base_position,
            times=times,
            position=_compress_vector(positions, {"x": base_position.x, "y": base_position.y}),
            scale=_compress_number(scales, base_scale),
            rotation=_compress_number(rotations, placement.rotation),
            opacity=_compress_number(opacities, placement.opacity),
            actions=actions,
            height=height,
        )

    def _target(self, action: CartoonAction) -> tuple[float, float] | None:
        target = action.target
        if target is None:
            return None
        if isinstance(target, Point):
            return (target.x, target.y)
        other = next((item for item in self.spec.characters if item.character_id == target), None)
        if other is None:
            return None
        character = self.characters.get(target)
        position = other.position or (character.default_position if character else Point(x=0.5, y=0.78))
        return (position.x, position.y)

    # Props -----------------------------------------------------------------

    def _props(self) -> None:
        for prop in self.spec.props:
            asset = self._asset(prop.asset_id)
            size = prop.size if prop.size is not None else 0.18
            width, height = self._box(asset, size)
            anchor = prop.anchor or Point(x=0.5, y=0.5)
            start = min(prop.start, max(0.0, self.scene.duration - _EPSILON))
            duration = prop.duration if prop.duration is not None else self.scene.duration - start
            duration = max(_STEP, min(duration, self.scene.duration - start))
            layer: dict[str, Any] = {
                "id": _layer_id("prop", prop.prop_id),
                "type": "svg" if asset.type == "svg" else "image",
                "asset_id": prop.asset_id,
                "start": round(start, 6),
                "duration": round(duration, 6),
                "z_index": prop.z_index,
                "width": width,
                "height": height,
                "anchor": {"x": anchor.x, "y": anchor.y},
                "fit": "contain",
                "animation": dict(_LINEAR),
                "position": {"x": prop.position.x, "y": prop.position.y},
                "scale": prop.scale,
                "rotation": prop.rotation,
                "opacity": prop.opacity,
            }
            if prop.animation is not None:
                action = resolve_action(prop.animation, scene_duration=self.scene.duration, target=None)
                times = sample_times([action], start=start, duration=duration)
                positions = []
                scales = []
                rotations = []
                opacities = []
                for time in times:
                    deltas = compose([action], start + time)
                    scale = prop.scale * deltas.scale
                    lift = -(scale - prop.scale) * (anchor.y - 0.5) * height
                    positions.append(
                        {
                            "time": round(time, 6),
                            "value": {
                                "x": round(prop.position.x + deltas.dx, 6),
                                "y": round(prop.position.y + deltas.dy + lift, 6),
                            },
                        }
                    )
                    scales.append({"time": round(time, 6), "value": round(scale, 6)})
                    rotations.append({"time": round(time, 6), "value": round(prop.rotation + deltas.rotation, 6)})
                    opacities.append({"time": round(time, 6), "value": round(_clamp01(prop.opacity * deltas.opacity), 6)})
                layer["position"] = _compress_vector(positions, {"x": prop.position.x, "y": prop.position.y})
                layer["scale"] = _compress_number(scales, prop.scale)
                layer["rotation"] = _compress_number(rotations, prop.rotation)
                layer["opacity"] = _compress_number(opacities, prop.opacity)
            self.layers.append(layer)

    # Dialogue --------------------------------------------------------------

    def _dialogue(self) -> None:
        left, right, top, bottom = self._visible_window()
        for line in self.spec.dialogue:
            style = line.style
            anchor_point = self._dialogue_anchor(line)
            font_size = self._font_size(line)
            max_width = min(style.max_width if style else 0.42, (right - left) / _BUBBLE_PAD - 0.02)
            max_width = max(0.12, max_width)
            text_height = self._text_height(line.text, font_size, max_width)
            bubble_height = text_height + (font_size * 0.9) / self.project.height
            half_width = max_width * _BUBBLE_PAD / 2
            half_height = bubble_height * 1.25 / 2
            centre = {
                "x": round(_fit_between(anchor_point[0], left + half_width, right - half_width), 6),
                "y": round(
                    _fit_between(anchor_point[1] - bubble_height / 2, top + half_height, bottom - half_height),
                    6,
                ),
            }
            z_index = style.z_index if style else Z_DIALOGUE
            if style is None or style.bubble:
                self.layers.append(self._bubble(line, centre, max_width, bubble_height, z_index))
            self.layers.append(
                {
                    "id": _layer_id("dlg", line.dialogue_id, "text"),
                    "type": "text",
                    "content": line.text,
                    "start": round(line.start, 6),
                    "duration": round(line.duration, 6),
                    "z_index": z_index + 1,
                    "width": max_width,
                    "height": round(text_height, 6),
                    "position": centre,
                    "anchor": {"x": 0.5, "y": 0.5},
                    "respect_safe_area": False,
                    "animation": {"type": line.animation or "fade", "duration": None, "easing": None},
                    "style": {
                        "font_family": style.font_family if style else "Inter",
                        "font_size": font_size,
                        "font_weight": style.font_weight if style else 600,
                        "color": style.text_color if style else "#111111",
                        "align": style.align if style else "center",
                        "line_height": 1.25,
                        "max_width": max_width,
                    },
                }
            )

    def _bubble(
        self,
        line: Dialogue,
        centre: dict[str, float],
        width: float,
        height: float,
        z_index: int,
    ) -> dict[str, Any]:
        style = line.style
        padded_width = round(width * _BUBBLE_PAD, 6)
        padded_height = round(height * 1.25, 6)
        layer: dict[str, Any] = {
            "id": _layer_id("dlg", line.dialogue_id, "bubble"),
            "start": round(line.start, 6),
            "duration": round(line.duration, 6),
            "z_index": z_index,
            "width": padded_width,
            "height": padded_height,
            "position": centre,
            "anchor": {"x": 0.5, "y": 0.5},
            "opacity": style.bubble_opacity if style else 1,
            "animation": {"type": line.animation if line.animation in {"fade", "scale_in"} else "fade", "duration": None, "easing": None},
        }
        if style and style.bubble_asset_id:
            asset = self._asset(style.bubble_asset_id)
            layer.update(
                {
                    "type": "svg" if asset.type == "svg" else "image",
                    "asset_id": style.bubble_asset_id,
                    "fit": "fill",
                }
            )
        else:
            layer.update(
                {
                    "type": "shape",
                    "shape": "rect",
                    "fill": style.bubble_color if style else "#FFFFFF",
                    "border_radius": 0.22,
                }
            )
        return layer

    def _dialogue_anchor(self, line: Dialogue) -> tuple[float, float]:
        if line.style and line.style.position:
            point = line.style.position
            return (point.x, point.y)
        offset = line.style.offset if line.style and line.style.offset else None
        if line.character_id and line.character_id in self.tracks:
            track = self.tracks[line.character_id]
            # Sample where the speaker stands when the line begins, so a moving character does
            # not drag the bubble around mid sentence.
            x, y = track.at(line.start)
            top = y - track.height * 1.02
            if offset:
                x += offset.x - 0.5
                top += offset.y - 0.5
            return (x, max(0.08, top))
        if offset:
            return (offset.x, offset.y)
        return (0.5, 0.86)

    def _font_size(self, line: Dialogue) -> float:
        if line.style and line.style.font_size:
            return line.style.font_size
        return round(max(14.0, min(400.0, self.project.height * 0.030)), 2)

    def _text_height(self, text: str, font_size: float, max_width: float) -> float:
        per_line = max(8, int((max_width * self.project.width) / (font_size * 0.54)))
        lines = 0
        for paragraph in text.split("\n"):
            lines += max(1, math.ceil(len(paragraph) / per_line))
        return round(min(0.6, (lines * font_size * 1.25) / self.project.height), 6)

    # Camera ----------------------------------------------------------------

    def _camera_samples(self) -> list[tuple[float, float, float, float, float]] | None:
        camera = self.spec.camera
        if camera is None:
            return None
        if self._camera_cache is not None:
            return self._camera_cache
        base_zoom = camera.zoom if camera.zoom is not None else CAMERA_SHOTS.get(camera.shot or "wide", 1.0)
        base_point = self._camera_point(camera)
        animation = camera.animation
        samples: list[tuple[float, float, float, float, float]] = []
        if animation is None and not camera.keyframes:
            samples = [(0.0, base_point[0], base_point[1], base_zoom, camera.rotation)]
        elif camera.keyframes:
            for frame in camera.keyframes:
                samples.append(
                    (
                        round(frame.time, 6),
                        frame.position.x if frame.position else base_point[0],
                        frame.position.y if frame.position else base_point[1],
                        frame.zoom if frame.zoom is not None else base_zoom,
                        frame.rotation if frame.rotation is not None else camera.rotation,
                    )
                )
        else:
            samples = _camera_move(animation, base_point, base_zoom, camera.rotation, self.scene.duration)
        self._camera_cache = samples
        return samples

    def _camera(self) -> dict[str, Any] | None:
        samples = self._camera_samples()
        if samples is None:
            return None
        positions = [{"time": time, "value": {"x": round(x, 6), "y": round(y, 6)}} for time, x, y, _z, _r in samples]
        zooms = [{"time": time, "value": round(zoom, 6)} for time, _x, _y, zoom, _r in samples]
        rotations = [{"time": time, "value": round(rotation, 6)} for time, _x, _y, _z, rotation in samples]
        first = samples[0]
        return {
            "position": _anim_prop(_compress_vector(positions, {"x": first[1], "y": first[2]})),
            "zoom": _anim_prop(_compress_number(zooms, first[3])),
            "rotation": _anim_prop(_compress_number(rotations, first[4])),
        }

    def _visible_window(self) -> tuple[float, float, float, float]:
        """The part of the frame the camera shows for the whole scene, as left, right, top, bottom.

        A zoomed camera crops the frame, so a bubble placed at the edge would be cut in half.
        Dialogue is kept inside the window that stays visible for every camera sample.
        """
        samples = self._camera_samples()
        if not samples:
            return (0.0, 1.0, 0.0, 1.0)
        left, right, top, bottom = 0.0, 1.0, 0.0, 1.0
        for _time, x, y, zoom, _rotation in samples:
            half = 0.5 / max(zoom, 1e-6)
            left = max(left, x - half)
            right = min(right, x + half)
            top = max(top, y - half)
            bottom = min(bottom, y + half)
        return (left, right, top, bottom)

    def _camera_point(self, camera: Any) -> tuple[float, float]:
        if camera.position is not None:
            return (camera.position.x, camera.position.y)
        if camera.focus and camera.focus in self.tracks:
            track = self.tracks[camera.focus]
            x, y = track.at(0.0)
            # Frame the upper body rather than the feet.
            return (_clamp(x, 0.0, 1.0), _clamp(y - track.height * 0.5, 0.0, 1.0))
        return (0.5, 0.5)

    # Helpers ---------------------------------------------------------------

    def _asset(self, asset_id: str) -> Asset:
        asset = self.assets.get(asset_id)
        if asset is None:
            raise MarketingError(
                "INVALID_ASSET_REFERENCE",
                f"Scene {self.scene.scene_id} references asset {asset_id}, but that asset does not exist.",
                suggested_action="Register the asset before rendering this scene.",
                scene_id=self.scene.scene_id,
                asset_id=asset_id,
            )
        if asset_id not in self.used_assets:
            self.used_assets.append(asset_id)
        return asset

    def _box(self, asset: Asset, size: float) -> tuple[float, float]:
        """Size is the sprite height as a fraction of the frame. Width follows the artwork."""
        ratio = 1.0
        if asset.width and asset.height:
            ratio = asset.width / asset.height
        width = size * ratio / self.frame_aspect
        return (round(_clamp(width, 0.01, 2.0), 6), round(_clamp(size, 0.01, 2.0), 6))


@dataclass
class _CharacterTrack:
    character_id: str
    start: float
    duration: float
    size: float
    anchor: Point
    base_position: Point
    times: list[float]
    position: Any
    scale: Any
    rotation: Any
    opacity: Any
    actions: list[ResolvedAction]
    height: float

    def at(self, time: float) -> tuple[float, float]:
        """Where the character stands at an absolute scene time."""
        deltas: Deltas = compose(self.actions, time)
        return (self.base_position.x + deltas.dx, self.base_position.y + deltas.dy)


@dataclass(frozen=True)
class _Swap:
    to: str
    start: float
    end: float


def _expression_swap(placement: SceneCharacter, character: Character) -> _Swap | None:
    for action in placement.actions:
        if action.type == "expression_change" and action.to and action.to in character.assets.expressions:
            duration = action.duration if action.duration is not None else 0.4
            return _Swap(to=action.to, start=action.start, end=action.start + duration)
    return None


def _fade(swap: _Swap, track: _CharacterTrack, *, out: bool) -> list[dict[str, Any]]:
    start = max(0.0, swap.start - track.start)
    end = max(start + _STEP, swap.end - track.start)
    high, low = (1.0, 0.0) if out else (0.0, 1.0)
    frames = [{"time": 0.0, "value": high}, {"time": round(start, 6), "value": high}, {"time": round(end, 6), "value": low}]
    if end < track.duration:
        frames.append({"time": round(track.duration, 6), "value": low})
    return frames


def _flutter(
    actions: list[ResolvedAction],
    track: _CharacterTrack,
    *,
    cycles_per_second: float,
    duty: float = 0.5,
) -> list[dict[str, Any]]:
    """A hard on/off opacity series across the windows of the given actions."""
    frames: list[dict[str, Any]] = [{"time": 0.0, "value": 0.0}]
    for action in actions:
        period = 1.0 / cycles_per_second
        count = max(1, int(round(action.duration * cycles_per_second)))
        for index in range(count):
            on = action.start + index * period - track.start
            off = on + period * duty
            for moment, value in ((on, 1.0), (off, 0.0)):
                clamped = round(_clamp(moment, 0.0, track.duration), 6)
                previous = 0.0 if value else 1.0
                frames.append({"time": round(max(0.0, clamped - _STEP), 6), "value": previous})
                frames.append({"time": clamped, "value": value})
    frames.append({"time": round(track.duration, 6), "value": 0.0})
    frames.sort(key=lambda item: item["time"])
    deduped: list[dict[str, Any]] = []
    for frame in frames:
        if deduped and abs(deduped[-1]["time"] - frame["time"]) < 1e-9:
            deduped[-1] = frame
            continue
        deduped.append(frame)
    return deduped


def _invert(frames: list[dict[str, Any]], track: _CharacterTrack) -> list[dict[str, Any]]:
    return [{"time": frame["time"], "value": round(1.0 - float(frame["value"]), 6)} for frame in frames]


def _multiply_track(base: Any, frames: list[dict[str, Any]]) -> Any:
    """Combine a sampled opacity series with whatever the placement already asked for."""
    if isinstance(base, (int, float)):
        scaled = [{"time": frame["time"], "value": round(float(base) * float(frame["value"]), 6)} for frame in frames]
        return _compress_number(scaled, float(base))
    return _compress_number(frames, 1.0)


def _camera_move(
    animation: Any,
    point: tuple[float, float],
    zoom: float,
    rotation: float,
    scene_duration: float,
) -> list[tuple[float, float, float, float, float]]:
    start = min(animation.start, scene_duration)
    duration = animation.duration if animation.duration is not None else max(0.1, scene_duration - start)
    duration = max(0.1, min(duration, scene_duration - start))
    end = start + duration
    amount = animation.amount if animation.amount is not None else None
    kind = animation.type
    samples: list[tuple[float, float, float, float, float]] = [(0.0, point[0], point[1], zoom, rotation)]
    if start > 0:
        samples.append((round(start, 6), point[0], point[1], zoom, rotation))
    if kind == "hold":
        return samples
    if kind in {"push_in", "pull_out"}:
        factor = amount if amount else 0.35
        target = zoom * (1 + factor) if kind == "push_in" else max(0.25, zoom * (1 - factor))
        samples.append((round(end, 6), point[0], point[1], round(target, 6), rotation))
    elif kind in {"pan_left", "pan_right", "tilt_up", "tilt_down"}:
        distance = amount if amount else 0.2
        dx = {"pan_left": -distance, "pan_right": distance}.get(kind, 0.0)
        dy = {"tilt_up": -distance, "tilt_down": distance}.get(kind, 0.0)
        samples.append((round(end, 6), round(point[0] + dx, 6), round(point[1] + dy, 6), zoom, rotation))
    elif kind == "shake":
        magnitude = 0.012 * animation.intensity
        steps = max(2, int(round(duration * 12)))
        for index in range(1, steps + 1):
            progress = index / steps
            moment = start + duration * progress
            decay = 1 - progress
            samples.append(
                (
                    round(moment, 6),
                    round(point[0] + math.sin(progress * math.pi * 8) * magnitude * decay, 6),
                    round(point[1] + math.cos(progress * math.pi * 7) * magnitude * decay, 6),
                    zoom,
                    rotation,
                )
            )
    if end < scene_duration:
        last = samples[-1]
        samples.append((round(scene_duration, 6), last[1], last[2], last[3], last[4]))
    return samples


def _anim_prop(value: Any) -> dict[str, Any]:
    """The renderer's Anim shape, matching app.renderer.scene_graph._anim."""
    if isinstance(value, dict) and "keyframes" in value:
        return {"mode": "keyframes", "keyframes": value["keyframes"]}
    return {"mode": "static", "value": value}


def _compress_number(frames: list[dict[str, Any]], default: float) -> Any:
    if not frames:
        return default
    values = [float(frame["value"]) for frame in frames]
    if max(values) - min(values) < 1e-6:
        return round(values[0], 6)
    return {"keyframes": _drop_flat(frames)}


def _compress_vector(frames: list[dict[str, Any]], default: dict[str, float]) -> Any:
    if not frames:
        return default
    xs = [float(frame["value"]["x"]) for frame in frames]
    ys = [float(frame["value"]["y"]) for frame in frames]
    if max(xs) - min(xs) < 1e-6 and max(ys) - min(ys) < 1e-6:
        return {"x": round(xs[0], 6), "y": round(ys[0], 6)}
    return {"keyframes": _drop_flat(frames)}


def _drop_flat(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove samples that sit exactly between two identical neighbours."""
    if len(frames) <= 2:
        return frames
    kept = [frames[0]]
    for index in range(1, len(frames) - 1):
        previous, current, following = frames[index - 1], frames[index], frames[index + 1]
        if _same(previous["value"], current["value"]) and _same(current["value"], following["value"]):
            continue
        kept.append(current)
    kept.append(frames[-1])
    return kept


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return abs(left["x"] - right["x"]) < 1e-6 and abs(left["y"] - right["y"]) < 1e-6
    return abs(float(left) - float(right)) < 1e-6


def _check_compiled(scene: Scene) -> None:
    """Invariants the renderer relies on. Coordinates may leave the frame on purpose."""
    ids = [layer.id for layer in scene.layers]
    duplicates = {value for value in ids if ids.count(value) > 1}
    if duplicates:
        raise MarketingError(
            "INVALID_CARTOON_SCENE",
            f"Compiled scene {scene.scene_id} has duplicate layer ids: {', '.join(sorted(duplicates))}.",
            suggested_action="Rename the manual layer that collides with a compiled cartoon layer.",
            scene_id=scene.scene_id,
        )
    for layer in scene.layers:
        span = layer.duration if layer.duration is not None else scene.duration - layer.start
        if layer.start < -_EPSILON or span <= 0 or layer.start + span > scene.duration + 1e-3:
            raise MarketingError(
                "INVALID_DURATION",
                f"Compiled layer {layer.id} does not fit inside scene {scene.scene_id}.",
                suggested_action="Shorten the action, dialogue, or prop window, or lengthen the scene.",
                scene_id=scene.scene_id,
                layer_id=layer.id,
            )
        for field_name in ("position", "scale", "rotation", "opacity"):
            _check_keyframes(scene, layer.id, field_name, getattr(layer, field_name), span)


def _check_keyframes(scene: Scene, layer_id: str, field_name: str, value: Any, span: float) -> None:
    if not isinstance(value, dict) or "keyframes" not in value:
        return
    last = -1.0
    for frame in value["keyframes"]:
        time = float(frame["time"])
        if time < last - 1e-9 or time > span + 1e-3:
            raise MarketingError(
                "INVALID_CARTOON_SCENE",
                f"Compiled {field_name} keyframes on {layer_id} are out of order or past the layer.",
                suggested_action="This is an engine fault. Report the scene specification that produced it.",
                scene_id=scene.scene_id,
                layer_id=layer_id,
            )
        last = time


def _manual_asset_ids(scene: Scene) -> list[str]:
    ids: list[str] = []
    if scene.background.asset_id:
        ids.append(scene.background.asset_id)
    ids.extend(layer.asset_id for layer in scene.layers if layer.asset_id)
    return _dedupe(ids)


def _dedupe(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def _layer_id(prefix: str, *parts: str) -> str:
    """Stable compiled layer id. Layer ids are limited to 64 characters."""
    candidate = "_".join([prefix, *parts])
    if len(candidate) <= 64:
        return candidate
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:8]
    return f"{candidate[:55]}_{digest}"


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _fit_between(value: float, low: float, high: float) -> float:
    """Clamp, but centre the value when the window is narrower than the thing being placed."""
    if low > high:
        return (low + high) / 2
    return _clamp(value, low, high)
