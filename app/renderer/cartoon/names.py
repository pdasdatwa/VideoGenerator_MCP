"""The cartoon vocabulary. Capabilities, validation, and the compiler all read these names."""

from __future__ import annotations

# Bump when a primitive changes shape. Cartoon cache keys include this value.
CARTOON_COMPILER_VERSION = "1.0.0"

# Every action a client may direct, with the parameters this implementation honours.
# start and duration are seconds inside the scene and are accepted by every action.
ACTION_SPECS: dict[str, dict[str, object]] = {
    "walk": {
        "family": "movement",
        "parameters": ["direction", "distance", "intensity"],
        "summary": "Travel across the frame with a walking bob. direction is left or right.",
    },
    "walk_in": {
        "family": "movement",
        "parameters": ["direction", "distance", "intensity"],
        "summary": "Walk in from off frame to the placed position. direction is the side entered from.",
    },
    "walk_out": {
        "family": "movement",
        "parameters": ["direction", "distance", "intensity"],
        "summary": "Walk from the placed position off frame. direction is the side exited to.",
    },
    "run": {
        "family": "movement",
        "parameters": ["direction", "distance", "intensity"],
        "summary": "Like walk with a faster bob and a forward lean.",
    },
    "enter": {
        "family": "movement",
        "parameters": ["direction", "distance"],
        "summary": "Slide in from off frame and fade up. No walk bob.",
    },
    "exit": {
        "family": "movement",
        "parameters": ["direction", "distance"],
        "summary": "Slide off frame and fade out. No walk bob.",
    },
    "slide": {
        "family": "movement",
        "parameters": ["direction", "distance"],
        "summary": "Move by distance in one direction and stay there.",
    },
    "jump": {
        "family": "movement",
        "parameters": ["intensity", "repeat"],
        "summary": "Anticipate, leave the ground, squash on landing.",
    },
    "bounce": {
        "family": "body",
        "parameters": ["intensity", "repeat"],
        "summary": "Repeated vertical bounce that settles at the placed position.",
    },
    "squash": {
        "family": "body",
        "parameters": ["intensity"],
        "summary": "Compress vertically and widen, then return.",
    },
    "stretch": {
        "family": "body",
        "parameters": ["intensity"],
        "summary": "Extend vertically and narrow, then return.",
    },
    "shake": {
        "family": "body",
        "parameters": ["intensity", "repeat"],
        "summary": "Rapid horizontal tremor that decays to zero.",
    },
    "recoil": {
        "family": "body",
        "parameters": ["direction", "intensity"],
        "summary": "Snap away from an impact and settle back.",
    },
    "lean": {
        "family": "body",
        "parameters": ["direction", "intensity"],
        "summary": "Tilt toward one side and hold.",
    },
    "nod": {
        "family": "body",
        "parameters": ["intensity", "repeat"],
        "summary": "Vertical agreement nod.",
    },
    "shake_head": {
        "family": "body",
        "parameters": ["intensity", "repeat"],
        "summary": "Horizontal disagreement shake.",
    },
    "point": {
        "family": "body",
        "parameters": ["direction", "target", "intensity"],
        "summary": "Lean and rotate toward a direction, a point, or another character.",
    },
    "wave": {
        "family": "body",
        "parameters": ["intensity", "repeat"],
        "summary": "Rocking wave built from a rotation oscillation.",
    },
    "sit": {
        "family": "body",
        "parameters": ["intensity"],
        "summary": "Lower and compress into a seated offset.",
    },
    "stand": {
        "family": "body",
        "parameters": ["intensity"],
        "summary": "Rise from a seated offset to full height.",
    },
    "turn": {
        "family": "body",
        "parameters": ["direction", "intensity"],
        "summary": "Rotate in place toward a side and hold. Register a pose or variant asset for a real turnaround.",
    },
    "talk": {
        "family": "face",
        "parameters": ["intensity", "repeat"],
        "summary": "Speaking bob. Swaps mouth_open and mouth_closed parts when both are registered.",
    },
    "blink": {
        "family": "face",
        "parameters": ["repeat"],
        "summary": "Hides the eyes_open part in short beats. Requires an eyes part; otherwise a no-op warning.",
    },
    "look_left": {
        "family": "face",
        "parameters": ["intensity"],
        "summary": "Shift attention left with a small offset and tilt.",
    },
    "look_right": {
        "family": "face",
        "parameters": ["intensity"],
        "summary": "Shift attention right with a small offset and tilt.",
    },
    "look_at": {
        "family": "face",
        "parameters": ["target", "intensity"],
        "summary": "Turn toward a normalized point or another character in the scene.",
    },
    "expression_change": {
        "family": "face",
        "parameters": ["to", "intensity"],
        "summary": "Cross fade from the current expression asset to another registered expression.",
    },
    "surprised_reaction": {
        "family": "reaction",
        "parameters": ["intensity"],
        "summary": "Pop up and back with a scale overshoot.",
    },
    "angry_reaction": {
        "family": "reaction",
        "parameters": ["intensity"],
        "summary": "Lean in, scale up, and tremble.",
    },
    "confused_reaction": {
        "family": "reaction",
        "parameters": ["intensity"],
        "summary": "Slow head tilt one way then the other.",
    },
    "happy_reaction": {
        "family": "reaction",
        "parameters": ["intensity"],
        "summary": "Two light hops with a rotation lilt.",
    },
    "sad_reaction": {
        "family": "reaction",
        "parameters": ["intensity"],
        "summary": "Sink down and compress, then hold low.",
    },
    "shocked_reaction": {
        "family": "reaction",
        "parameters": ["intensity"],
        "summary": "Hard recoil backwards with a scale spike.",
    },
    "laugh": {
        "family": "reaction",
        "parameters": ["intensity", "repeat"],
        "summary": "Rocking bounce with a rotation wobble.",
    },
    "cry": {
        "family": "reaction",
        "parameters": ["intensity", "repeat"],
        "summary": "Slow shoulder shudder while sunk down.",
    },
    "impact": {
        "family": "effect",
        "parameters": ["direction", "intensity"],
        "summary": "Single hard displacement and squash on the hit frame.",
    },
    "pop": {
        "family": "effect",
        "parameters": ["intensity"],
        "summary": "Scale from nothing to slightly over size, then settle.",
    },
    "overshoot": {
        "family": "effect",
        "parameters": ["direction", "distance", "intensity"],
        "summary": "Travel past the target and ease back to it.",
    },
    "anticipation": {
        "family": "effect",
        "parameters": ["direction", "intensity"],
        "summary": "Pull back before moving forward. Use before a movement action.",
    },
}

