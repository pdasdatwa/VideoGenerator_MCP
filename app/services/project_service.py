"""Project CRUD on the local filesystem."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import PRESETS, SAFE_AREAS, Settings
from app.errors import MarketingError
from app.ids import new_id
from app.models.project import Brand, GlobalEffects, Project, SafeArea
from app.storage.filesystem import read_json, write_json
from app.storage.paths import DataPaths

MODES = ("standard", "cartoon")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.paths = DataPaths(settings.data_dir)
        self.paths.ensure()

    def create(
        self,
        name: str,
        *,
        description: str = "",
        preset: str | None = "instagram_reels",
        width: int | None = None,
        height: int | None = None,
        fps: int = 30,
        platform: str | None = None,
        brand: dict[str, Any] | None = None,
        mode: str = "standard",
    ) -> dict[str, Any]:
        if not name.strip():
            raise MarketingError(
                "INVALID_PROJECT",
                "Project name is required.",
                suggested_action="Pass a non-empty name.",
            )
        if fps <= 0 or fps > 120:
            raise MarketingError(
                "INVALID_PROJECT",
                "fps must be between 1 and 120.",
                suggested_action="Use 30 unless the reel needs another frame rate.",
            )
        if mode not in MODES:
            raise MarketingError(
                "INVALID_PROJECT",
                f"Unknown mode '{mode}'.",
                suggested_action="Use mode='standard' for ordinary video, or mode='cartoon' to enable character production.",
            )
        chosen = preset or "custom"
        if width and height:
            chosen = "custom"
            frame = (width, height, _aspect(width, height))
        elif chosen in PRESETS:
            frame = PRESETS[chosen]
        else:
            raise MarketingError(
                "INVALID_PROJECT",
                f"Unknown preset '{chosen}'.",
                suggested_action="Use instagram_reels, youtube_shorts, youtube, landscape, square, portrait, or pass width and height.",
            )
        if frame[0] < 2 or frame[1] < 2:
            raise MarketingError(
                "INVALID_DIMENSIONS",
                "Width and height must be at least 2 pixels.",
                suggested_action="Choose a preset or a larger custom size.",
            )
        platform_key = platform or (chosen if chosen in SAFE_AREAS else "custom")
        if platform_key not in SAFE_AREAS:
            raise MarketingError(
                "INVALID_PROJECT",
                f"Unknown platform '{platform_key}'.",
                suggested_action="Use instagram_reels, youtube_shorts, youtube, landscape, square, portrait, or custom.",
            )
        project = Project(
            project_id=new_id("project"),
            name=name.strip(),
            description=description,
            mode=mode,  # type: ignore[arg-type]
            created_at=_now(),
            updated_at=_now(),
            width=frame[0],
            height=frame[1],
            fps=fps,
            aspect_ratio=frame[2],
            platform=platform_key,
            brand=Brand.model_validate(brand) if brand else None,
            global_effects=GlobalEffects(),
            safe_area=SafeArea.model_validate(SAFE_AREAS[platform_key]),
            preset=chosen if chosen in PRESETS else "custom",
        )
        self.paths.ensure_project(project.project_id)
        self.save(project)
        return project.model_dump(mode="json")

    def create_or_update(
        self,
        name: str,
        *,
        project_id: str | None = None,
        description: str = "",
        preset: str | None = "instagram_reels",
        width: int | None = None,
        height: int | None = None,
        fps: int = 30,
        platform: str | None = None,
        mode: str = "standard",
    ) -> dict[str, Any]:
        if project_id:
            path = self.paths.project_file(project_id)
            if path.exists():
                fields: dict[str, Any] = {"name": name, "description": description, "fps": fps}
                if platform:
                    fields["platform"] = platform
                if width and height:
                    fields["width"] = width
                    fields["height"] = height
                return self.update(project_id, fields)
        return self.create(
            name,
            description=description,
            preset=preset,
            width=width,
            height=height,
            fps=fps,
            platform=platform,
            mode=mode,
        )

    def save(self, project: Project) -> None:
        project.updated_at = _now()
        write_json(self.paths.project_file(project.project_id), project.model_dump(mode="json"))

    def get(self, project_id: str) -> Project:
        path = self.paths.project_file(project_id)
        if not path.exists():
            raise MarketingError(
                "PROJECT_NOT_FOUND",
                f"Project {project_id} does not exist.",
                suggested_action="Call list_projects and use an existing project_id.",
                project_id=project_id,
            )
        return Project.model_validate(read_json(path))

    def get_dict(self, project_id: str) -> dict[str, Any]:
        project = self.get(project_id)
        return project.model_dump(mode="json")

    def list_projects(self) -> list[dict[str, Any]]:
        root = self.paths.root / "projects"
        if not root.exists():
            return []
        projects = []
        for path in sorted(root.glob("*/project.json")):
            projects.append(read_json(path))
        return projects

    def update(self, project_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        project = self.get(project_id)
        data = project.model_dump()
        allowed = {
            "name",
            "description",
            "mode",
            "fps",
            "platform",
            "brand",
            "global_effects",
            "safe_area",
            "audio_tracks",
            "scene_order",
            "width",
            "height",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise MarketingError(
                "INVALID_PROJECT",
                f"Cannot update {', '.join(sorted(unknown))}.",
                suggested_action=f"Update only: {', '.join(sorted(allowed))}.",
            )
        data.update(fields)
        if "width" in fields or "height" in fields:
            data["aspect_ratio"] = _aspect(int(data["width"]), int(data["height"]))
            data["preset"] = "custom"
        updated = Project.model_validate(data)
        self.save(updated)
        return updated.model_dump(mode="json")

    def delete(self, project_id: str) -> dict[str, Any]:
        self.get(project_id)
        from app.storage.filesystem import delete_tree

        delete_tree(self.paths.project_dir(project_id))
        return {"deleted": project_id}

    def require_cartoon(self, project_id: str) -> Project:
        """Cartoon tools refuse to run on a standard project and never switch the mode themselves."""
        project = self.get(project_id)
        if project.mode != "cartoon":
            raise MarketingError(
                "CARTOON_MODE_REQUIRED",
                "Character tools require a project with mode='cartoon'.",
                suggested_action=(
                    "Create the project with mode='cartoon', or call update_project with "
                    "fields={'mode': 'cartoon'} after confirming that with the user."
                ),
                project_id=project_id,
                mode=project.mode,
            )
        return project


def _aspect(width: int, height: int) -> str:
    ratio = width / height
    known = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1, "4:5": 4 / 5}
    for name, value in known.items():
        if abs(ratio - value) < 0.02:
            return name
    return f"{width}:{height}"
