"""Machine-readable capabilities shared by MCP resources and the docs."""

from __future__ import annotations

from app.renderer.cartoon.names import (
    ACTION_FAMILIES,
    ACTION_SPECS,
    ASSET_ROLES,
    BACKGROUND_LAYERS,
    CAMERA_MOVES,
    CAMERA_SHOTS,
    CARTOON_COMPILER_VERSION,
    CHARACTER_PARTS,
    DIALOGUE_ANIMATIONS,
    DIRECTIONS,
)
from app.renderer.version import RENDERER_VERSION

CAPABILITIES = {
    "renderer_version": RENDERER_VERSION,
    "modes": {"standard": True, "cartoon": True},
    "default_mode": "standard",
    "layers": ["image", "video", "svg", "text", "shape"],
    "supported_layer_types": ["image", "video", "svg", "text", "shape"],
    "motion": [
        "fade",
        "fade_up",
        "fade_down",
        "fade_left",
        "fade_right",
        "slide_left",
        "slide_right",
        "slide_up",
        "slide_down",
        "scale_in",
        "scale_out",
        "slow_push",
        "slow_pull",
        "pan_left",
        "pan_right",
        "pan_up",
        "pan_down",
        "rotate",
        "orbit",
        "parallax",
        "ken_burns",
        "float",
        "drift",
        "shake",
        "handheld",
    ],
    "animations": [
        "fade",
        "fade_up",
        "fade_down",
        "fade_left",
        "fade_right",
        "scale_in",
        "scale_out",
        "slide_left",
        "slide_right",
        "slide_up",
        "slide_down",
        "rotate",
        "ken_burns",
        "parallax",
        "slow_push",
        "slow_pull",
        "pan_left",
        "pan_right",
        "pan_up",
        "pan_down",
        "orbit",
        "float",
        "drift",
        "shake",
        "handheld",
        "word_reveal",
        "character_reveal",
        "typewriter",
    ],
    "easing": ["linear", "ease_in", "ease_out", "ease_in_out", "spring"],
    "effects": [
        "blur",
        "motion_blur",
        "brightness",
        "contrast",
        "saturation",
        "grayscale",
        "sepia",
        "vignette",
        "glow",
        "bloom",
        "drop_shadow",
        "grain",
        "color_tint",
    ],
    "transitions": ["cut", "fade", "crossfade", "slide", "zoom", "blur", "whip", "dip_to_color"],
    "blend_modes": ["normal", "multiply", "screen", "overlay", "soft_light"],
    "masks": ["rect", "rounded_rect", "circle", "ellipse"],
    "aspect_ratios": ["9:16", "16:9", "1:1", "4:5"],
    "presets": {
        "instagram_reels": {"width": 1080, "height": 1920, "aspect_ratio": "9:16"},
        "youtube_shorts": {"width": 1080, "height": 1920, "aspect_ratio": "9:16"},
        "youtube": {"width": 1920, "height": 1080, "aspect_ratio": "16:9"},
        "landscape": {"width": 1920, "height": 1080, "aspect_ratio": "16:9"},
        "square": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"},
        "portrait": {"width": 1080, "height": 1350, "aspect_ratio": "4:5"},
    },
    "supported_assets": ["png", "jpeg", "webp", "svg", "mp4", "mov", "webm", "mp3", "wav", "aac"],
    "coordinates": "x=0 is left, x=1 is right, y=0 is top, y=1 is bottom",
    "semantic_metadata": "Caller-supplied only. This server never infers what an asset depicts.",
    "audio": {
        "optional": True,
        "music": True,
        "voiceover": True,
        "sound_effects": True,
        "ducking": True,
    },
    "video": {
        "slow_motion": True,
        "speed_ramping": True,
        "playback_rates": [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2],
    },
    "keyframes": [
        "position",
        "scale",
        "rotation",
        "opacity",
        "blur",
        "brightness",
        "contrast",
        "saturation",
        "volume",
        "playback_rate",
    ],
    "cartoon_capabilities": {
        "characters": True,
        "expressions": True,
        "poses": True,
        "actions": True,
        "dialogue": True,
        "camera": True,
        "props": True,
        "cartoon_animation_primitives": True,
        "layered_backgrounds": True,
        "mixed_content": True,
    },
    "cartoon": {
        "requires": "project mode='cartoon'",
        "compiler_version": CARTOON_COMPILER_VERSION,
        "actions": list(ACTION_FAMILIES["movement"] + ACTION_FAMILIES["body"] + ACTION_FAMILIES["face"] + ACTION_FAMILIES["reaction"] + ACTION_FAMILIES["effect"]),
        "action_families": {family: list(names) for family, names in ACTION_FAMILIES.items()},
        "action_parameters": {
            name: ["start", "duration", *spec["parameters"]] for name, spec in sorted(ACTION_SPECS.items())
        },
        "directions": list(DIRECTIONS),
        "camera_shots": CAMERA_SHOTS,
        "camera_animations": list(CAMERA_MOVES),
        "dialogue_animations": list(DIALOGUE_ANIMATIONS),
        "asset_roles": list(ASSET_ROLES),
        "character_parts": list(CHARACTER_PARTS),
        "background_layers": list(BACKGROUND_LAYERS),
        "asset_resolution_order": [
            "assets.variants['<pose>:<expression>']",
            "assets.expressions['<expression>']",
            "assets.poses['<pose>']",
            "assets.base",
        ],
        "notes": [
            "Cartoon scenes compile into the same layers, renderer, cache, and versioning as standard scenes.",
            "This server does not generate artwork. Register character, background, and prop files you produced elsewhere.",
            "Dialogue stays editable data. It is never baked into a character asset.",
        ],
    },
}

