"""Version tools."""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def create_version(project_id: str, label: str | None = None, note: str | None = None) -> dict:
        """Purpose: Snapshot the current project settings and scene specifications.

        When to use: After a coherent edit the user may want to restore.
        Arguments: project_id, optional label and note.
        Returns: version_id, number, and scene_order. Scene renders stay addressable by cache key.
        Side effects: Writes a version file and points current_version at it.
        Cache behavior: Does not delete or rerender cached scenes.
        Errors: PROJECT_NOT_FOUND.
        Example: create_version(project_id="project_01", label="approved-hook")
        """
        return call(ctx.versions.create, project_id, label=label, note=note)

    @mcp.tool()
    def list_versions(project_id: str) -> dict:
        """Purpose: List snapshots from oldest to newest.

        When to use: The user asks what can be restored.
        Arguments: project_id.
        Returns: {"versions": [...]} summaries without the full scene bodies.
        Side effects: None.
        Cache behavior: None.
        Errors: PROJECT_NOT_FOUND.
        Example: list_versions(project_id="project_01")
        """
        return call(lambda: {"versions": ctx.versions.list_versions(project_id)})

    @mcp.tool()
    def get_version(project_id: str, version_id: str) -> dict:
        """Purpose: Read one snapshot, including every scene specification.

        When to use: You need to compare or explain a previous cut.
        Arguments: project_id, version_id.
        Returns: The full version record.
        Side effects: None.
        Cache behavior: None.
        Errors: VERSION_NOT_FOUND.
        Example: get_version(project_id="project_01", version_id="ver_01")
        """
        return call(ctx.versions.get, project_id, version_id)

    @mcp.tool()
    def restore_version(project_id: str, version_id: str) -> dict:
        """Purpose: Make a previous snapshot the current project again.

        When to use: The user says to go back to an earlier version.
        Arguments: project_id, version_id.
        Returns: restored_from, the new version created for the restore, and kept_versions.
        Side effects: Rewrites current scenes from the snapshot. Does not delete newer version records. Appends a new version noting the restore.
        Cache behavior: Scene files change back, so the next render reuses any cache keys that match the restored specs.
        Errors: VERSION_NOT_FOUND.
        Example: restore_version(project_id="project_01", version_id="ver_01")
        """
        return call(ctx.versions.restore, project_id, version_id)
