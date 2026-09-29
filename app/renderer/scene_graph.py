"""Turn a validated scene into Remotion input props. Audio is omitted on purpose."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.renderer.validator import parse_scene


def visual_dict(scene: Scene) -> dict[str, Any]:
    """Canonical visual specification. Audio is excluded so mixes do not bust the cache."""
    payload = scene.model_dump(mode="json")
    payload.pop("audio", None)
    if payload.get("cartoon") is None:
        # A standard scene keeps the exact shape it had before cartoon mode existed.
        payload.pop("cartoon", None)
    return payload


def canonical_json(payload: Any) -> str:
    return json.dumps(_stabilize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stabilize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _stabilize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stabilize(item) for item in value]
    return value


def build_scene_props(
    project: Project,
    scene: Scene,
    assets: dict[str, Asset],
    *,
    width: int,
    height: int,
    renderer_version: str,
    crf: int,
    data_root: Path,
    compiled: Any | None = None,
) -> dict[str, Any]:
    """Props for one scene. A cartoon scene is compiled first; a standard scene is unchanged."""
    camera = None
    if compiled is not None:
        scene = compiled.scene
        camera = compiled.camera
    props = {
        "sceneId": scene.scene_id,
        "rendererVersion": renderer_version,
        "width": width,
        "height": height,
        "fps": project.fps,
        "duration": scene.duration,
        "background": _background(scene, assets, data_root),
        "layers": [_layer(layer.model_dump(mode="json"), scene, assets, data_root) for layer in scene.layers],
        "safeArea": project.safe_area.model_dump(),
        "globalEffects": project.global_effects.model_dump(),
        "render": {"crf": crf},
    }
    if camera is not None:
        props["camera"] = camera
    return props


def _background(scene: Scene, assets: dict[str, Asset], data_root: Path) -> dict[str, Any]:
    background = scene.background
    if background.type == "color":
        return {"type": "color", "value": background.value}
    asset = _require(assets, background.asset_id or "", scene.scene_id, expected={"image", "video"})
    return {"type": background.type, "src": _src(data_root, asset)}


def _layer(raw: dict[str, Any], scene: Scene, assets: dict[str, Asset], data_root: Path) -> dict[str, Any]:
    duration = raw.get("duration")
    if duration is None:
        duration = scene.duration - raw["start"]
    layer_type = raw["type"]
    src = None
    svg = None
    if layer_type in {"image", "video", "svg"}:
        expected = {"image": "image", "video": "video", "svg": "svg"}[layer_type]
        asset = _require(assets, raw.get("asset_id") or "", scene.scene_id, expected={expected})
        if layer_type == "svg":
            svg = _read_svg(data_root / asset.blob_path)
        else:
            src = _src(data_root, asset)
    animation = raw.get("animation") or {"type": "ease_out", "duration": None, "easing": "ease_out"}
    if animation.get("easing") is None:
        animation["easing"] = "ease_out" if animation.get("type") not in {"linear", "ease_in", "ease_out", "ease_in_out", "spring"} else animation["type"]
    layer = {
        "id": raw["id"],
        "type": layer_type,
        "src": src,
        "svg": svg,
        "text": raw.get("content"),
        "start": raw["start"],
        "duration": duration,
        "zIndex": raw["z_index"],
        "position": _anim(raw.get("position"), {"x": 0.5, "y": 0.5}),
        "scale": _anim(raw.get("scale"), 1),
        "rotation": _anim(raw.get("rotation"), 0),
        "opacity": _anim(raw.get("opacity"), 1),
        "anchor": _anim(raw.get("anchor"), {"x": 0.5, "y": 0.5}),
        "crop": _anim(raw.get("crop"), None) if raw.get("crop") is not None else None,
        "fit": raw.get("fit") or ("cover" if layer_type == "video" else "contain"),
        "effects": _effects(raw.get("effects")),
        "animation": animation,
        "style": raw.get("style") or {},
        "shape": raw.get("shape"),
        "fill": raw.get("fill") or "#FFFFFF",
        "width": raw.get("width") or 0.4,
        "height": raw.get("height") or 0.2,
        "borderRadius": raw.get("border_radius") or 0,
        "gradient": raw.get("gradient"),
        "trimStart": raw.get("trim_start") or 0,
        "trimEnd": raw.get("trim_end"),
        "playbackRate": raw.get("playback_rate") or 1,
        "loop": bool(raw.get("loop")),
        "respectSafeArea": bool(raw.get("respect_safe_area", True)) if layer_type == "text" else False,
        "blendMode": raw.get("blend_mode") or "normal",
        "mask": _mask(raw.get("mask")),
    }
    if layer_type == "video" and isinstance(raw.get("playback_rate"), dict):
        from app.renderer.speed import resolve_playback

        asset = _require(assets, raw.get("asset_id") or "", scene.scene_id, expected={"video"})
        src, rate, trim_start = resolve_playback(
            data_root / asset.blob_path,
            raw["playback_rate"],
            trim_start=float(raw.get("trim_start") or 0),
            layer_duration=float(duration),
            cache_dir=data_root / "cache" / "speed",
        )
        layer["src"] = src
        layer["playbackRate"] = rate
        layer["trimStart"] = trim_start
        layer["trimEnd"] = None
    return layer


def _effects(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {}
    payload: dict[str, Any] = {}
    for key in ("blur", "brightness", "contrast", "saturation"):
        if raw.get(key) is not None:
            payload[key] = _anim(raw[key], 0)
    for key in ("grayscale", "drop_shadow", "motion_blur", "sepia", "vignette", "glow", "bloom", "grain", "color_tint"):
        if raw.get(key) is not None:
            payload[key] = raw[key]
    return payload


def _mask(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return {
        "shape": raw["shape"],
        "x": _anim(raw.get("x"), 0.5),
        "y": _anim(raw.get("y"), 0.5),
        "width": _anim(raw.get("width"), 0.5),
        "height": _anim(raw.get("height"), 0.5),
        "radius": _anim(raw.get("radius"), 0),
    }


def _anim(value: Any, default: Any) -> dict[str, Any]:
    if value is None:
        return {"mode": "static", "value": default}
    if isinstance(value, (int, float)):
        return {"mode": "static", "value": value}
    if isinstance(value, dict) and "keyframes" in value:
        return {"mode": "keyframes", "keyframes": value["keyframes"]}
    if isinstance(value, dict) and "from" in value and "to" in value:
        return {"mode": "from_to", "from": value["from"], "to": value["to"]}
    return {"mode": "static", "value": value}


def _require(assets: dict[str, Asset], asset_id: str, scene_id: str, *, expected: set[str]) -> Asset:
    from app.errors import MarketingError

    asset = assets.get(asset_id)
    if asset is None:
        raise MarketingError(
            "INVALID_ASSET_REFERENCE",
            f"Scene {scene_id} references asset {asset_id}, but that asset does not exist.",
            suggested_action=f"Register the asset before rendering {scene_id}.",
            scene_id=scene_id,
            asset_id=asset_id,
        )
    if asset.type not in expected:
        raise MarketingError(
            "UNSUPPORTED_FORMAT",
            f"Scene {scene_id} uses asset {asset_id} as {', '.join(sorted(expected))}, but it is {asset.type}.",
            suggested_action="Use an asset whose type matches the layer.",
            scene_id=scene_id,
            asset_id=asset_id,
            asset_type=asset.type,
        )
    return asset


def _src(data_root: Path, asset: Asset) -> str:
    return str((data_root / asset.blob_path).resolve())


def _read_svg(path: Path) -> str:
    from app.renderer.svg_sanitize import sanitize_svg

    return sanitize_svg(path.read_text(encoding="utf-8"))


def referenced_asset_ids(scene: Scene) -> list[str]:
    """Visual assets a scene draws, including the ones its cartoon block pulls in."""
    ids: list[str] = []
    if scene.background.asset_id:
        ids.append(scene.background.asset_id)
    for layer in scene.layers:
        if layer.asset_id:
            ids.append(layer.asset_id)
    ids.extend(cartoon_asset_ids(scene))
    seen: list[str] = []
    for asset_id in ids:
        if asset_id not in seen:
            seen.append(asset_id)
    return seen


def cartoon_asset_ids(scene: Scene) -> list[str]:
    """Assets named directly by the cartoon block. Character artwork resolves at compile time."""
    spec = scene.cartoon
    if spec is None:
        return []
    ids: list[str] = []
    if spec.background:
        for field_name in ("asset_id", "background", "midground", "foreground"):
            value = getattr(spec.background, field_name)
            if value:
                ids.append(value)
    ids.extend(prop.asset_id for prop in spec.props)
    for line in spec.dialogue:
        if line.style and line.style.bubble_asset_id:
            ids.append(line.style.bubble_asset_id)
    return ids


def scene_from_stored(payload: dict[str, Any]) -> Scene:
    return parse_scene(payload)
