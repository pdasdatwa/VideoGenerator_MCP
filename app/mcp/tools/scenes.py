"""Scene and validation tools."""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def create_scene(project_id: str, scene: dict) -> dict:
        """Purpose: Store one declarative scene.

        When to use: You have designed a scene as JSON. Send the whole scene, not one layer at a time.
        Arguments: project_id; scene object with scene_id, duration, background, layers, optional audio and transition_out.
        Returns: The stored scene plus timeline_start and timeline_end.
        Side effects: Writes the scene and appends it to scene_order. Updates project duration.
        Cache behavior: A new scene has no cache entry until the next render.
        Errors: INVALID_SCENE, INVALID_LAYER, INVALID_ANIMATION, INVALID_COORDINATES, INVALID_DURATION, INVALID_ASSET_REFERENCE.
        Example: create_scene(project_id="project_01", scene={"scene_id": "scene_01", "duration": 3, "layers": []})
        """
        return call(ctx.scenes.create, project_id, scene)

    @mcp.tool()
    def get_scene(project_id: str, scene_id: str) -> dict:
        """Purpose: Read one scene specification.

        When to use: Before you modify a scene, so you can send back a complete update.
        Arguments: project_id, scene_id.
        Returns: The scene plus its place on the timeline.
        Side effects: None.
        Cache behavior: None.
        Errors: SCENE_NOT_FOUND.
        Example: get_scene(project_id="project_01", scene_id="scene_02")
        """
        return call(ctx.scenes.get, project_id, scene_id)

    @mcp.tool()
    def list_scenes(project_id: str) -> dict:
        """Purpose: List scenes in timeline order.

        When to use: You need every scene_id and the computed start and end times.
        Arguments: project_id.
        Returns: duration, timeline, and scenes.
        Side effects: None.
        Cache behavior: None.
        Errors: PROJECT_NOT_FOUND.
        Example: list_scenes(project_id="project_01")
        """
        return call(ctx.scenes.list_scenes, project_id)

    @mcp.tool()
    def update_scene(project_id: str, scene_id: str, scene: dict) -> dict:
        """Purpose: Replace one scene specification.

        When to use: The user asks to change copy, timing, motion, or assets in a single scene.
        Arguments: project_id, scene_id, and the full scene object. scene_id in the object is overwritten by the argument.
        Returns: The updated scene and timeline placement.
        Side effects: Rewrites that scene file and the project duration.
        Cache behavior: The visual cache key changes only if the visual spec or referenced asset hashes change. Other scenes stay cached. Audio-only edits do not change the visual key.
        Errors: SCENE_NOT_FOUND plus the same validation errors as create_scene.
        Example: update_scene(project_id="project_01", scene_id="scene_02", scene={"scene_id": "scene_02", "duration": 4, "layers": []})
        """
        return call(ctx.scenes.update, project_id, scene_id, scene)

    @mcp.tool()
    def delete_scene(project_id: str, scene_id: str) -> dict:
        """Purpose: Remove a scene from the project.

        When to use: The user no longer wants that scene in the timeline.
        Arguments: project_id, scene_id.
        Returns: {"deleted": scene_id}.
        Side effects: Deletes the scene file and updates scene_order and duration.
        Cache behavior: The next assembly omits the scene. Other scene caches remain.
        Errors: SCENE_NOT_FOUND.
        Example: delete_scene(project_id="project_01", scene_id="scene_03")
        """
        return call(ctx.scenes.delete, project_id, scene_id)

    @mcp.tool()
    def upsert_scene(project_id: str, scene: dict) -> dict:
        """Purpose: Create a scene or replace it when scene_id already exists.

        When to use: You are building or revising a composition and do not want a separate existence check.
        Arguments: project_id and the full scene object.
        Returns: The stored scene plus timeline placement.
        Side effects: Writes the scene file and updates project duration.
        Cache behavior: Same as create_scene or update_scene.
        Errors: The same validation errors as create_scene.
        Example: upsert_scene(project_id="project_01", scene={"scene_id": "scene_01", "duration": 4, "layers": []})
        """
        return call(ctx.scenes.upsert, project_id, scene)

    @mcp.tool()
    def validate_scene(project_id: str, scene: dict) -> dict:
        """Purpose: Check a scene without saving it.

        When to use: You want to know if a spec is legal before create_scene or update_scene.
        Arguments: project_id and a scene object. Referenced assets must already be registered.
        Returns: {"valid": true, "scene_id": ...} or an error object.
        Side effects: None.
        Cache behavior: None.
        Errors: INVALID_SCENE, INVALID_ASSET_REFERENCE, INVALID_ANIMATION, INVALID_COORDINATES, INVALID_DURATION.
        Example: validate_scene(project_id="project_01", scene={"scene_id": "draft", "duration": 2, "layers": []})
        """
        return call(ctx.scenes.validate_scene, project_id, scene)

    @mcp.tool()
    def validate_project(project_id: str) -> dict:
        """Purpose: Check every saved scene, asset reference, transition, and the timeline.

        When to use: Before render_preview or render_project.
        Arguments: project_id.
        Returns: {"valid": true, duration, timeline, scene_count} or an error object.
        Side effects: None.
        Cache behavior: None.
        Errors: INVALID_SCENE, INVALID_ASSET_REFERENCE, INVALID_DURATION, PROJECT_NOT_FOUND.
        Example: validate_project(project_id="project_01")
        """
        return call(ctx.scenes.validate_project, project_id)
