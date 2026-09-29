"""Render job and cache report."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RenderReport(BaseModel):
    rendered: list[str] = Field(default_factory=list)
    cached: list[str] = Field(default_factory=list)
    cache_hit_rate: float = 0
    output_path: str | None = None
    profile: str = "final"
    warnings: list[str] = Field(default_factory=list)


class RenderJob(BaseModel):
    job_id: str
    project_id: str
    type: Literal["preview", "final", "scene"]
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    progress: float = 0
    current_scene: str | None = None
    output_path: str | None = None
    error: dict[str, Any] | None = None
    report: RenderReport | None = None
    scene_id: str | None = None
    profile: str = "final"
