"""Persisted asset record. Technical and semantic metadata stay separate."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Asset(BaseModel):
    id: str
    project_id: str
    filename: str
    type: Literal["image", "video", "audio", "svg"]
    mime_type: str
    file_size: int
    sha256: str
    blob_path: str
    width: int | None = None
    height: int | None = None
    has_alpha: bool | None = None
    duration: float | None = None
    technical_metadata: dict[str, Any] = Field(default_factory=dict)
    semantic_metadata: dict[str, Any] | None = None
    semantic_type: (
        Literal[
            "character_base",
            "character_pose",
            "character_expression",
            "character_accessory",
            "character_part",
            "background",
            "prop",
            "speech_bubble",
            "other",
        ]
        | None
    ) = None
    character_id: str | None = None
    semantic_metadata_note: str = (
        "semantic_metadata, semantic_type, and character_id are caller-supplied and are not verified by this server."
    )
    preview: dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str
