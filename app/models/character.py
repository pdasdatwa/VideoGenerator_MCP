"""A character is a named identity plus the assets that draw it. Identity persists across scenes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CharacterAssets(BaseModel):
    """asset_id references only. The files live in the ordinary asset registry."""

    model_config = ConfigDict(extra="forbid")

    base: str | None = None
    poses: dict[str, str] = Field(default_factory=dict)
    expressions: dict[str, str] = Field(default_factory=dict)
    variants: dict[str, str] = Field(default_factory=dict)
    parts: dict[str, str] = Field(default_factory=dict)
    accessories: dict[str, str] = Field(default_factory=dict)


class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str
    project_id: str
    name: str
    description: str = ""
    traits: list[str] = Field(default_factory=list)
    visual_style: str = ""
    default_position: Point = Field(default_factory=lambda: Point(x=0.5, y=0.78))
    default_scale: float = Field(default=1, gt=0, le=8)
    default_size: float = Field(default=0.55, gt=0, le=2)
    default_anchor: Point = Field(default_factory=lambda: Point(x=0.5, y=1))
    assets: CharacterAssets = Field(default_factory=CharacterAssets)
    metadata: dict[str, Any] | None = None
    metadata_note: str = (
        "name, description, traits, visual_style, and metadata are caller-supplied and are not verified by this server."
    )
    created_at: str
    updated_at: str
