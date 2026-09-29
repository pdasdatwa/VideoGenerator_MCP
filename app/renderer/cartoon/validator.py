"""Cartoon scene validation. Errors name the field and the fix so a model can repair them."""

from __future__ import annotations

from typing import Any

from app.errors import MarketingError
from app.models.asset import Asset
from app.models.cartoon import Camera, CartoonSpec, Dialogue, Prop, SceneCharacter
from app.models.character import Character
from app.models.project import Project
from app.models.scene import Scene
from app.renderer.cartoon.names import (
    ACTIONS,
    ACTION_SPECS,
    CAMERA_MOVES,
    CAMERA_SHOTS,
    DIALOGUE_ANIMATIONS,
)
from app.renderer.cartoon.resolve import resolve_character_asset

_VISUAL_TYPES = {"image", "svg"}
COMPILED_PREFIXES = ("cbg_", "char_", "prop_", "dlg_")


def validate_cartoon(
    scene: Scene,
    project: Project,
    assets: dict[str, Asset],
    characters: dict[str, Character],
) -> None:
    spec = scene.cartoon
    if spec is None:
        return
    if project.mode != "cartoon":
        raise MarketingError(
            "CARTOON_MODE_REQUIRED",
            f"Scene {scene.scene_id} carries a cartoon block, but project {project.project_id} is mode='{project.mode}'.",
            suggested_action="Create the project with mode='cartoon', or remove the cartoon block from the scene.",
            project_id=project.project_id,
            scene_id=scene.scene_id,
            mode=project.mode,
        )
    _check_manual_layer_ids(scene)
    _check_background(scene, spec, assets)
    placed = _check_characters(scene, spec, assets, characters)
    _check_dialogue(scene, spec, placed, assets)
    _check_camera(scene, spec, placed)
    _check_props(scene, spec, assets)


def _fail(code: str, message: str, fix: str, scene: Scene, **details: Any) -> None:
    raise MarketingError(code, message, suggested_action=fix, scene_id=scene.scene_id, **details)


def _check_manual_layer_ids(scene: Scene) -> None:
    for layer in scene.layers:
        if layer.id.startswith(COMPILED_PREFIXES):
            _fail(
                "INVALID_CARTOON_SCENE",
                f"Layer id '{layer.id}' uses a reserved cartoon prefix.",
                f"Rename the layer. These prefixes belong to compiled cartoon layers: {', '.join(COMPILED_PREFIXES)}.",
                scene,
                layer_id=layer.id,
            )


def _require_visual(scene: Scene, assets: dict[str, Asset], asset_id: str, field: str, **details: Any) -> Asset:
    asset = assets.get(asset_id)
    if asset is None:
        _fail(
            "INVALID_ASSET_REFERENCE",
            f"{field} references asset {asset_id}, but that asset does not exist on this project.",
            "Call register_asset or register_character_asset first, then use the returned asset_id.",
            scene,
            asset_id=asset_id,
            **details,
        )
    if asset.type not in _VISUAL_TYPES:  # type: ignore[union-attr]
        _fail(
            "UNSUPPORTED_FORMAT",
            f"{field} uses asset {asset_id}, which is {asset.type}. Cartoon artwork must be image or svg.",  # type: ignore[union-attr]
            "Point the field at a PNG, WebP, JPEG, or SVG asset.",
            scene,
            asset_id=asset_id,
            asset_type=asset.type,  # type: ignore[union-attr]
            **details,
        )
    return asset  # type: ignore[return-value]


def _check_background(scene: Scene, spec: CartoonSpec, assets: dict[str, Asset]) -> None:
    background = spec.background
    if background is None:
        return
    for field in ("asset_id", "background", "midground", "foreground"):
        asset_id = getattr(background, field)
        if asset_id:
            _require_visual(scene, assets, asset_id, f"cartoon.background.{field}")
    if background.asset_id and background.background:
        _fail(
            "INVALID_CARTOON_SCENE",
            "cartoon.background sets both asset_id and a layered background plate.",
            "Use asset_id for a single plate, or background/midground/foreground for parallax. Not both.",
            scene,
        )


