"""Computed placement of scenes on the project timeline."""

from __future__ import annotations

from pydantic import BaseModel


class TimelineEntry(BaseModel):
    scene_id: str
    index: int
    start: float
    end: float
    duration: float


class Timeline(BaseModel):
    entries: list[TimelineEntry]
    duration: float
