"""Deterministic cartoon animation primitives.

A primitive turns one named direction such as ``walk_in`` into an offset from the character's
resting placement at a given time. Nothing here reads a clock, a random source, or the project
fps, so the same action always produces the same numbers. The compiler samples these offsets on
a fixed grid and writes ordinary layer keyframes.

Offsets are normalized to the frame: 0.1 on x is a tenth of the frame width. Scale and opacity
are multipliers. Rotation is degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from app.models.cartoon import CartoonAction
from app.renderer.cartoon.names import ACTION_SPECS

# Offsets are sampled at a fixed rate so output never depends on project fps.
SAMPLE_RATE = 24
MAX_SAMPLES_PER_ACTION = 480

DEFAULT_DURATIONS: dict[str, float] = {
    "walk": 2.0,
    "walk_in": 2.0,
    "walk_out": 2.0,
    "run": 1.4,
    "enter": 1.0,
    "exit": 1.0,
    "slide": 1.0,
    "jump": 0.9,
    "bounce": 1.0,
    "squash": 0.5,
    "stretch": 0.5,
    "shake": 0.8,
    "recoil": 0.7,
    "lean": 0.6,
    "nod": 0.9,
    "shake_head": 0.9,
    "point": 0.6,
    "wave": 1.2,
    "sit": 0.7,
    "stand": 0.7,
    "turn": 0.5,
    "talk": 1.5,
    "blink": 1.0,
    "look_left": 0.5,
    "look_right": 0.5,
    "look_at": 0.5,
    "expression_change": 0.4,
    "surprised_reaction": 0.8,
    "angry_reaction": 1.0,
    "confused_reaction": 1.2,
    "happy_reaction": 1.0,
    "sad_reaction": 1.0,
    "shocked_reaction": 0.9,
    "laugh": 1.4,
    "cry": 1.6,
    "impact": 0.6,
    "pop": 0.5,
    "overshoot": 0.8,
    "anticipation": 0.5,
}

DEFAULT_DISTANCES: dict[str, float] = {
    "walk": 0.35,
    "walk_in": 0.55,
    "walk_out": 0.55,
    "run": 0.5,
    "enter": 0.45,
    "exit": 0.45,
    "slide": 0.2,
    "overshoot": 0.25,
}

DEFAULT_REPEATS: dict[str, int] = {
    "bounce": 2,
    "jump": 1,
    "shake": 6,
    "nod": 2,
    "shake_head": 2,
    "wave": 3,
    "talk": 4,
    "blink": 2,
    "laugh": 3,
    "cry": 4,
}

DEFAULT_DIRECTIONS: dict[str, str] = {
    "walk": "right",
    "walk_in": "left",
    "walk_out": "right",
    "run": "right",
    "enter": "left",
    "exit": "right",
    "slide": "right",
    "recoil": "left",
    "lean": "right",
    "point": "right",
    "turn": "right",
    "impact": "left",
    "overshoot": "right",
    "anticipation": "right",
}

_AXIS = {"left": (-1.0, 0.0), "right": (1.0, 0.0), "up": (0.0, -1.0), "down": (0.0, 1.0)}

# Actions that start somewhere other than the resting placement, and therefore hold that
# starting offset for the part of the scene before they begin.
_PRE_HOLD = {"walk_in", "enter", "pop", "stand"}


@dataclass(frozen=True)
class Deltas:
    """An offset from the resting placement. Positions add, scale and opacity multiply."""

    dx: float = 0.0
    dy: float = 0.0
    rotation: float = 0.0
    scale: float = 1.0
    opacity: float = 1.0

    def merge(self, other: "Deltas") -> "Deltas":
        return Deltas(
            dx=self.dx + other.dx,
            dy=self.dy + other.dy,
            rotation=self.rotation + other.rotation,
            scale=self.scale * other.scale,
            opacity=self.opacity * other.opacity,
        )


NEUTRAL = Deltas()


@dataclass(frozen=True)
class ResolvedAction:
    """An action with every default filled in. The compiler builds these before sampling."""

    type: str
    start: float
    duration: float
    direction: str
    distance: float
    intensity: float
    repeat: int
    target: tuple[float, float] | None
    to: str | None

    @property
    def end(self) -> float:
        return self.start + self.duration

    @property
    def vector(self) -> tuple[float, float]:
        return _AXIS.get(self.direction, (1.0, 0.0))


def resolve_action(
    action: CartoonAction,
    *,
    scene_duration: float,
    target: tuple[float, float] | None = None,
) -> ResolvedAction:
    kind = action.type
    duration = action.duration if action.duration is not None else DEFAULT_DURATIONS.get(kind, 1.0)
    remaining = max(0.05, scene_duration - action.start)
    return ResolvedAction(
        type=kind,
        start=action.start,
        duration=min(duration, remaining),
        direction=action.direction or DEFAULT_DIRECTIONS.get(kind, "right"),
        distance=action.distance if action.distance is not None else DEFAULT_DISTANCES.get(kind, 0.2),
        intensity=action.intensity,
        repeat=action.repeat if action.repeat is not None else DEFAULT_REPEATS.get(kind, 1),
        target=target,
        to=action.to,
    )


def deltas_at(action: ResolvedAction, time: float) -> Deltas:
    """Offset contributed by one action at an absolute scene time."""
    primitive = _PRIMITIVES.get(action.type)
    if primitive is None:
        return NEUTRAL
    if time <= action.start:
        # An entrance holds its starting offset beforehand, so a character who walks in at
        # 2s waits off frame instead of standing in shot and teleporting away.
        return primitive(action, 0.0, 0.0) if action.type in _PRE_HOLD else NEUTRAL
    local = min(time - action.start, action.duration)
    progress = 1.0 if action.duration <= 0 else local / action.duration
    return primitive(action, local, progress)


def compose(actions: list[ResolvedAction], time: float) -> Deltas:
    total = NEUTRAL
    for action in actions:
        total = total.merge(deltas_at(action, time))
    return total


def sample_times(actions: list[ResolvedAction], *, start: float, duration: float) -> list[float]:
    """Times, relative to the layer start, where the composed offset has to be measured.

    Only action windows need dense samples. Offsets hold their last value afterwards, so the
    span between windows needs nothing but the endpoints.
    """
    end = start + duration
    times = {0.0, round(duration, 6)}
    for action in actions:
        window = max(action.duration, 1.0 / SAMPLE_RATE)
        count = min(MAX_SAMPLES_PER_ACTION, max(2, int(round(window * SAMPLE_RATE))))
        step = window / count
        for index in range(count + 1):
            moment = action.start + index * step
            if start <= moment <= end:
                times.add(round(moment - start, 6))
        if start <= action.end <= end:
            times.add(round(action.end - start, 6))
    return sorted(value for value in times if 0 <= value <= duration + 1e-9)


# Easing helpers ------------------------------------------------------------


def _smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _ease_out(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) * (1 - u)


def _ease_in(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u


def _bump(u: float) -> float:
    """0 at both ends, 1 in the middle."""
    return math.sin(math.pi * min(1.0, max(0.0, u)))


def _decay(u: float, rate: float = 4.0) -> float:
    return math.exp(-rate * min(1.0, max(0.0, u)))


# Primitives ----------------------------------------------------------------


def _bob(action: ResolvedAction, progress: float, height: float, steps: float) -> float:
    if progress >= 1:
        return 0.0
    return -abs(math.sin(math.pi * steps * progress)) * height * action.intensity


def _walk(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    travel = action.distance * _smooth(progress)
    steps = max(2.0, round(action.duration * 2))
    return Deltas(
        dx=axis_x * travel,
        dy=axis_y * travel + _bob(action, progress, 0.012, steps),
        rotation=math.sin(math.pi * steps * progress) * 1.5 * action.intensity if progress < 1 else 0.0,
    )


def _walk_in(action: ResolvedAction, local: float, progress: float) -> Deltas:
    # direction names the side the character comes from, so the offset starts on that side.
    axis_x, axis_y = action.vector
    remaining = action.distance * (1 - _smooth(progress))
    steps = max(2.0, round(action.duration * 2))
    return Deltas(
        dx=axis_x * remaining,
        dy=axis_y * remaining + _bob(action, progress, 0.012, steps),
        rotation=math.sin(math.pi * steps * progress) * 1.5 * action.intensity if progress < 1 else 0.0,
    )


def _walk_out(action: ResolvedAction, local: float, progress: float) -> Deltas:
    return _walk(action, local, progress)


def _run(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    travel = action.distance * _smooth(progress)
    steps = max(3.0, round(action.duration * 4))
    lean = axis_x * 6 * action.intensity * (1 if progress < 1 else 0)
    return Deltas(
        dx=axis_x * travel,
        dy=axis_y * travel + _bob(action, progress, 0.02, steps),
        rotation=lean,
    )


def _enter(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    remaining = action.distance * (1 - _ease_out(progress))
    return Deltas(dx=axis_x * remaining, dy=axis_y * remaining, opacity=min(1.0, 0.15 + _ease_out(progress)))


def _exit(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    travel = action.distance * _ease_in(progress)
    return Deltas(dx=axis_x * travel, dy=axis_y * travel, opacity=max(0.0, 1 - _ease_in(progress)))


def _slide(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    travel = action.distance * _smooth(progress)
    return Deltas(dx=axis_x * travel, dy=axis_y * travel)


def _jump(action: ResolvedAction, local: float, progress: float) -> Deltas:
    height = 0.16 * action.intensity
    hops = max(1, action.repeat)
    phase = (progress * hops) % 1.0 if progress < 1 else 1.0
    if progress >= 1:
        return NEUTRAL
    if phase < 0.18:
        crouch = phase / 0.18
        return Deltas(dy=0.02 * action.intensity * crouch, scale=1 - 0.06 * action.intensity * crouch)
    if phase < 0.86:
        flight = (phase - 0.18) / 0.68
        return Deltas(dy=-height * math.sin(math.pi * flight), scale=1 + 0.04 * action.intensity * math.sin(math.pi * flight))
    land = (phase - 0.86) / 0.14
    return Deltas(dy=0.02 * action.intensity * (1 - land), scale=1 - 0.08 * action.intensity * (1 - land))


def _bounce(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    hops = max(1, action.repeat)
    envelope = 1 - 0.35 * progress
    lift = abs(math.sin(math.pi * hops * progress)) * 0.09 * action.intensity * envelope
    return Deltas(dy=-lift, scale=1 + 0.03 * action.intensity * envelope * math.sin(math.pi * hops * progress))


def _squash(action: ResolvedAction, local: float, progress: float) -> Deltas:
    return Deltas(scale=1 - 0.18 * action.intensity * _bump(progress))


def _stretch(action: ResolvedAction, local: float, progress: float) -> Deltas:
    return Deltas(scale=1 + 0.18 * action.intensity * _bump(progress))


def _shake(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    cycles = max(1, action.repeat)
    return Deltas(dx=math.sin(2 * math.pi * cycles * progress) * 0.018 * action.intensity * (1 - progress))


def _recoil(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    axis_x, axis_y = action.vector
    swing = 0.05 * action.intensity * _decay(progress, 3.5) * math.cos(2 * math.pi * 1.25 * progress)
    return Deltas(dx=axis_x * swing, dy=axis_y * swing, rotation=-axis_x * 4 * action.intensity * _decay(progress, 3.5))


def _lean(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, _ = action.vector
    return Deltas(rotation=axis_x * 8 * action.intensity * _smooth(progress), dx=axis_x * 0.01 * _smooth(progress))


def _nod(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    cycles = max(1, action.repeat)
    wave = math.sin(2 * math.pi * cycles * progress)
    return Deltas(dy=-0.014 * action.intensity * wave, rotation=2.5 * action.intensity * wave)


def _shake_head(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    cycles = max(1, action.repeat)
    wave = math.sin(2 * math.pi * cycles * progress)
    return Deltas(dx=0.012 * action.intensity * wave, rotation=5 * action.intensity * wave)


def _point(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, _ = action.vector
    return Deltas(rotation=axis_x * 6 * action.intensity * _smooth(progress), dx=axis_x * 0.02 * _smooth(progress))


def _wave(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    cycles = max(1, action.repeat)
    envelope = _bump(progress)
    return Deltas(
        rotation=math.sin(2 * math.pi * cycles * progress) * 7 * action.intensity * envelope,
        dy=-0.006 * action.intensity * envelope,
    )


def _sit(action: ResolvedAction, local: float, progress: float) -> Deltas:
    settle = _smooth(progress)
    return Deltas(dy=0.06 * action.intensity * settle, scale=1 - 0.12 * action.intensity * settle)


def _stand(action: ResolvedAction, local: float, progress: float) -> Deltas:
    rise = 1 - _smooth(progress)
    return Deltas(dy=0.06 * action.intensity * rise, scale=1 - 0.12 * action.intensity * rise)


def _turn(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, _ = action.vector
    return Deltas(rotation=axis_x * 12 * action.intensity * _smooth(progress))


def _talk(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    beats = max(1, action.repeat) * max(1.0, action.duration)
    return Deltas(dy=-0.005 * action.intensity * abs(math.sin(math.pi * beats * progress)))


def _blink(action: ResolvedAction, local: float, progress: float) -> Deltas:
    # The eyes are swapped by the compiler when an eyes part exists. The body does not move.
    return NEUTRAL


def _look(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    settle = _smooth(progress)
    return Deltas(
        dx=axis_x * 0.012 * action.intensity * settle,
        dy=axis_y * 0.012 * action.intensity * settle,
        rotation=axis_x * 3 * action.intensity * settle,
    )


def _look_left(action: ResolvedAction, local: float, progress: float) -> Deltas:
    return _look(_with_direction(action, "left"), local, progress)


def _look_right(action: ResolvedAction, local: float, progress: float) -> Deltas:
    return _look(_with_direction(action, "right"), local, progress)


def _expression_change(action: ResolvedAction, local: float, progress: float) -> Deltas:
    # The compiler cross fades the two expression assets. The body does not move.
    return NEUTRAL


def _surprised(action: ResolvedAction, local: float, progress: float) -> Deltas:
    lift = _bump(progress)
    return Deltas(dy=-0.03 * action.intensity * lift, scale=1 + 0.12 * action.intensity * lift)


def _angry(action: ResolvedAction, local: float, progress: float) -> Deltas:
    settle = _smooth(progress)
    tremble = math.sin(2 * math.pi * 9 * progress) * 0.007 * action.intensity * (1 - progress)
    return Deltas(dx=tremble, scale=1 + 0.06 * action.intensity * settle, rotation=3 * action.intensity * settle)


def _confused(action: ResolvedAction, local: float, progress: float) -> Deltas:
    wobble = math.sin(2 * math.pi * 0.75 * progress)
    return Deltas(rotation=7 * action.intensity * wobble * (1 - progress * 0.3), dy=-0.006 * action.intensity * abs(wobble))


def _happy(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    hops = max(2, action.repeat)
    lift = abs(math.sin(math.pi * hops * progress)) * 0.06 * action.intensity
    return Deltas(dy=-lift, rotation=math.sin(2 * math.pi * hops * progress) * 3 * action.intensity)


def _sad(action: ResolvedAction, local: float, progress: float) -> Deltas:
    settle = _smooth(progress)
    return Deltas(dy=0.03 * action.intensity * settle, scale=1 - 0.05 * action.intensity * settle, rotation=2 * action.intensity * settle)


def _shocked(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, _ = action.vector
    spike = _decay(progress, 3.0)
    return Deltas(
        dx=axis_x * 0.06 * action.intensity * spike,
        scale=1 + 0.15 * action.intensity * spike,
        rotation=-axis_x * 5 * action.intensity * spike,
    )


def _laugh(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    cycles = max(2, action.repeat)
    wave = math.sin(2 * math.pi * cycles * progress)
    return Deltas(dy=-0.02 * action.intensity * abs(wave), rotation=4 * action.intensity * wave)


def _cry(action: ResolvedAction, local: float, progress: float) -> Deltas:
    settle = _smooth(min(1.0, progress * 3))
    cycles = max(2, action.repeat)
    shudder = math.sin(2 * math.pi * cycles * progress) * 0.005 * action.intensity
    return Deltas(dy=0.03 * action.intensity * settle + shudder, scale=1 - 0.04 * action.intensity * settle, rotation=3 * action.intensity * settle)


def _impact(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    hit = _decay(progress, 6.0)
    return Deltas(
        dx=axis_x * 0.05 * action.intensity * hit,
        dy=axis_y * 0.05 * action.intensity * hit,
        scale=1 - 0.1 * action.intensity * hit,
    )


def _pop(action: ResolvedAction, local: float, progress: float) -> Deltas:
    if progress >= 1:
        return NEUTRAL
    if progress < 0.7:
        grow = _ease_out(progress / 0.7)
        return Deltas(scale=0.2 + 0.9 * grow, opacity=min(1.0, grow * 1.5))
    settle = (progress - 0.7) / 0.3
    return Deltas(scale=1.1 - 0.1 * _smooth(settle))


def _overshoot(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    travel = action.distance * _smooth(progress) * (1 + 0.12 * action.intensity * _bump(progress))
    return Deltas(dx=axis_x * travel, dy=axis_y * travel)


def _anticipation(action: ResolvedAction, local: float, progress: float) -> Deltas:
    axis_x, axis_y = action.vector
    pull = 0.04 * action.intensity * _bump(progress)
    return Deltas(dx=-axis_x * pull, dy=-axis_y * pull, rotation=-axis_x * 3 * action.intensity * _bump(progress))


def _with_direction(action: ResolvedAction, direction: str) -> ResolvedAction:
    return ResolvedAction(
        type=action.type,
        start=action.start,
        duration=action.duration,
        direction=direction,
        distance=action.distance,
        intensity=action.intensity,
        repeat=action.repeat,
        target=action.target,
        to=action.to,
    )


_PRIMITIVES: dict[str, Callable[[ResolvedAction, float, float], Deltas]] = {
    "walk": _walk,
    "walk_in": _walk_in,
    "walk_out": _walk_out,
    "run": _run,
    "enter": _enter,
    "exit": _exit,
    "slide": _slide,
    "jump": _jump,
    "bounce": _bounce,
    "squash": _squash,
    "stretch": _stretch,
    "shake": _shake,
    "recoil": _recoil,
    "lean": _lean,
    "nod": _nod,
    "shake_head": _shake_head,
    "point": _point,
    "wave": _wave,
    "sit": _sit,
    "stand": _stand,
    "turn": _turn,
    "talk": _talk,
    "blink": _blink,
    "look_left": _look_left,
    "look_right": _look_right,
    "look_at": _look,
    "expression_change": _expression_change,
    "surprised_reaction": _surprised,
    "angry_reaction": _angry,
    "confused_reaction": _confused,
    "happy_reaction": _happy,
    "sad_reaction": _sad,
    "shocked_reaction": _shocked,
    "laugh": _laugh,
    "cry": _cry,
    "impact": _impact,
    "pop": _pop,
    "overshoot": _overshoot,
    "anticipation": _anticipation,
}

# Every advertised action has an implementation, and nothing is implemented in secret.
assert set(_PRIMITIVES) == set(ACTION_SPECS), "cartoon action vocabulary and primitives disagree"