def _check_characters(
    scene: Scene,
    spec: CartoonSpec,
    assets: dict[str, Asset],
    characters: dict[str, Character],
) -> set[str]:
    seen: set[str] = set()
    for placement in spec.characters:
        character = characters.get(placement.character_id)
        if character is None:
            _fail(
                "CHARACTER_NOT_FOUND",
                f"Scene references character '{placement.character_id}', which does not exist on this project.",
                f"Call create_character first. Known characters: {', '.join(sorted(characters)) or 'none'}.",
                scene,
                character_id=placement.character_id,
            )
            continue
        if placement.character_id in seen:
            _fail(
                "DUPLICATE_CHARACTER",
                f"Character '{placement.character_id}' appears twice in scene {scene.scene_id}.",
                "Place each character once. Use actions to move them during the scene.",
                scene,
                character_id=placement.character_id,
            )
        seen.add(placement.character_id)
        _check_placement_assets(scene, placement, character, assets)
        _check_actions(scene, placement, characters)
    return seen


def _check_placement_assets(
    scene: Scene,
    placement: SceneCharacter,
    character: Character,
    assets: dict[str, Asset],
) -> None:
    if placement.pose and placement.pose not in character.assets.poses and not _variant(character, placement):
        _fail(
            "INVALID_POSE",
            f"Character '{character.character_id}' has no pose '{placement.pose}'.",
            f"Register it with register_character_asset(role='character_pose', key='{placement.pose}'). Known poses: {', '.join(sorted(character.assets.poses)) or 'none'}.",
            scene,
            character_id=character.character_id,
            pose=placement.pose,
        )
    if placement.expression and placement.expression not in character.assets.expressions and not _variant(character, placement):
        _fail(
            "INVALID_EXPRESSION",
            f"Character '{character.character_id}' has no expression '{placement.expression}'.",
            f"Register it with register_character_asset(role='character_expression', key='{placement.expression}'). Known expressions: {', '.join(sorted(character.assets.expressions)) or 'none'}.",
            scene,
            character_id=character.character_id,
            expression=placement.expression,
        )
    resolved = resolve_character_asset(character, placement.pose, placement.expression)
    if not resolved:
        _fail(
            "MISSING_CHARACTER_ASSET",
            f"Character '{character.character_id}' has no artwork to draw.",
            "Register at least a base asset with register_character_asset(role='character_base').",
            scene,
            character_id=character.character_id,
        )
        return
    _require_visual(scene, assets, resolved, f"character '{character.character_id}'", character_id=character.character_id)
    for accessory in placement.accessories:
        asset_id = character.assets.accessories.get(accessory)
        if not asset_id:
            _fail(
                "MISSING_CHARACTER_ASSET",
                f"Character '{character.character_id}' has no accessory '{accessory}'.",
                f"Register it with register_character_asset(role='character_accessory', key='{accessory}'). Known accessories: {', '.join(sorted(character.assets.accessories)) or 'none'}.",
                scene,
                character_id=character.character_id,
            )
            continue
        _require_visual(scene, assets, asset_id, f"accessory '{accessory}'", character_id=character.character_id)


def _variant(character: Character, placement: SceneCharacter) -> bool:
    if not (placement.pose and placement.expression):
        return False
    return f"{placement.pose}:{placement.expression}" in character.assets.variants


