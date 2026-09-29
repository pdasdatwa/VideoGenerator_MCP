"""Render tools."""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def render_preview(project_id: str, wait: bool = False) -> dict:
        """Purpose: Render a fast lower-resolution cut of the whole project.

        When to use: You want to iterate before a full-size export.
        Arguments: project_id; wait=true to block until the job finishes (local debugging). Default returns immediately.
        Returns: A job record. When it completes, report.rendered, report.cached, and report.cache_hit_rate say what was reused.
        Side effects: May render missing scenes with Remotion and stitch them with FFmpeg.
        Cache behavior: Reuses scene MP4s whose visual cache key matches. Does not rerender cache hits.
        Errors: The job error field carries INVALID_* or RENDER_FAILURE or FFMPEG_FAILURE. Poll get_render_status.
        Example: render_preview(project_id="project_01", wait=true)
        """
        return call(ctx.renders.render_preview, project_id, wait=wait)

    @mcp.tool()
    def render_project(project_id: str, wait: bool = False) -> dict:
        """Purpose: Render the final-resolution project.

        When to use: The user wants the deliverable MP4.
        Arguments: project_id; optional wait.
        Returns: A job record whose output_path is the MP4 when status is completed.
        Side effects: Renders cache misses at project resolution, stitches scenes, mixes audio.
        Cache behavior: Same incremental rules as preview, but the final profile has its own cache keys.
        Errors: Reported on the job. Use get_render_status.
        Example: render_project(project_id="project_01", wait=true)
        """
        return call(ctx.renders.render_project, project_id, wait=wait)

    @mcp.tool()
    def render_scene(project_id: str, scene_id: str, profile: str = "preview", wait: bool = False) -> dict:
        """Purpose: Render a single scene.

        When to use: You want to inspect one scene without assembling the whole film.
        Arguments: project_id, scene_id, profile (preview or final), wait.
        Returns: A job record. report.rendered or report.cached contains that scene only.
        Side effects: Writes one scene MP4 into the cache and copies it to the job output.
        Cache behavior: A matching key returns the cached file and does not call Remotion.
        Errors: SCENE_NOT_FOUND and render errors on the job.
        Example: render_scene(project_id="project_01", scene_id="scene_02", wait=true)
        """
        return call(ctx.renders.render_scene, project_id, scene_id, profile=profile, wait=wait)

    @mcp.tool()
    def get_render_status(job_id: str) -> dict:
        """Purpose: Read job progress.

        When to use: After render_preview or render_project when wait was false.
        Arguments: job_id.
        Returns: status (queued, running, completed, failed, cancelled), progress, current_scene, error, report.
        Side effects: None.
        Cache behavior: None.
        Errors: JOB_NOT_FOUND.
        Example: get_render_status(job_id="job_01")
        """
        return call(ctx.renders.get_status, job_id)

    @mcp.tool()
    def get_render(job_id: str) -> dict:
        """Purpose: Read a finished render, including the output path and cache report.

        When to use: status is completed and you need the MP4 location and cache_hit_rate.
        Arguments: job_id.
        Returns: The job plus file_size when the MP4 exists.
        Side effects: None.
        Cache behavior: None. The report lists which scenes were reused.
        Errors: JOB_NOT_FOUND.
        Example: get_render(job_id="job_01")
        """
        return call(ctx.renders.get_render, job_id)
