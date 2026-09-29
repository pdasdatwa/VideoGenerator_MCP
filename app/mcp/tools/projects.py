"""Project tools."""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def create_project(
        name: str,
        description: str = "",
        preset: str = "instagram_reels",
        width: int | None = None,
        height: int | None = None,
        fps: int = 30,
        platform: str | None = None,
        mode: str = "standard",
    ) -> dict:
        """Purpose: Create one project and its storage folder.

        When to use: The user wants a new reel and you do not already have a project_id.
        Arguments: name; optional description, preset (instagram_reels, youtube_shorts, youtube, landscape, square, portrait), width, height, fps, platform, mode.
        Returns: The project record including project_id, mode, dimensions, fps, and safe area.
        Side effects: Writes data/projects/<project_id>/project.json.
        Cache behavior: No render cache is touched.
        Errors: INVALID_PROJECT, INVALID_DIMENSIONS.
        Example: create_project(name="Travel reel", preset="instagram_reels")
        Cartoon: pass mode="cartoon" to enable characters, dialogue, actions, camera, and props. mode defaults to "standard".
        """
        return call(
            ctx.projects.create,
            name,
            description=description,
            preset=preset,
            width=width,
            height=height,
            fps=fps,
            platform=platform,
            mode=mode,
        )

    @mcp.tool()
    def get_project(project_id: str) -> dict:
        """Purpose: Read one project, including scene order and duration.

        When to use: You need the current settings before editing or rendering.
        Arguments: project_id.
        Returns: The project record.
        Side effects: None.
        Cache behavior: None.
        Errors: PROJECT_NOT_FOUND.
        Example: get_project(project_id="project_01")
        """
        return call(ctx.projects.get_dict, project_id)

    @mcp.tool()
    def list_projects() -> dict:
        """Purpose: List every local project.

        When to use: You do not know which project_id to continue.
        Arguments: None.
        Returns: {"projects": [...]}.
        Side effects: None.
        Cache behavior: None.
        Errors: None on an empty library.
        Example: list_projects()
        """
        return {"projects": ctx.projects.list_projects()}

    @mcp.tool()
    def update_project(project_id: str, fields: dict) -> dict:
        """Purpose: Change project settings, scene order, audio tracks, safe area, or global effects.

        When to use: The user changes format, brand, music, or scene order. Do not use this to edit layer animation; use update_scene.
        Arguments: project_id; fields object with any of name, description, mode, fps, platform, brand, global_effects, safe_area, audio_tracks, scene_order, width, height.
        Returns: The updated project.
        Side effects: Rewrites project.json. Dimension, fps, safe area, and global effect changes alter visual cache keys.
        Cache behavior: Existing scene files stay on disk. The next render recomputes keys and reuses matches.
        Errors: PROJECT_NOT_FOUND, INVALID_PROJECT.
        Example: update_project(project_id="project_01", fields={"name": "Spring cut"})
        """
        return call(ctx.projects.update, project_id, fields)

    @mcp.tool()
    def delete_project(project_id: str) -> dict:
        """Purpose: Delete a project and its scenes, renders, and cache.

        When to use: The user explicitly wants the project removed.
        Arguments: project_id.
        Returns: {"deleted": project_id}.
        Side effects: Removes the project directory. Shared content-addressed blobs used by other projects are kept.
        Cache behavior: That project's scene cache is deleted.
        Errors: PROJECT_NOT_FOUND.
        Example: delete_project(project_id="project_01")
        """
        return call(ctx.projects.delete, project_id)

    @mcp.tool()
    def create_or_update_project(
        name: str,
        project_id: str | None = None,
        description: str = "",
        preset: str = "instagram_reels",
        width: int | None = None,
        height: int | None = None,
        fps: int = 30,
        platform: str | None = None,
        mode: str = "standard",
    ) -> dict:
        """Purpose: Create a project, or update an existing one when project_id is already stored.

        When to use: You want one call instead of checking get_project before create_project.
        Arguments: name; optional project_id, description, preset, width, height, fps, platform, mode.
        Returns: The project record.
        Side effects: Creates storage or rewrites allowed project fields.
        Cache behavior: Dimension and fps changes alter later cache keys.
        Errors: INVALID_PROJECT, PROJECT_NOT_FOUND.
        Example: create_or_update_project(name="Birthday", preset="square")
        Cartoon: mode applies to new projects only. An existing project keeps its mode; change it with update_project.
        """
        return call(
            ctx.projects.create_or_update,
            name,
            project_id=project_id,
            description=description,
            preset=preset,
            width=width,
            height=height,
            fps=fps,
            platform=platform,
            mode=mode,
        )