def _check_actions(scene: Scene, placement: SceneCharacter, characters: dict[str, Character]) -> None:
    ids: set[str] = set()
    for action in placement.actions:
        if action.type not in ACTIONS:
            _fail(
                "INVALID_ACTION",
                f"Action '{action.type}' is not implemented.",
                "Read rendering://cartoon-animation-primitives for the list this renderer supports.",
                scene,
                character_id=placement.character_id,
                action=action.type,
            )
        if action.action_id:
            if action.action_id in ids:
                _fail(
                    "INVALID_ACTION",
                    f"Duplicate action_id '{action.action_id}' on character '{placement.character_id}'.",
                    "Give every action on a character a unique action_id.",
                    scene,
                    character_id=placement.character_id,
                )
            ids.add(action.action_id)
        if action.start >= scene.duration:
            _fail(
                "INVALID_DURATION",
                f"Action '{action.type}' starts at {action.start}s, at or after the {scene.duration}s scene ends.",
                "Move the action earlier or lengthen the scene.",
                scene,
                character_id=placement.character_id,
                action=action.type,
            )
        if action.duration is not None and action.start + action.duration > scene.duration + 1e-6:
            _fail(
                "INVALID_DURATION",
                f"Action '{action.type}' runs to {round(action.start + action.duration, 3)}s, past the {scene.duration}s scene.",
                "Shorten the action, move it earlier, or lengthen the scene.",
                scene,
                character_id=placement.character_id,
                action=action.type,
            )
        allowed = set(ACTION_SPECS[action.type]["parameters"])  # type: ignore[arg-type]
        for field in ("direction", "distance", "repeat", "target", "to"):
            if getattr(action, field) is not None and field not in allowed:
                _fail(
                    "INVALID_ACTION_PARAMETER",
                    f"Action '{action.type}' does not use '{field}'.",
                    f"Supported parameters: start, duration, {', '.join(sorted(allowed))}.",
                    scene,
                    character_id=placement.character_id,
                    action=action.type,
                    parameter=field,
                )
        if action.type == "expression_change":
            character = characters.get(placement.character_id)
            if not action.to:
                _fail(
                    "INVALID_ACTION_PARAMETER",
                    "expression_change needs 'to' set to another registered expression.",
                    "Pass to='angry', for example.",
                    scene,
                    character_id=placement.character_id,
                    action=action.type,
                )
            elif character is not None and action.to not in character.assets.expressions:
                _fail(
                    "INVALID_EXPRESSION",
                    f"Character '{placement.character_id}' has no expression '{action.to}' to change into.",
                    f"Known expressions: {', '.join(sorted(character.assets.expressions)) or 'none'}.",
                    scene,
                    character_id=placement.character_id,
                    expression=action.to,
                )
        if isinstance(action.target, str) and action.target not in {item.character_id for item in scene.cartoon.characters}:  # type: ignore[union-attr]
            _fail(
                "INVALID_ACTION_PARAMETER",
                f"Action '{action.type}' targets character '{action.target}', who is not in this scene.",
                "Target a character placed in the same scene, or pass a point such as {'x': 0.2, 'y': 0.6}.",
                scene,
                character_id=placement.character_id,
                action=action.type,
            )


def _check_dialogue(scene: Scene, spec: CartoonSpec, placed: set[str], assets: dict[str, Asset]) -> None:
    seen: set[str] = set()
    for line in spec.dialogue:
        if line.dialogue_id in seen:
            _fail(
                "INVALID_DIALOGUE",
                f"Duplicate dialogue_id '{line.dialogue_id}' in scene {scene.scene_id}.",
                "Give every line a unique dialogue_id so it stays addressable.",
                scene,
                dialogue_id=line.dialogue_id,
            )
        seen.add(line.dialogue_id)
        if line.character_id is not None and line.character_id not in placed:
            _fail(
                "INVALID_DIALOGUE",
                f"Dialogue '{line.dialogue_id}' is spoken by '{line.character_id}', who is not in this scene.",
                f"Add the character with add_character_to_scene, or omit character_id for a narrator caption. Placed: {', '.join(sorted(placed)) or 'none'}.",
                scene,
                dialogue_id=line.dialogue_id,
                character_id=line.character_id,
            )
        if line.start + line.duration > scene.duration + 1e-6:
            _fail(
                "INVALID_DURATION",
                f"Dialogue '{line.dialogue_id}' runs to {round(line.start + line.duration, 3)}s, past the {scene.duration}s scene.",
                "Shorten the line, move it earlier, or lengthen the scene.",
                scene,
                dialogue_id=line.dialogue_id,
            )
        if line.animation and line.animation not in DIALOGUE_ANIMATIONS:
            _fail(
                "INVALID_ANIMATION",
                f"Dialogue animation '{line.animation}' is not supported.",
                f"Use one of: {', '.join(DIALOGUE_ANIMATIONS)}.",
                scene,
                dialogue_id=line.dialogue_id,
                animation=line.animation,
            )
        if line.style and line.style.bubble_asset_id:
            _require_visual(
                scene,
                assets,
                line.style.bubble_asset_id,
                f"dialogue '{line.dialogue_id}' bubble",
                dialogue_id=line.dialogue_id,
            )


