"""Sequential scene timeline."""

from __future__ import annotations

from app.errors import MarketingError
from app.models.scene import Scene
from app.models.timeline import Timeline, TimelineEntry


def build_timeline(scene_order: list[str], scenes: dict[str, Scene]) -> Timeline:
    cursor = 0.0
    entries: list[TimelineEntry] = []
    ordered = [scenes[scene_id] for scene_id in scene_order]
    for index, scene in enumerate(ordered):
        transition = scene.transition_out
        if transition.type != "cut" and transition.duration > 0:
            if transition.duration >= scene.duration:
                raise MarketingError(
                    "INVALID_DURATION",
                    f"Transition on {scene.scene_id} is longer than the scene.",
                    suggested_action="Shorten transition_out.duration so it is less than the scene duration.",
                    scene_id=scene.scene_id,
                )
            if index + 1 < len(ordered) and transition.duration >= ordered[index + 1].duration:
                raise MarketingError(
                    "INVALID_DURATION",
                    f"Transition into the scene after {scene.scene_id} is longer than that scene.",
                    suggested_action="Shorten the transition or lengthen the next scene.",
                    scene_id=scene.scene_id,
                )
        entries.append(
            TimelineEntry(
                scene_id=scene.scene_id,
                index=index,
                start=round(cursor, 6),
                end=round(cursor + scene.duration, 6),
                duration=scene.duration,
            )
        )
        cursor += scene.duration
    return Timeline(entries=entries, duration=round(cursor, 6))