ACTIONS: tuple[str, ...] = tuple(sorted(ACTION_SPECS))

ACTION_FAMILIES: dict[str, tuple[str, ...]] = {
    family: tuple(sorted(name for name, spec in ACTION_SPECS.items() if spec["family"] == family))
    for family in ("movement", "body", "face", "reaction", "effect")
}

# Shot presets resolve to a base camera zoom.
CAMERA_SHOTS: dict[str, float] = {
    "wide": 1.0,
    "medium": 1.25,
    "close_up": 1.6,
    "extreme_close_up": 2.2,
    "over_shoulder": 1.45,
    "two_shot": 1.1,
}

CAMERA_MOVES: dict[str, str] = {
    "hold": "Keep the framing still for the whole scene.",
    "push_in": "Zoom in from the shot zoom toward a tighter framing.",
    "pull_out": "Zoom out from the shot zoom toward a wider framing.",
    "pan_left": "Slide the view left across the scene.",
    "pan_right": "Slide the view right across the scene.",
    "tilt_up": "Slide the view up across the scene.",
    "tilt_down": "Slide the view down across the scene.",
    "shake": "Decaying handheld tremor on the whole frame.",
}

DIRECTIONS: tuple[str, ...] = ("left", "right", "up", "down")

# Caller-supplied asset roles. They organise the library; they are not verified by the server.
ASSET_ROLES: tuple[str, ...] = (
    "character_base",
    "character_pose",
    "character_expression",
    "character_accessory",
    "character_part",
    "background",
    "prop",
    "speech_bubble",
    "other",
)

# Character part names the compiler understands. Anything else is stored but not animated.
CHARACTER_PARTS: tuple[str, ...] = ("mouth_open", "mouth_closed", "eyes_open", "eyes_closed")

# Dialogue text animations. These are existing renderer motions, restricted to the text-safe set.
DIALOGUE_ANIMATIONS: tuple[str, ...] = (
    "fade",
    "fade_up",
    "fade_down",
    "scale_in",
    "word_reveal",
    "character_reveal",
    "typewriter",
)

BACKGROUND_LAYERS: tuple[str, ...] = ("background", "midground", "foreground")
