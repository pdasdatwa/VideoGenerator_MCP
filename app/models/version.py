"""A restorable snapshot of project settings and scene specifications."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectVersion(BaseModel):
    version_id: str
    project_id: str
    number: int
    label: str | None = None
    note: str | None = None
    created_at: str
    restored_from: str | None = None
    scene_order: list[str] = Field(default_factory=list)
    project: dict[str, Any]
    scenes: dict[str, Any]
    characters: dict[str, Any] = Field(default_factory=dict)