EFFECTS = {
    "blur": "Gaussian blur in pixels, 0 to 40. Number or keyframes.",
    "motion_blur": "Velocity-scaled blur from 0 to 1. An approximation, not optical flow.",
    "brightness": "CSS brightness multiplier, 0 to 3. Number or keyframes.",
    "contrast": "CSS contrast multiplier, 0 to 3. Number or keyframes.",
    "saturation": "CSS saturation multiplier, 0 to 3. Number or keyframes.",
    "grayscale": "0 to 1.",
    "sepia": "0 to 1.",
    "vignette": "0 to 1, radial darkening on the layer.",
    "glow": "0 to 1, light drop shadow.",
    "bloom": "0 to 1, extra brightness and soft highlight.",
    "drop_shadow": "Boolean fixed shadow.",
    "grain": "0 to 1, deterministic noise tile.",
    "color_tint": {"color": "#RRGGBB", "amount": "0 to 1"},
}

SCENE_EXAMPLE = {
    "scene_id": "scene_01",
    "duration": 4,
    "background": {"type": "color", "value": "#000000"},
    "transition_out": {"type": "crossfade", "duration": 0.4},
    "layers": [
        {
            "id": "hero",
            "type": "image",
            "asset_id": "photo_01",
            "start": 0,
            "duration": 4,
            "z_index": 10,
            "position": {"x": 0.5, "y": 0.5},
            "scale": {"from": 0.9, "to": 1.05},
            "animation": {"type": "slow_push"},
        }
    ],
}

CHARACTER_EXAMPLE = {
    "character_id": "raj",
    "name": "Raj",
    "description": "Backend engineer, permanently one incident away from the edge.",
    "traits": ["sarcastic", "loyal", "tired"],
    "visual_style": "2D flat comic, thick outlines",
    "default_position": {"x": 0.35, "y": 0.78},
    "default_size": 0.55,
    "default_anchor": {"x": 0.5, "y": 1},
    "assets": {
        "base": "raj_base",
        "expressions": {"angry": "raj_angry", "shocked": "raj_shocked"},
        "poses": {"standing": "raj_standing"},
        "parts": {"mouth_open": "raj_mouth_open", "mouth_closed": "raj_mouth_closed"},
    },
}

CARTOON_SCENE_EXAMPLE = {
    "scene_id": "scene_03",
    "duration": 8,
    "cartoon": {
        "background": {"asset_id": "office_night", "parallax": 0.2},
        "characters": [
            {
                "character_id": "raj",
                "expression": "angry",
                "position": {"x": 0.32, "y": 0.78},
                "actions": [
                    {"action_id": "act_1", "type": "walk_in", "direction": "left", "duration": 1.5},
                    {"action_id": "act_2", "type": "talk", "start": 2, "duration": 2},
                ],
            },
            {"character_id": "sam", "expression": "nervous", "position": {"x": 0.68, "y": 0.78}},
        ],
        "dialogue": [
            {
                "dialogue_id": "d1",
                "character_id": "raj",
                "text": "WHO BROKE PRODUCTION?",
                "start": 2,
                "duration": 2,
            },
            {
                "dialogue_id": "d2",
                "character_id": "sam",
                "text": "It was a small change...",
                "start": 4.5,
                "duration": 2.5,
            },
        ],
        "camera": {"shot": "two_shot", "animation": {"type": "push_in", "start": 2, "duration": 2}},
        "props": [{"prop_id": "laptop", "asset_id": "laptop_svg", "position": {"x": 0.5, "y": 0.86}}],
    },
    "layers": [],
}

INSTRUCTIONS = """
You are connected to reel-production, a deterministic video production engine.
You are the creative director. This server does not run an LLM and does not generate images, video, or voice.

The user describes the reel. You decide the story, scene count, timing, motion, effects, and audio.
This server stores state, validates a declarative scene graph, renders, caches, and versions.
It can make travel reels, product films, event recaps, explainers, birthday videos, visualizers, and ads.
Do not assume the output is a marketing video.

Understand before rendering:
inspect assets, read rendering://capabilities, decide what is missing, ask the user only when duration, aspect ratio, or purpose would change the cut, then build scenes, validate, render a preview, and iterate.
If the request already names duration and format, do not ask a clarifying question.
If something visual is missing, generate or obtain it with your own tools and register_asset. This server has no image generator.

Use asset_id values, never filesystem paths, after register_asset.
technical_metadata is measured. semantic_metadata is unverified text you stored. It is not ground truth.
If a client cannot show an image resource, you have not seen the pixels. Do not invent what the asset depicts.

Submit whole scene specifications to create_scene, update_scene, or upsert_scene.
Send JSON only. Never send executable code.
Audio is optional. A project with no music, voiceover, or sound effects is valid.

Projects have a mode. mode='standard' is the default general-purpose engine and is unchanged.
mode='cartoon' enables character production on the same engine: characters, poses, expressions, dialogue, actions, camera, and props.
Choose cartoon mode when the user asks for a cartoon, an animated story, or talking characters. Otherwise stay standard.
Cartoon tools refuse to run on a standard project instead of switching the mode for you.
A cartoon project still accepts ordinary images, video, text, shapes, effects, and audio in the same scene.
Read rendering://cartoon-schema, rendering://character-schema, and rendering://cartoon-animation-primitives before directing a cartoon.
Direct the animation with named actions and camera moves. Do not compute keyframes yourself.

Changing one scene rerenders only that scene when the visual cache key changes.
Audio is mixed at assembly time and does not rerender cached pictures.
Call create_version at meaningful checkpoints. restore_version keeps newer versions.
""".strip()
