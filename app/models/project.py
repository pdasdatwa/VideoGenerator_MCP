"""Persisted project record."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Brand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    font_family: str | None = None


class SafeArea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: float = Field(ge=0, le=0.45)
    bottom: float = Field(ge=0, le=0.45)
    left: float = Field(ge=0, le=0.45)
    right: float = Field(ge=0, le=0.45)


class GlobalEffects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brightness: float = Field(default=1, ge=0, le=3)
    contrast: float = Field(default=1, ge=0, le=3)
    saturation: float = Field(default=1, ge=0, le=3)
    tint: str | None = None
    tint_opacity: float = Field(default=0, ge=0, le=1)
    vignette: float = Field(default=0, ge=0, le=1)


class Project(BaseModel):
    project_id: str
    name: str
    description: str = ""
    mode: Literal["standard", "cartoon"] = "standard"
    created_at: str
    updated_at: str
    width: int
    height: int
    fps: int = 30
    duration: float = 0
    aspect_ratio: str
    platform: str | None = None
    brand: Brand | None = None
    scene_order: list[str] = Field(default_factory=list)
    audio_tracks: list[dict[str, Any]] = Field(default_factory=list)
    global_effects: GlobalEffects = Field(default_factory=GlobalEffects)
    safe_area: SafeArea
    current_version: str | None = None
    preset: Literal["instagram_reels", "youtube", "square", "portrait", "custom"] = "custom"
