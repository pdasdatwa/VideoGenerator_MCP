"""Scene persistence and validation against the asset library."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.errors import MarketingError
from app.models.scene import AudioTrack, Scene
from app.renderer.cartoon.compile import compile_cartoon_scene
from app.renderer.cartoon.validator import validate_cartoon
from app.renderer.scene_graph import referenced_asset_ids
from app.renderer.timeline import build_timeline
from app.renderer.validator import parse_scene
from app.services.asset_service import AssetService
from app.services.character_service import CharacterService
from app.services.project_service import ProjectService
from app.storage.filesystem import read_json, write_json
from app.storage.paths import DataPaths


class SceneService:
    def __init__(
        self,
        settings: Settings,
        projects: ProjectService,
        assets: AssetService,
        characters: CharacterService,
    ) -> None:
        self.paths = DataPaths(settings.data_dir)
        self.projects = projects
        self.assets = assets
        self.characters = characters

    def create(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        project = self.projects.get(project_id)
        scene = self._validate(project_id, _writable_scene(payload))
        path = self.paths.scene_file(project_id, scene.scene_id)
        if path.exists():
            raise MarketingError(
                "SCENE_EXISTS",
                f"Scene {scene.scene_id} already exists.",
                suggested_action="Call update_scene to change it, or pick a new scene_id.",
                scene_id=scene.scene_id,
            )
        write_json(path, scene.model_dump(mode="json"))
        if scene.scene_id not in project.scene_order:
            project.scene_order.append(scene.scene_id)
        self._refresh_duration(project_id, project)
        return self._with_timeline(project_id, scene)

    def upsert(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        scene_id = str(payload.get("scene_id") or "")
        if scene_id and self.paths.scene_file(project_id, scene_id).exists():
            return self.update(project_id, scene_id, payload)
        return self.create(project_id, payload)

    def update(self, project_id: str, scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_model(project_id, scene_id)
        payload = _writable_scene(payload)
        payload["scene_id"] = scene_id
        scene = self._validate(project_id, payload)
        write_json(self.paths.scene_file(project_id, scene_id), scene.model_dump(mode="json"))
        project = self.projects.get(project_id)
        self._refresh_duration(project_id, project)
        return self._with_timeline(project_id, scene)

    def get_model(self, project_id: str, scene_id: str) -> Scene:
        self.projects.get(project_id)
        path = self.paths.scene_file(project_id, scene_id)
        if not path.exists():
            raise MarketingError(
                "SCENE_NOT_FOUND",
                f"Scene {scene_id} does not exist on project {project_id}.",
                suggested_action="Call list_scenes and use an id from that list.",
                project_id=project_id,
                scene_id=scene_id,
            )
        return Scene.model_validate(read_json(path))

    def get(self, project_id: str, scene_id: str) -> dict[str, Any]:
        return self._with_timeline(project_id, self.get_model(project_id, scene_id))

    def list_scenes(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        scenes = self.map_scenes(project_id)
        timeline = build_timeline(project.scene_order, scenes)
        return {
            "project_id": project_id,
            "duration": timeline.duration,
            "timeline": [entry.model_dump() for entry in timeline.entries],
            "scenes": [scenes[scene_id].model_dump(mode="json") for scene_id in project.scene_order if scene_id in scenes],
        }

    def map_scenes(self, project_id: str) -> dict[str, Scene]:
        folder = self.paths.scenes_dir(project_id)
        if not folder.exists():
            return {}
        scenes = [Scene.model_validate(read_json(path)) for path in folder.glob("*.json")]
        return {scene.scene_id: scene for scene in scenes}

    def delete(self, project_id: str, scene_id: str) -> dict[str, Any]:
        self.get_model(project_id, scene_id)
        self.paths.scene_file(project_id, scene_id).unlink()
        project = self.projects.get(project_id)
        project.scene_order = [item for item in project.scene_order if item != scene_id]
        self._refresh_duration(project_id, project)
        return {"deleted": scene_id}

    def validate_scene(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        scene = self._validate(project_id, payload)
        return {"valid": True, "scene_id": scene.scene_id}

    def validate_project(self, project_id: str) -> dict[str, Any]:
        project = self.projects.get(project_id)
        scenes = self.map_scenes(project_id)
        missing = [scene_id for scene_id in project.scene_order if scene_id not in scenes]
        if missing:
            raise MarketingError(
                "INVALID_SCENE",
                f"Project order references missing scenes: {', '.join(missing)}.",
                suggested_action="Remove those ids from scene_order or recreate the scenes.",
                scene_ids=missing,
            )
        assets = self.assets.map_assets(project_id)
        characters = self.characters.map_characters(project_id)
        for scene in scenes.values():
            self._check_assets(project_id, scene, assets)
            if scene.cartoon is not None:
                validate_cartoon(scene, project, assets, characters)
        for track in project.audio_tracks:
            AudioTrack.model_validate(track)
            self._check_audio(project_id, track["asset_id"], assets)
        timeline = build_timeline(project.scene_order, scenes)
        return {
            "valid": True,
            "project_id": project_id,
            "duration": timeline.duration,
            "scene_count": len(project.scene_order),
            "timeline": [entry.model_dump() for entry in timeline.entries],
        }

    def validate_cartoon_scene(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate a cartoon scene and prove it compiles into renderable layers."""
        project = self.projects.require_cartoon(project_id)
        scene = self._validate(project_id, payload)
        if scene.cartoon is None:
            raise MarketingError(
                "INVALID_CARTOON_SCENE",
                f"Scene {scene.scene_id} has no cartoon block.",
                suggested_action="Add a cartoon object with characters, dialogue, camera, or props, or call validate_scene instead.",
                scene_id=scene.scene_id,
            )
        compiled = compile_cartoon_scene(
            scene,
            project,
            self.assets.map_assets(project_id),
            self.characters.map_characters(project_id),
        )
        return {
            "valid": True,
            "scene_id": scene.scene_id,
            "characters": [item.character_id for item in scene.cartoon.characters],
            "dialogue": [item.dialogue_id for item in scene.cartoon.dialogue],
            "props": [item.prop_id for item in scene.cartoon.props],
            "compiled_layers": [layer.id for layer in compiled.scene.layers],
            "camera": compiled.camera,
            "warnings": compiled.warnings,
        }

    def _validate(self, project_id: str, payload: dict[str, Any]) -> Scene:
        scene = parse_scene(payload)
        assets = self.assets.map_assets(project_id)
        self._check_assets(project_id, scene, assets)
        if scene.cartoon is not None:
            validate_cartoon(
                scene,
                self.projects.get(project_id),
                assets,
                self.characters.map_characters(project_id),
            )
        return scene

    def _check_assets(self, project_id: str, scene: Scene, assets: dict) -> None:
        expected = {"image": "image", "video": "video", "svg": "svg"}
        if scene.background.asset_id:
            self._expect(assets, scene.background.asset_id, scene.scene_id, {scene.background.type})
        for layer in scene.layers:
            if layer.type in expected:
                self._expect(assets, layer.asset_id or "", scene.scene_id, {expected[layer.type]})
        for track in scene.audio:
            self._check_audio(project_id, track.asset_id, assets)
        referenced_asset_ids(scene)

    def _expect(self, assets: dict, asset_id: str, scene_id: str, types: set[str]) -> None:
        asset = assets.get(asset_id)
        if asset is None:
            raise MarketingError(
                "INVALID_ASSET_REFERENCE",
                f"Scene {scene_id} references asset {asset_id}, but that asset does not exist.",
                suggested_action=f"Register the asset before using it in {scene_id}.",
                scene_id=scene_id,
                asset_id=asset_id,
            )
        if asset.type not in types:
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                f"Asset {asset_id} is {asset.type}, which does not match this use.",
                suggested_action="Choose an asset of the required type.",
                scene_id=scene_id,
                asset_id=asset_id,
                asset_type=asset.type,
            )

    def _check_audio(self, project_id: str, asset_id: str, assets: dict) -> None:
        asset = assets.get(asset_id)
        if asset is None:
            raise MarketingError(
                "INVALID_ASSET_REFERENCE",
                f"Audio track references missing asset {asset_id}.",
                suggested_action="Register an audio file and use its asset_id.",
                project_id=project_id,
                asset_id=asset_id,
            )
        if asset.type != "audio":
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                f"Asset {asset_id} is not audio.",
                suggested_action="Point the audio track at an MP3, WAV, or AAC asset.",
                asset_id=asset_id,
            )

    def _refresh_duration(self, project_id: str, project) -> None:
        scenes = self.map_scenes(project_id)
        timeline = build_timeline(project.scene_order, scenes)
        project.duration = timeline.duration
        self.projects.save(project)

    def _with_timeline(self, project_id: str, scene: Scene) -> dict[str, Any]:
        project = self.projects.get(project_id)
        scenes = self.map_scenes(project_id)
        timeline = build_timeline(project.scene_order, scenes)
        payload = scene.model_dump(mode="json")
        for entry in timeline.entries:
            if entry.scene_id == scene.scene_id:
                payload["timeline_start"] = entry.start
                payload["timeline_end"] = entry.end
        return payload


def _writable_scene(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    cleaned.pop("timeline_start", None)
    cleaned.pop("timeline_end", None)
    return cleaned
