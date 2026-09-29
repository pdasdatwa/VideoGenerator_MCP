"""Declarative scene specification. The renderer accepts only this shape."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.cartoon import CartoonSpec


class Background(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["color", "image", "video"] = "color"
    value: str | None = "#000000"
    asset_id: str | None = None


class TextStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font_family: str = "Inter"
    font_size: float = Field(default=48, gt=0, le=400)
    font_weight: int = Field(default=400, ge=100, le=900)
    color: str = "#FFFFFF"
    align: Literal["left", "center", "right"] = "center"
    line_height: float = Field(default=1.2, gt=0, le=4)
    letter_spacing: float = Field(default=0, ge=-20, le=80)
    max_width: float | None = Field(default=None, gt=0, le=1)


class ColorTint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str = "#FFFFFF"
    amount: float = Field(default=0.3, ge=0, le=1)


class Effects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blur: Any = None
    brightness: Any = None
    contrast: Any = None
    saturation: Any = None
    grayscale: float | None = Field(default=None, ge=0, le=1)
    drop_shadow: bool | None = None
    motion_blur: float | None = Field(default=None, ge=0, le=1)
    sepia: float | None = Field(default=None, ge=0, le=1)
    vignette: float | None = Field(default=None, ge=0, le=1)
    glow: float | None = Field(default=None, ge=0, le=1)
    bloom: float | None = Field(default=None, ge=0, le=1)
    grain: float | None = Field(default=None, ge=0, le=1)
    color_tint: ColorTint | None = None


class Mask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shape: Literal["rect", "rounded_rect", "circle", "ellipse"]
    x: Any = 0.5
    y: Any = 0.5
    width: Any = 0.5
    height: Any = 0.5
    radius: Any = 0


class Duck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    when_role: Literal["voiceover"] = "voiceover"
    to_volume: float = Field(default=0.25, ge=0, le=2)
    attack: float = Field(default=0.15, ge=0, le=5)
    release: float = Field(default=0.3, ge=0, le=5)


class GradientStop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str
    offset: float = Field(ge=0, le=1)


class Gradient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    angle: float = 180
    stops: list[GradientStop] = Field(min_length=2)


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["cut", "fade", "crossfade", "slide", "zoom", "blur", "whip", "dip_to_color"] = "cut"
    duration: float = Field(default=0.4, ge=0, le=2)
    direction: Literal["left", "right", "up", "down"] = "left"
    color: str = "#000000"


class Animation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    duration: float | None = Field(default=None, gt=0, le=30)
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out", "spring"] | None = None


class AudioTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    asset_id: str
    role: Literal["voiceover", "music", "sfx"] = "music"
    start: float = Field(default=0, ge=0)
    duration: float | None = Field(default=None, gt=0)
    volume: Any = 1
    fade_in: float = Field(default=0, ge=0)
    fade_out: float = Field(default=0, ge=0)
    trim_start: float = Field(default=0, ge=0)
    trim_end: float | None = Field(default=None, gt=0)
    duck: Duck | None = None


class Layer(BaseModel):
    """A layer. Transform fields accept a static value, from/to, or keyframes."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    type: Literal["image", "video", "svg", "text", "shape"]
    asset_id: str | None = None
    content: str | None = None
    start: float = Field(default=0, ge=0)
    duration: float | None = Field(default=None, gt=0)
    z_index: int = 0
    position: Any = None
    scale: Any = None
    rotation: Any = None
    opacity: Any = None
    anchor: Any = None
    crop: Any = None
    fit: Literal["contain", "cover", "crop", "fill"] | None = None
    effects: Effects | None = None
    animation: Animation | None = None
    style: TextStyle | None = None
    trim_start: float | None = Field(default=None, ge=0)
    trim_end: float | None = Field(default=None, gt=0)
    playback_rate: Any = 1
    loop: bool = False
    blend_mode: Literal["normal", "multiply", "screen", "overlay", "soft_light"] = "normal"
    mask: Mask | None = None
    shape: Literal["rect", "ellipse", "gradient"] | None = None
    fill: str | None = None
    width: float | None = Field(default=None, gt=0, le=2)
    height: float | None = Field(default=None, gt=0, le=2)
    border_radius: float | None = Field(default=None, ge=0, le=1)
    gradient: Gradient | None = None
    respect_safe_area: bool = True


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str | None = None
    duration: float = Field(gt=0, le=120)
    background: Background = Field(default_factory=Background)
    layers: list[Layer] = Field(default_factory=list)
    audio: list[AudioTrack] = Field(default_factory=list)
    transition_out: Transition = Field(default_factory=lambda: Transition(type="cut", duration=0))
    cartoon: CartoonSpec | None = None
