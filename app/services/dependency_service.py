"""Which scenes depend on which assets and characters, derived from scene specifications."""

from __future__ import annotations

from app.models.character import Character
from app.models.scene import Scene
from app.renderer.cartoon.resolve import referenced_character_assets


class DependencyService:
    def graph(self, scenes: dict[str, Scene]) -> dict[str, list[dict[str, str]]]:
        """asset_id -> [{scene_id, layer_id}]."""
        edges: dict[str, list[dict[str, str]]] = {}
        for scene in scenes.values():
            if scene.background.asset_id:
                edges.setdefault(scene.background.asset_id, []).append(
                    {"scene_id": scene.scene_id, "layer_id": "background"}
                )
            for layer in scene.layers:
                if layer.asset_id:
                    edges.setdefault(layer.asset_id, []).append(
                        {"scene_id": scene.scene_id, "layer_id": layer.id}
                    )
            for track in scene.audio:
                edges.setdefault(track.asset_id, []).append(
                    {"scene_id": scene.scene_id, "layer_id": track.id}
                )
            for asset_id, source in _cartoon_edges(scene):
                edges.setdefault(asset_id, []).append({"scene_id": scene.scene_id, "layer_id": source})
        return edges

    def character_graph(self, scenes: dict[str, Scene]) -> dict[str, list[str]]:
        """character_id -> [scene_id]."""
        edges: dict[str, list[str]] = {}
        for scene in scenes.values():
            if scene.cartoon is None:
                continue
            for placement in scene.cartoon.characters:
                scene_ids = edges.setdefault(placement.character_id, [])
                if scene.scene_id not in scene_ids:
                    scene_ids.append(scene.scene_id)
        return edges

    def scenes_for_character(self, scenes: dict[str, Scene], character_id: str) -> list[str]:
        return self.character_graph(scenes).get(character_id, [])

    def scenes_for_character_asset(
        self,
        scenes: dict[str, Scene],
        characters: dict[str, Character],
        asset_id: str,
    ) -> list[str]:
        """Scenes that draw a character whose asset pack contains this file."""
        owners = [
            character_id
            for character_id, character in characters.items()
            if asset_id in referenced_character_assets(character)
        ]
        found: list[str] = []
        for character_id in owners:
            for scene_id in self.scenes_for_character(scenes, character_id):
                if scene_id not in found:
                    found.append(scene_id)
        return found

    def scenes_for_asset(self, scenes: dict[str, Scene], asset_id: str) -> list[str]:
        found = []
        for edge in self.graph(scenes).get(asset_id, []):
            if edge["scene_id"] not in found:
                found.append(edge["scene_id"])
        return found

    def visual_scenes_for_asset(self, scenes: dict[str, Scene], asset_id: str) -> list[str]:
        """Scenes whose picture cache depends on this asset. Audio-only uses are excluded."""
        found = []
        for scene in scenes.values():
            ids = []
            if scene.background.asset_id:
                ids.append(scene.background.asset_id)
            ids.extend(layer.asset_id for layer in scene.layers if layer.asset_id)
            ids.extend(asset for asset, _source in _cartoon_edges(scene))
            if asset_id in ids and scene.scene_id not in found:
                found.append(scene.scene_id)
        return found


def _cartoon_edges(scene: Scene) -> list[tuple[str, str]]:
    """Assets a cartoon block names directly, paired with where they came from."""
    spec = scene.cartoon
    if spec is None:
        return []
    edges: list[tuple[str, str]] = []
    if spec.background:
        for field_name in ("asset_id", "background", "midground", "foreground"):
            value = getattr(spec.background, field_name)
            if value:
                edges.append((value, f"cartoon_background_{field_name}"))
    for prop in spec.props:
        edges.append((prop.asset_id, f"prop_{prop.prop_id}"))
    for line in spec.dialogue:
        if line.style and line.style.bubble_asset_id:
            edges.append((line.style.bubble_asset_id, f"dialogue_{line.dialogue_id}"))
    return edges
