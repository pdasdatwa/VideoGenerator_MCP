"""Turning a (pose, expression) pair into one asset_id, and listing what a character references."""

from __future__ import annotations

from app.models.character import Character


def resolve_character_asset(character: Character, pose: str | None, expression: str | None) -> str | None:
    """variants['pose:expression'] -> expressions[expression] -> poses[pose] -> base."""
    assets = character.assets
    if pose and expression:
        variant = assets.variants.get(f"{pose}:{expression}")
        if variant:
            return variant
    if expression:
        found = assets.expressions.get(expression)
        if found:
            return found
    if pose:
        found = assets.poses.get(pose)
        if found:
            return found
    return assets.base


def referenced_character_assets(character: Character) -> list[str]:
    assets = character.assets
    ids: list[str] = []
    if assets.base:
        ids.append(assets.base)
    for group in (assets.poses, assets.expressions, assets.variants, assets.parts, assets.accessories):
        ids.extend(group.values())
    return ids
