"""Wire services once per process."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.logsetup import configure_logging
from app.services.asset_service import AssetService
from app.services.cache_service import CacheService
from app.services.cartoon_service import CartoonService
from app.services.character_service import CharacterService
from app.services.dependency_service import DependencyService
from app.services.project_service import ProjectService
from app.services.render_service import RenderService
from app.services.scene_service import SceneService
from app.services.version_service import VersionService
from app.storage.paths import DataPaths


@dataclass
class AppContext:
    settings: Settings
    projects: ProjectService
    assets: AssetService
    characters: CharacterService
    scenes: SceneService
    cartoon: CartoonService
    dependencies: DependencyService
    cache: CacheService
    versions: VersionService
    renders: RenderService

    def asset_users(self, project_id: str, asset_id: str) -> list[str]:
        scenes = self.scenes.map_scenes(project_id)
        users = list(self.dependencies.scenes_for_asset(scenes, asset_id))
        characters = self.characters.map_characters(project_id)
        for scene_id in self.dependencies.scenes_for_character_asset(scenes, characters, asset_id):
            if scene_id not in users:
                users.append(scene_id)
        return users

    def character_users(self, project_id: str, character_id: str) -> list[str]:
        return self.dependencies.scenes_for_character(self.scenes.map_scenes(project_id), character_id)


def build_context(settings: Settings | None = None, renderer: Any | None = None) -> AppContext:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.log_level)
    DataPaths(settings.data_dir).ensure()
    projects = ProjectService(settings)
    assets = AssetService(settings, projects)
    characters = CharacterService(settings, projects, assets)
    scenes = SceneService(settings, projects, assets, characters)
    cartoon = CartoonService(scenes, characters)
    cache = CacheService(DataPaths(settings.data_dir))
    versions = VersionService(settings, projects, scenes, characters)
    renders = RenderService(settings, projects, assets, scenes, cache, characters, renderer=renderer)
    return AppContext(
        settings=settings,
        projects=projects,
        assets=assets,
        characters=characters,
        scenes=scenes,
        cartoon=cartoon,
        dependencies=DependencyService(),
        cache=cache,
        versions=versions,
        renders=renders,
    )


_CONTEXT: AppContext | None = None


def get_context() -> AppContext:
    global _CONTEXT
    if _CONTEXT is None:
        _CONTEXT = build_context()
    return _CONTEXT
