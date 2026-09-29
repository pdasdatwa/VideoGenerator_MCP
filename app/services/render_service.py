"""Render jobs: cache lookup, Remotion for misses, FFmpeg for assembly."""

from __future__ import annotations

import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings
from app.errors import MarketingError
from app.ids import new_id
from app.logsetup import get_logger
from app.models.project import Project
from app.models.render import RenderJob, RenderReport
from app.models.scene import AudioTrack, Scene
from app.renderer.assembly import mix_audio, stitch_scenes
from app.renderer.cartoon.compile import compile_cartoon_scene
from app.renderer.scene_graph import build_scene_props
from app.renderer.version import RENDERER_VERSION
from app.services.asset_service import AssetService
from app.services.cache_service import CacheService
from app.services.character_service import CharacterService
from app.services.project_service import ProjectService
from app.services.scene_service import SceneService
from app.storage.filesystem import delete_tree, read_json, write_json
from app.storage.paths import DataPaths

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RenderService:
    def __init__(
        self,
        settings: Settings,
        projects: ProjectService,
        assets: AssetService,
        scenes: SceneService,
        cache: CacheService,
        characters: CharacterService,
        renderer: Any | None = None,
    ) -> None:
        self.settings = settings
        self.projects = projects
        self.assets = assets
        self.scenes = scenes
        self.cache = cache
        self.characters = characters
        self.paths = DataPaths(settings.data_dir)
        self.renderer = renderer
        self._lock = threading.Lock()

    def render_preview(self, project_id: str, *, wait: bool = False) -> dict[str, Any]:
        return self._start(project_id, "preview", wait=wait)

    def render_project(self, project_id: str, *, wait: bool = False) -> dict[str, Any]:
        return self._start(project_id, "final", wait=wait)

    def render_scene(self, project_id: str, scene_id: str, *, profile: str = "preview", wait: bool = False) -> dict[str, Any]:
        return self._start(project_id, "scene", scene_id=scene_id, profile=profile, wait=wait)

    def get_status(self, job_id: str) -> dict[str, Any]:
        return self._read(job_id).model_dump(mode="json")

    def get_render(self, job_id: str) -> dict[str, Any]:
        job = self._read(job_id)
        payload = job.model_dump(mode="json")
        if job.output_path and Path(job.output_path).exists():
            payload["file_size"] = Path(job.output_path).stat().st_size
            payload["playable_check"] = "Run ffprobe on output_path to confirm. This record means the encoder finished."
        return payload

    def _start(
        self,
        project_id: str,
        kind: str,
        *,
        scene_id: str | None = None,
        profile: str | None = None,
        wait: bool = False,
    ) -> dict[str, Any]:
        chosen = profile or ("preview" if kind == "preview" else "final")
        job = RenderJob(
            job_id=new_id("job"),
            project_id=project_id,
            type=kind,  # type: ignore[arg-type]
            created_at=_now(),
            scene_id=scene_id,
            profile=chosen,
        )
        self._write(job)
        if wait:
            self._execute(job.job_id)
            return self.get_render(job.job_id)
        thread = threading.Thread(target=self._execute, args=(job.job_id,), daemon=True)
        thread.start()
        return self.get_status(job.job_id)

    def _execute(self, job_id: str) -> None:
        with self._lock:
            job = self._read(job_id)
            if job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = _now()
            self._write(job)
            temp = self.paths.temp_dir(job_id)
            temp.mkdir(parents=True, exist_ok=True)
            try:
                report = self._render_locked(job, temp)
                job.status = "completed"
                job.progress = 1
                job.completed_at = _now()
                job.report = report
                job.output_path = report.output_path
                job.current_scene = None
                job.error = None
            except MarketingError as exc:
                job.status = "failed"
                job.completed_at = _now()
                job.error = exc.to_dict()
                logger.exception(
                    "render failed",
                    extra={"job_id": job_id, "project_id": job.project_id, "render_error": exc.code},
                )
            except Exception as exc:  # noqa: BLE001 - persist unexpected failures on the job
                job.status = "failed"
                job.completed_at = _now()
                job.error = {
                    "error": "RENDER_FAILURE",
                    "message": str(exc),
                    "suggested_action": "Read the server log for the traceback and retry the render.",
                }
                logger.exception(
                    "render failed",
                    extra={"job_id": job_id, "project_id": job.project_id, "render_error": "RENDER_FAILURE"},
                )
            finally:
                delete_tree(temp)
                self._write(job)

    def _render_locked(self, job: RenderJob, temp: Path) -> RenderReport:
        self.scenes.validate_project(job.project_id)
        project = self.projects.get(job.project_id)
        scenes = self.scenes.map_scenes(job.project_id)
        assets = self.assets.map_assets(job.project_id)
        characters = self.characters.map_characters(job.project_id)
        ordered = [scenes[scene_id] for scene_id in project.scene_order]
        if job.type == "scene":
            if job.scene_id not in scenes:
                raise MarketingError(
                    "SCENE_NOT_FOUND",
                    f"Scene {job.scene_id} does not exist.",
                    suggested_action="Call list_scenes first.",
                    scene_id=job.scene_id,
                )
            ordered = [scenes[job.scene_id]]
        width, height, crf = _profile(project, job.profile, self.settings.preview_long_edge, self.settings.preview_crf, self.settings.final_crf)
        rendered: list[str] = []
        cached: list[str] = []
        warnings: list[str] = []
        files: list[tuple[Scene, Path]] = []
        for index, scene in enumerate(ordered):
            job.current_scene = scene.scene_id
            job.progress = index / max(len(ordered), 1)
            self._write(job)
            # Compile once: the same result keys the cache and, on a miss, feeds the renderer.
            compiled = compile_cartoon_scene(scene, project, assets, characters)
            warnings.extend(f"{scene.scene_id}: {note}" for note in compiled.warnings)
            key = self.cache.key(
                project,
                scene,
                assets,
                profile=job.profile,
                width=width,
                height=height,
                crf=crf,
                compiled=compiled,
            )
            destination = self.cache.path_for(project.project_id, key)
            if self.cache.has(project.project_id, key):
                cached.append(scene.scene_id)
                logger.info(
                    "scene cache hit",
                    extra={"project_id": project.project_id, "scene_id": scene.scene_id, "job_id": job.job_id, "cache_hit": True},
                )
            else:
                props = build_scene_props(
                    project,
                    scene,
                    assets,
                    width=width,
                    height=height,
                    renderer_version=RENDERER_VERSION,
                    crf=crf,
                    data_root=self.paths.root,
                    compiled=compiled,
                )
                started = datetime.now(timezone.utc)
                self._renderer().render_scene(props, destination)
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                rendered.append(scene.scene_id)
                logger.info(
                    "scene cache miss",
                    extra={
                        "project_id": project.project_id,
                        "scene_id": scene.scene_id,
                        "job_id": job.job_id,
                        "cache_miss": True,
                        "render_duration": elapsed,
                    },
                )
            self.cache.remember(project.project_id, scene.scene_id, key)
            files.append((scene, destination))
        output = self.paths.render_output(project.project_id, job.job_id)
        if job.type == "scene":
            shutil.copyfile(files[0][1], output)
        else:
            stitched = temp / "stitched.mp4"
            stitch_scenes(files, stitched, fps=project.fps)
            tracks = _audio_tracks(project, scenes, assets, self.paths.root)
            mix_audio(stitched, tracks, output, duration=project.duration or sum(scene.duration for scene in ordered))
        total = len(ordered)
        hits = len(cached) / total if total else 1
        return RenderReport(
            rendered=rendered,
            cached=cached,
            cache_hit_rate=round(hits, 4),
            output_path=str(output.resolve()),
            profile=job.profile,
            warnings=_dedupe(warnings),
        )

    def _renderer(self):
        if self.renderer is None:
            from app.renderer.remotion_adapter import RemotionAdapter

            self.renderer = RemotionAdapter(self.settings)
        return self.renderer

    def _write(self, job: RenderJob) -> None:
        write_json(self.paths.job_file(job.job_id), job.model_dump(mode="json"))

    def _read(self, job_id: str) -> RenderJob:
        path = self.paths.job_file(job_id)
        if not path.exists():
            raise MarketingError(
                "JOB_NOT_FOUND",
                f"Render job {job_id} does not exist.",
                suggested_action="Call render_preview or render_project and use the returned job_id.",
                job_id=job_id,
            )
        return RenderJob.model_validate(read_json(path))


def _dedupe(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _profile(project: Project, profile: str, preview_edge: int, preview_crf: int, final_crf: int) -> tuple[int, int, int]:
    if profile == "final":
        return project.width, project.height, final_crf
    long_edge = max(project.width, project.height)
    scale = preview_edge / long_edge if long_edge else 1
    width = max(2, int(project.width * scale) // 2 * 2)
    height = max(2, int(project.height * scale) // 2 * 2)
    return width, height, preview_crf


def _audio_tracks(project: Project, scenes: dict[str, Scene], assets, root: Path):
    from app.renderer.timeline import build_timeline

    tracks: list[tuple[AudioTrack, Path]] = []
    for raw in project.audio_tracks:
        track = AudioTrack.model_validate(raw)
        tracks.append((track, root / assets[track.asset_id].blob_path))
    timeline = build_timeline(project.scene_order, scenes)
    offsets = {entry.scene_id: entry.start for entry in timeline.entries}
    for scene in scenes.values():
        for track in scene.audio:
            shifted = track.model_copy(update={"start": track.start + offsets.get(scene.scene_id, 0)})
            tracks.append((shifted, root / assets[track.asset_id].blob_path))
    return tracks
