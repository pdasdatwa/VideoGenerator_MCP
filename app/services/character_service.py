"""Characters: stored identity plus asset wiring. Cartoon mode only.

The client LLM produces the artwork. This service registers it through the ordinary asset
registry, remembers which file plays which pose or expression, and resolves a
(pose, expression) pair back to one asset_id at compile time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.errors import MarketingError
from app.ids import validate_client_id
from app.models.character import Character, CharacterAssets
from app.renderer.cartoon.names import ASSET_ROLES, CHARACTER_PARTS
from app.renderer.cartoon.resolve import referenced_character_assets, resolve_character_asset
from app.services.asset_service import AssetService
from app.services.project_service import ProjectService
from app.storage.filesystem import read_json, write_json
from app.storage.paths import DataPaths

_KEYED_ROLES = {
    "character_pose": "poses",
    "character_expression": "expressions",
    "character_part": "parts",
    "character_accessory": "accessories",
}
_VISUAL_TYPES = {"image", "svg"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CharacterService:
    def __init__(self, settings: Settings, projects: ProjectService, assets: AssetService) -> None:
        self.paths = DataPaths(settings.data_dir)
        self.projects = projects
        self.assets = assets

    def create(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.projects.require_cartoon(project_id)
        character_id = str(payload.get("character_id") or "").strip()
        if not character_id:
            raise MarketingError(
                "INVALID_CHARACTER",
                "character_id is required.",
                suggested_action="Pass a short stable id such as 'raj'. You will reuse it in every scene.",
                project_id=project_id,
            )
        validate_client_id(character_id, field="character_id")
        if self.paths.character_file(project_id, character_id).exists():
            raise MarketingError(
                "CHARACTER_EXISTS",
                f"Character {character_id} already exists.",
                suggested_action="Call update_character to change it, or pick another character_id.",
                project_id=project_id,
                character_id=character_id,
            )
        now = _now()
        character = self._parse(
            {
                **payload,
                "character_id": character_id,
                "project_id": project_id,
                "name": payload.get("name") or character_id,
                "created_at": now,
                "updated_at": now,
            },
            character_id,
        )
        self._check_assets(project_id, character)
        self._save(character)
        return character.model_dump(mode="json")

    def get(self, project_id: str, character_id: str) -> Character:
        self.projects.require_cartoon(project_id)
        return self.read(project_id, character_id)

    def read(self, project_id: str, character_id: str) -> Character:
        """Load without the mode check. Used by validation and the compiler."""
        path = self.paths.character_file(project_id, character_id)
        if not path.exists():
            raise MarketingError(
                "CHARACTER_NOT_FOUND",
                f"Character {character_id} does not exist on project {project_id}.",
                suggested_action="Call list_characters and use an id from that list, or create_character first.",
                project_id=project_id,
                character_id=character_id,
            )
        return Character.model_validate(read_json(path))

    def get_dict(self, project_id: str, character_id: str) -> dict[str, Any]:
        return self.get(project_id, character_id).model_dump(mode="json")

    def list_characters(self, project_id: str) -> dict[str, Any]:
        self.projects.require_cartoon(project_id)
        characters = self.map_characters(project_id)
        return {
            "project_id": project_id,
            "characters": [characters[key].model_dump(mode="json") for key in sorted(characters)],
        }

    def map_characters(self, project_id: str) -> dict[str, Character]:
        folder = self.paths.characters_dir(project_id)
        if not folder.exists():
            return {}
        records = [Character.model_validate(read_json(path)) for path in folder.glob("*.json")]
        return {record.character_id: record for record in records}

    def update(self, project_id: str, character_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.projects.require_cartoon(project_id)
        character = self.read(project_id, character_id)
        allowed = {
            "name",
            "description",
            "traits",
            "visual_style",
            "default_position",
            "default_scale",
            "default_size",
            "default_anchor",
            "assets",
            "metadata",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise MarketingError(
                "INVALID_CHARACTER",
                f"Cannot update {', '.join(sorted(unknown))}.",
                suggested_action=f"Update only: {', '.join(sorted(allowed))}.",
                project_id=project_id,
                character_id=character_id,
            )
        data = character.model_dump()
        data.update(fields)
        data["updated_at"] = _now()
        updated = self._parse(data, character_id)
        self._check_assets(project_id, updated)
        self._save(updated)
        return updated.model_dump(mode="json")

    def delete(self, project_id: str, character_id: str, referenced_by: list[str]) -> dict[str, Any]:
        self.projects.require_cartoon(project_id)
        self.read(project_id, character_id)
        if referenced_by:
            raise MarketingError(
                "CHARACTER_IN_USE",
                f"Character {character_id} is used by {', '.join(referenced_by)}.",
                suggested_action="Call remove_character_from_scene on those scenes, then delete the character.",
                project_id=project_id,
                character_id=character_id,
                scene_ids=referenced_by,
            )
        self.paths.character_file(project_id, character_id).unlink()
        return {"deleted": character_id}

    def register_asset(
        self,
        project_id: str,
        character_id: str,
        path: str,
        *,
        role: str,
        key: str | None = None,
        asset_id: str | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Register a file through the ordinary asset registry and wire it into the character."""
        self.projects.require_cartoon(project_id)
        character = self.read(project_id, character_id)
        if role not in ASSET_ROLES:
            raise MarketingError(
                "INVALID_METADATA",
                f"role '{role}' is not a known asset role.",
                suggested_action=f"Use one of: {', '.join(ASSET_ROLES)}.",
                character_id=character_id,
            )
        if role == "character_base":
            slot, name = "base", None
        elif role in _KEYED_ROLES:
            if not key:
                raise MarketingError(
                    "INVALID_METADATA",
                    f"role '{role}' needs a key.",
                    suggested_action="Pass key='angry' for an expression, key='sitting' for a pose, or key='standing:angry' for a combined variant.",
                    character_id=character_id,
                )
            slot, name = _KEYED_ROLES[role], key
        else:
            raise MarketingError(
                "INVALID_METADATA",
                f"role '{role}' does not belong to a character.",
                suggested_action="Use character_base, character_pose, character_expression, character_part, or character_accessory. Register backgrounds and props with register_asset.",
                character_id=character_id,
            )
        if name and ":" in name:
            slot = "variants"
        registered = self.assets.register(
            project_id,
            path,
            asset_id=asset_id,
            replace=replace,
            semantic_type=role,
            character_id=character_id,
        )
        stored_id = registered["id"]
        asset = self.assets.get(project_id, stored_id)
        if asset.type not in _VISUAL_TYPES:
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                f"Character assets must be image or svg. Asset {stored_id} is {asset.type}.",
                suggested_action="Register a PNG, WebP, JPEG, or SVG for the character.",
                character_id=character_id,
                asset_id=stored_id,
                asset_type=asset.type,
            )
        assets = character.assets.model_dump()
        if slot == "base":
            assets["base"] = stored_id
        else:
            assets[slot] = {**assets[slot], str(name): stored_id}
        character.assets = CharacterAssets.model_validate(assets)
        character.updated_at = _now()
        self._save(character)
        warnings = []
        if role == "character_part" and name not in CHARACTER_PARTS:
            warnings.append(
                f"Part '{name}' is stored but no primitive animates it. Animated parts are: {', '.join(CHARACTER_PARTS)}."
            )
        return {
            "character_id": character_id,
            "role": role,
            "key": name,
            "slot": slot,
            "asset": registered,
            "assets": character.assets.model_dump(mode="json"),
            "warnings": warnings,
        }

    def get_assets(self, project_id: str, character_id: str) -> dict[str, Any]:
        self.projects.require_cartoon(project_id)
        character = self.read(project_id, character_id)
        library = self.assets.map_assets(project_id)
        referenced = sorted(set(referenced_character_assets(character)))
        return {
            "character_id": character_id,
            "assets": character.assets.model_dump(mode="json"),
            "resolution_order": [
                "assets.variants['<pose>:<expression>']",
                "assets.expressions['<expression>']",
                "assets.poses['<pose>']",
                "assets.base",
            ],
            "poses": sorted(character.assets.poses),
            "expressions": sorted(character.assets.expressions),
            "variants": sorted(character.assets.variants),
            "parts": sorted(character.assets.parts),
            "records": [self.assets.public(library[asset_id]) for asset_id in referenced if asset_id in library],
            "missing": [asset_id for asset_id in referenced if asset_id not in library],
        }

    def _parse(self, data: dict[str, Any], character_id: str) -> Character:
        try:
            return Character.model_validate(data)
        except ValidationError as exc:
            raise MarketingError(
                "INVALID_CHARACTER",
                "Character failed schema validation.",
                suggested_action="Compare the payload with rendering://character-schema and fix the listed fields.",
                character_id=character_id,
                details=[{"loc": [str(part) for part in error["loc"]], "msg": error["msg"]} for error in exc.errors()],
            ) from exc

    def _check_assets(self, project_id: str, character: Character) -> None:
        library = self.assets.map_assets(project_id)
        for asset_id in referenced_character_assets(character):
            asset = library.get(asset_id)
            if asset is None:
                raise MarketingError(
                    "INVALID_ASSET_REFERENCE",
                    f"Character {character.character_id} references asset {asset_id}, but that asset does not exist.",
                    suggested_action="Call register_character_asset, or register the file first and reuse its asset_id.",
                    character_id=character.character_id,
                    asset_id=asset_id,
                )
            if asset.type not in _VISUAL_TYPES:
                raise MarketingError(
                    "UNSUPPORTED_FORMAT",
                    f"Character asset {asset_id} is {asset.type}. Characters are drawn from image or svg assets.",
                    suggested_action="Point the slot at a PNG, WebP, JPEG, or SVG asset.",
                    character_id=character.character_id,
                    asset_id=asset_id,
                    asset_type=asset.type,
                )

    def _save(self, character: Character) -> None:
        self.paths.ensure_project(character.project_id)
        write_json(
            self.paths.character_file(character.project_id, character.character_id),
            character.model_dump(mode="json"),
        )


__all__ = ["CharacterService", "referenced_character_assets", "resolve_character_asset"]
