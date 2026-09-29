"""Granular cartoon edits.

Every operation loads the scene, changes one part of its cartoon block, and saves it through
SceneService.update, so cartoon edits reuse the existing validation, scene order, duration
refresh, versioning, and cache behaviour.
"""

from __future__ import annotations

from typing import Any

from app.errors import MarketingError
from app.services.character_service import CharacterService
from app.services.scene_service import SceneService


class CartoonService:
    def __init__(self, scenes: SceneService, characters: CharacterService) -> None:
        self.scenes = scenes
        self.characters = characters
        self.projects = scenes.projects

    # Characters in a scene -------------------------------------------------

    def add_character_to_scene(self, project_id: str, scene_id: str, character: dict[str, Any]) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        character_id = self._require_id(character, "character_id", scene_id)
        self.characters.read(project_id, character_id)
        if any(item.get("character_id") == character_id for item in spec["characters"]):
            raise MarketingError(
                "DUPLICATE_CHARACTER",
                f"Character {character_id} is already in scene {scene_id}.",
                suggested_action="Call update_character_in_scene to change the existing placement.",
                scene_id=scene_id,
                character_id=character_id,
            )
        spec["characters"].append(dict(character))
        return self._save(project_id, scene_id, payload, spec)

    def update_character_in_scene(
        self, project_id: str, scene_id: str, character_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        entry = self._find(spec["characters"], "character_id", character_id, scene_id, "CHARACTER_NOT_IN_SCENE")
        entry.update(fields)
        entry["character_id"] = character_id
        return self._save(project_id, scene_id, payload, spec)

    def remove_character_from_scene(self, project_id: str, scene_id: str, character_id: str) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        self._find(spec["characters"], "character_id", character_id, scene_id, "CHARACTER_NOT_IN_SCENE")
        spec["characters"] = [item for item in spec["characters"] if item.get("character_id") != character_id]
        spec["dialogue"] = [item for item in spec["dialogue"] if item.get("character_id") != character_id]
        camera = spec.get("camera")
        if camera and camera.get("focus") == character_id:
            camera["focus"] = None
        return self._save(project_id, scene_id, payload, spec)

    # Dialogue --------------------------------------------------------------

    def create_dialogue(self, project_id: str, scene_id: str, dialogue: dict[str, Any]) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        dialogue_id = self._require_id(dialogue, "dialogue_id", scene_id)
        if any(item.get("dialogue_id") == dialogue_id for item in spec["dialogue"]):
            raise MarketingError(
                "DIALOGUE_EXISTS",
                f"Dialogue {dialogue_id} already exists in scene {scene_id}.",
                suggested_action="Call update_dialogue, or choose another dialogue_id.",
                scene_id=scene_id,
                dialogue_id=dialogue_id,
            )
        spec["dialogue"].append(dict(dialogue))
        return self._save(project_id, scene_id, payload, spec)

    def get_dialogue(self, project_id: str, scene_id: str, dialogue_id: str) -> dict[str, Any]:
        spec, _ = self._open(project_id, scene_id)
        return self._find(spec["dialogue"], "dialogue_id", dialogue_id, scene_id, "DIALOGUE_NOT_FOUND")

    def list_dialogue(self, project_id: str, scene_id: str) -> dict[str, Any]:
        spec, _ = self._open(project_id, scene_id)
        lines = sorted(spec["dialogue"], key=lambda item: float(item.get("start") or 0))
        return {"project_id": project_id, "scene_id": scene_id, "dialogue": lines}

    def update_dialogue(
        self, project_id: str, scene_id: str, dialogue_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        entry = self._find(spec["dialogue"], "dialogue_id", dialogue_id, scene_id, "DIALOGUE_NOT_FOUND")
        entry.update(fields)
        entry["dialogue_id"] = dialogue_id
        return self._save(project_id, scene_id, payload, spec)

    def delete_dialogue(self, project_id: str, scene_id: str, dialogue_id: str) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        self._find(spec["dialogue"], "dialogue_id", dialogue_id, scene_id, "DIALOGUE_NOT_FOUND")
        spec["dialogue"] = [item for item in spec["dialogue"] if item.get("dialogue_id") != dialogue_id]
        return self._save(project_id, scene_id, payload, spec)

    # Actions ---------------------------------------------------------------

    def add_character_action(
        self, project_id: str, scene_id: str, character_id: str, action: dict[str, Any]
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        entry = self._find(spec["characters"], "character_id", character_id, scene_id, "CHARACTER_NOT_IN_SCENE")
        actions = entry.setdefault("actions", [])
        item = dict(action)
        if not item.get("action_id"):
            item["action_id"] = _next_action_id(actions)
        elif any(existing.get("action_id") == item["action_id"] for existing in actions):
            raise MarketingError(
                "ACTION_EXISTS",
                f"Action {item['action_id']} already exists on {character_id} in {scene_id}.",
                suggested_action="Call update_character_action, or choose another action_id.",
                scene_id=scene_id,
                character_id=character_id,
            )
        actions.append(item)
        return self._save(project_id, scene_id, payload, spec)

    def update_character_action(
        self, project_id: str, scene_id: str, character_id: str, action_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        entry = self._find(spec["characters"], "character_id", character_id, scene_id, "CHARACTER_NOT_IN_SCENE")
        action = self._find(entry.get("actions", []), "action_id", action_id, scene_id, "ACTION_NOT_FOUND")
        action.update(fields)
        action["action_id"] = action_id
        return self._save(project_id, scene_id, payload, spec)

    def delete_character_action(
        self, project_id: str, scene_id: str, character_id: str, action_id: str
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        entry = self._find(spec["characters"], "character_id", character_id, scene_id, "CHARACTER_NOT_IN_SCENE")
        self._find(entry.get("actions", []), "action_id", action_id, scene_id, "ACTION_NOT_FOUND")
        entry["actions"] = [item for item in entry.get("actions", []) if item.get("action_id") != action_id]
        return self._save(project_id, scene_id, payload, spec)

    # Camera ----------------------------------------------------------------

    def set_scene_camera(self, project_id: str, scene_id: str, camera: dict[str, Any] | None) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        spec["camera"] = dict(camera) if camera else None
        return self._save(project_id, scene_id, payload, spec)

    # Props -----------------------------------------------------------------

    def add_prop_to_scene(self, project_id: str, scene_id: str, prop: dict[str, Any]) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        prop_id = self._require_id(prop, "prop_id", scene_id)
        if any(item.get("prop_id") == prop_id for item in spec["props"]):
            raise MarketingError(
                "PROP_EXISTS",
                f"Prop {prop_id} already exists in scene {scene_id}.",
                suggested_action="Call update_prop_in_scene, or choose another prop_id.",
                scene_id=scene_id,
                prop_id=prop_id,
            )
        spec["props"].append(dict(prop))
        return self._save(project_id, scene_id, payload, spec)

    def update_prop_in_scene(
        self, project_id: str, scene_id: str, prop_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        entry = self._find(spec["props"], "prop_id", prop_id, scene_id, "PROP_NOT_FOUND")
        entry.update(fields)
        entry["prop_id"] = prop_id
        return self._save(project_id, scene_id, payload, spec)

    def remove_prop_from_scene(self, project_id: str, scene_id: str, prop_id: str) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        self._find(spec["props"], "prop_id", prop_id, scene_id, "PROP_NOT_FOUND")
        spec["props"] = [item for item in spec["props"] if item.get("prop_id") != prop_id]
        return self._save(project_id, scene_id, payload, spec)

    # Background ------------------------------------------------------------

    def set_scene_background(
        self, project_id: str, scene_id: str, background: dict[str, Any] | None
    ) -> dict[str, Any]:
        spec, payload = self._open(project_id, scene_id)
        spec["background"] = dict(background) if background else None
        return self._save(project_id, scene_id, payload, spec)

    # Internals -------------------------------------------------------------

    def _open(self, project_id: str, scene_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        self.projects.require_cartoon(project_id)
        payload = self.scenes.get_model(project_id, scene_id).model_dump(mode="json")
        spec = payload.get("cartoon") or {}
        spec.setdefault("background", None)
        spec.setdefault("characters", [])
        spec.setdefault("dialogue", [])
        spec.setdefault("camera", None)
        spec.setdefault("props", [])
        return spec, payload

    def _save(
        self, project_id: str, scene_id: str, payload: dict[str, Any], spec: dict[str, Any]
    ) -> dict[str, Any]:
        payload["cartoon"] = spec
        return self.scenes.update(project_id, scene_id, payload)

    def _require_id(self, payload: dict[str, Any], field: str, scene_id: str) -> str:
        value = str(payload.get(field) or "").strip()
        if not value:
            raise MarketingError(
                "INVALID_CARTOON_SCENE",
                f"{field} is required.",
                suggested_action=f"Include {field} so later edits can address this entry.",
                scene_id=scene_id,
            )
        return value

    def _find(
        self, items: list[dict[str, Any]], field: str, value: str, scene_id: str, code: str
    ) -> dict[str, Any]:
        for item in items:
            if item.get(field) == value:
                return item
        known = [str(item.get(field)) for item in items]
        raise MarketingError(
            code,
            f"No entry with {field}='{value}' in scene {scene_id}.",
            suggested_action=f"Known values: {', '.join(known) if known else 'none'}.",
            scene_id=scene_id,
            **{field: value},
        )


def _next_action_id(actions: list[dict[str, Any]]) -> str:
    used = {item.get("action_id") for item in actions}
    index = len(actions) + 1
    while f"act_{index}" in used:
        index += 1
    return f"act_{index}"
