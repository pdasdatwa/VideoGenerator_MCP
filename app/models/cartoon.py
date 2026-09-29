"""The cartoon block on a scene. Declarative direction, compiled into ordinary layers at render time."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.character import Point


class CartoonAction(BaseModel):
    """One named animation direction. The engine turns it into keyframes."""

    model_config = ConfigDict(extra="forbid")

    type: str
    action_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    start: float = Field(default=0, ge=0)
    duration: float | None = Field(default=None, gt=0, le=120)
    direction: Literal["left", "right", "up", "down"] | None = None
    distance: float | None = Field(default=None, ge=0, le=2)
    intensity: float = Field(default=1, ge=0, le=3)
    repeat: int | None = Field(default=None, ge=1, le=40)
    target: str | Point | None = None
    to: str | None = None


class SceneCharacter(BaseModel):
    """A character placed in one scene. Identity and artwork come from the Character record."""

    model_config = ConfigDict(extra="forbid")

    character_id: str
    pose: str | None = None
    expression: str | None = None
    position: Point | None = None
    scale: float | None = Field(default=None, gt=0, le=8)
    size: float | None = Field(default=None, gt=0, le=2)
    anchor: Point | None = None
    rotation: float = Field(default=0, ge=-180, le=180)
    opacity: float = Field(default=1, ge=0, le=1)
    z_index: int = 20
    start: float = Field(default=0, ge=0)
    duration: float | None = Field(default=None, gt=0, le=120)
    accessories: list[str] = Field(default_factory=list)
    actions: list[CartoonAction] = Field(default_factory=list)


class DialogueStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bubble: bool = True
    bubble_asset_id: str | None = None
    bubble_color: str = "#FFFFFF"
    bubble_opacity: float = Field(default=1, ge=0, le=1)
    text_color: str = "#111111"
    font_family: str = "Inter"
    font_size: float | None = Field(default=None, gt=0, le=400)
    font_weight: int = Field(default=600, ge=100, le=900)
    align: Literal["left", "center", "right"] = "center"
    max_width: float = Field(default=0.42, gt=0, le=1)
    position: Point | None = None
    offset: Point | None = None
    z_index: int = 60


class Dialogue(BaseModel):
    """Editable text. Never baked into a character asset."""

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    character_id: str | None = None
    text: str = Field(min_length=1, max_length=600)
    start: float = Field(default=0, ge=0)
    duration: float = Field(gt=0, le=120)
    style: DialogueStyle | None = None
    animation: str | None = None


class CameraKeyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: float = Field(ge=0, le=120)
    position: Point | None = None
    zoom: float | None = Field(default=None, ge=0.25, le=6)
    rotation: float | None = Field(default=None, ge=-180, le=180)


class CameraAnimation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    start: float = Field(default=0, ge=0)
    duration: float | None = Field(default=None, gt=0, le=120)
    amount: float | None = Field(default=None, ge=0, le=4)
    intensity: float = Field(default=1, ge=0, le=3)
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out"] | None = None


class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot: str | None = None
    zoom: float | None = Field(default=None, ge=0.25, le=6)
    position: Point | None = None
    focus: str | None = None
    rotation: float = Field(default=0, ge=-180, le=180)
    animation: CameraAnimation | None = None
    keyframes: list[CameraKeyframe] = Field(default_factory=list)


class Prop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    asset_id: str
    position: Point = Field(default_factory=lambda: Point(x=0.5, y=0.7))
    scale: float = Field(default=1, gt=0, le=8)
    size: float | None = Field(default=None, gt=0, le=2)
    anchor: Point | None = None
    rotation: float = Field(default=0, ge=-180, le=180)
    opacity: float = Field(default=1, ge=0, le=1)
    z_index: int = 15
    start: float = Field(default=0, ge=0)
    duration: float | None = Field(default=None, gt=0, le=120)
    animation: CartoonAction | None = None


class CartoonBackground(BaseModel):
    """A flat background, or layered plates for parallax."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str | None = None
    background: str | None = None
    midground: str | None = None
    foreground: str | None = None
    color: str | None = None
    parallax: float = Field(default=0, ge=0, le=1)
    fit: Literal["contain", "cover", "fill"] = "cover"


class CartoonSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: CartoonBackground | None = None
    characters: list[SceneCharacter] = Field(default_factory=list)
    dialogue: list[Dialogue] = Field(default_factory=list)
    camera: Camera | None = None
    props: list[Prop] = Field(default_factory=list)
