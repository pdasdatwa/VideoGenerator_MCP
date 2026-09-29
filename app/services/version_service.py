"""Explicit project snapshots. Restore never deletes later versions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.errors import MarketingError
from app.ids import new_id
from app.models.version import ProjectVersion
from app.services.character_service import CharacterService
from app.services.project_service import ProjectService
from app.services.scene_service import SceneService
from app.storage.filesystem import read_json, write_json
from app.storage.paths import DataPaths


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VersionService:
    def __init__(
        self,
        settings: Settings,
        projects: ProjectService,
        scenes: SceneService,
        characters: CharacterService,
    ) -> None:
        self.paths = DataPaths(settings.data_dir)
        self.projects = projects
        self.scenes = scenes
        self.characters = characters

    def create(self, project_id: str, *, label: str | None = None, note: str | None = None) -> dict[str, Any]:
        project = self.projects.get(project_id)
        stored = self._all(project_id)
        version = ProjectVersion(
            version_id=new_id("ver"),
            project_id=project_id,
            number=len(stored) + 1,
            label=label,
            note=note,
            created_at=_now(),
            scene_order=list(project.scene_order),
            project=project.model_dump(mode="json"),
            scenes={
                scene_id: scene.model_dump(mode="json")
                for scene_id, scene in self.scenes.map_scenes(project_id).items()
            },
            characters={
                character_id: character.model_dump(mode="json")
                for character_id, character in self.characters.map_characters(project_id).items()
            },
        )
        write_json(self.paths.version_file(project_id, version.version_id), version.model_dump(mode="json"))
        project.current_version = version.version_id
        self.projects.save(project)
        return self._summary(version)

    def list_versions(self, project_id: str) -> list[dict[str, Any]]:
        self.projects.get(project_id)
        return [self._summary(version) for version in self._all(project_id)]

    def get(self, project_id: str, version_id: str) -> dict[str, Any]:
        version = self._load(project_id, version_id)
        return version.model_dump(mode="json")

    def restore(self, project_id: str, version_id: str) -> dict[str, Any]:
        source = self._load(project_id, version_id)
        project = self.projects.get(project_id)
        folder = self.paths.scenes_dir(project_id)
        if folder.exists():
            for path in folder.glob("*.json"):
                path.unlink()
        for scene_id, payload in source.scenes.items():
            write_json(self.paths.scene_file(project_id, scene_id), payload)
        characters_dir = self.paths.characters_dir(project_id)
        if characters_dir.exists():
            for path in characters_dir.glob("*.json"):
                path.unlink()
        for character_id, payload in source.characters.items():
            write_json(self.paths.character_file(project_id, character_id), payload)
        restored = dict(source.project)
        restored["project_id"] = project.project_id
        restored["created_at"] = project.created_at
        restored["scene_order"] = list(source.scene_order)
        restored["current_version"] = project.current_version
        from app.models.project import Project

        self.projects.save(Project.model_validate(restored))
        created = self.create(
            project_id,
            label=f"restore-{source.number}",
            note=f"Restored from version {source.number} ({source.version_id}). Previous versions were kept.",
        )
        stored = self._load(project_id, created["version_id"])
        stored.restored_from = source.version_id
        write_json(self.paths.version_file(project_id, stored.version_id), stored.model_dump(mode="json"))
        return {
            "restored_from": source.version_id,
            "new_version": self._summary(stored),
            "kept_versions": [item.version_id for item in self._all(project_id)],
        }

    def _all(self, project_id: str) -> list[ProjectVersion]:
        folder = self.paths.versions_dir(project_id)
        if not folder.exists():
            return []
        versions = [ProjectVersion.model_validate(read_json(path)) for path in folder.glob("*.json")]
        return sorted(versions, key=lambda item: item.number)

    def _load(self, project_id: str, version_id: str) -> ProjectVersion:
        self.projects.get(project_id)
        path = self.paths.version_file(project_id, version_id)
        if not path.exists():
            raise MarketingError(
                "VERSION_NOT_FOUND",
                f"Version {version_id} does not exist.",
                suggested_action="Call list_versions and pass a version_id from that list.",
                project_id=project_id,
                version_id=version_id,
            )
        return ProjectVersion.model_validate(read_json(path))

    def _summary(self, version: ProjectVersion) -> dict[str, Any]:
        return {
            "version_id": version.version_id,
            "project_id": version.project_id,
            "number": version.number,
            "label": version.label,
            "note": version.note,
            "created_at": version.created_at,
            "restored_from": version.restored_from,
            "scene_order": version.scene_order,
        }