def _check_camera(scene: Scene, spec: CartoonSpec, placed: set[str]) -> None:
    camera = spec.camera
    if camera is None:
        return
    if camera.shot and camera.shot not in CAMERA_SHOTS:
        _fail(
            "INVALID_CAMERA",
            f"Camera shot '{camera.shot}' is not a preset.",
            f"Use one of: {', '.join(CAMERA_SHOTS)}.",
            scene,
            shot=camera.shot,
        )
    if camera.focus and camera.focus not in placed:
        _fail(
            "INVALID_CAMERA",
            f"Camera focuses on '{camera.focus}', who is not in this scene.",
            f"Focus a placed character, or set camera.position instead. Placed: {', '.join(sorted(placed)) or 'none'}.",
            scene,
            character_id=camera.focus,
        )
    if camera.animation:
        if camera.animation.type not in CAMERA_MOVES:
            _fail(
                "INVALID_CAMERA",
                f"Camera animation '{camera.animation.type}' is not supported.",
                f"Use one of: {', '.join(CAMERA_MOVES)}.",
                scene,
                animation=camera.animation.type,
            )
        if camera.animation.start >= scene.duration:
            _fail(
                "INVALID_DURATION",
                f"Camera animation starts at {camera.animation.start}s, at or after the {scene.duration}s scene ends.",
                "Move the camera move earlier or lengthen the scene.",
                scene,
            )
    last = -1.0
    for frame in camera.keyframes:
        if frame.time < last:
            _fail(
                "INVALID_CAMERA",
                "Camera keyframes are out of order.",
                "Sort keyframes by ascending time.",
                scene,
            )
        if frame.time > scene.duration + 1e-6:
            _fail(
                "INVALID_DURATION",
                f"Camera keyframe at {frame.time}s is past the {scene.duration}s scene.",
                "Keep keyframe times inside the scene duration.",
                scene,
            )
        last = frame.time


def _check_props(scene: Scene, spec: CartoonSpec, assets: dict[str, Asset]) -> None:
    seen: set[str] = set()
    for prop in spec.props:
        if prop.prop_id in seen:
            _fail(
                "INVALID_PROP",
                f"Duplicate prop_id '{prop.prop_id}' in scene {scene.scene_id}.",
                "Give every prop a unique prop_id.",
                scene,
                prop_id=prop.prop_id,
            )
        seen.add(prop.prop_id)
        _require_visual(scene, assets, prop.asset_id, f"prop '{prop.prop_id}'", prop_id=prop.prop_id)
        if prop.animation and prop.animation.type not in ACTIONS:
            _fail(
                "INVALID_ACTION",
                f"Prop animation '{prop.animation.type}' is not implemented.",
                "Read rendering://cartoon-animation-primitives for the supported list.",
                scene,
                prop_id=prop.prop_id,
                action=prop.animation.type,
            )
        if prop.start >= scene.duration:
            _fail(
                "INVALID_DURATION",
                f"Prop '{prop.prop_id}' starts at {prop.start}s, at or after the {scene.duration}s scene ends.",
                "Move the prop earlier or lengthen the scene.",
                scene,
                prop_id=prop.prop_id,
            )


__all__ = ["validate_cartoon", "COMPILED_PREFIXES"]
