"""Asset tools."""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def register_asset(
        project_id: str,
        path: str,
        asset_id: str | None = None,
        replace: bool = False,
        semantic_type: str | None = None,
    ) -> dict:
        """Purpose: Copy an allowed local file into the project and inspect it.

        When to use: The user has a PNG, JPEG, WebP, SVG, video, or audio file to use in scenes.
        Arguments: project_id; path inside imports/ or demos/assets/; optional asset_id; replace=true to swap bytes for an existing id; optional semantic_type.
        Returns: Public asset record with technical_metadata, preview resource URIs, and asset_id. The internal blob path is not returned.
        Side effects: Stores bytes by SHA-256, writes asset JSON, and extracts video keyframes locally.
        Cache behavior: replace=true changes the hash, so the next render rerenders only scenes that reference this asset.
        Errors: PATH_NOT_ALLOWED, UNSUPPORTED_FORMAT, ASSET_EXISTS, ASSET_NOT_FOUND, INVALID_METADATA.
        Example: register_asset(project_id="project_01", path="imports/product.png", asset_id="product_png")
        Cartoon: semantic_type labels the role, such as background, prop, or speech_bubble. It is your label and is not verified. Use register_character_asset for character artwork.
        """
        return call(
            ctx.assets.register,
            project_id,
            path,
            asset_id=asset_id,
            replace=replace,
            semantic_type=semantic_type,
        )

    @mcp.tool()
    def get_asset(project_id: str, asset_id: str) -> dict:
        """Purpose: Read technical metadata and any semantic notes for one asset.

        When to use: Before you decide how to use an asset in a scene.
        Arguments: project_id, asset_id.
        Returns: Asset record. semantic_metadata is unverified caller input. Absence means nobody has described the pixels.
        Side effects: None.
        Cache behavior: None.
        Errors: ASSET_NOT_FOUND.
        Example: get_asset(project_id="project_01", asset_id="product_png")
        """
        return call(lambda: ctx.assets.public(ctx.assets.get(project_id, asset_id)))

    @mcp.tool()
    def list_assets(project_id: str) -> dict:
        """Purpose: List assets registered on a project.

        When to use: You need to choose asset_id values for layers.
        Arguments: project_id.
        Returns: {"assets": [...]}.
        Side effects: None.
        Cache behavior: None.
        Errors: PROJECT_NOT_FOUND.
        Example: list_assets(project_id="project_01")
        """
        return call(lambda: {"assets": ctx.assets.list_assets(project_id)})

    @mcp.tool()
    def update_asset_metadata(project_id: str, asset_id: str, semantic: dict) -> dict:
        """Purpose: Store your own semantic notes on an asset.

        When to use: After you have actually inspected a preview, or the user told you what the file is.
        Arguments: project_id, asset_id, semantic object (description, subjects, recommended_usage, visual_style).
        Returns: The asset record. technical_metadata is unchanged.
        Side effects: Writes semantic_metadata only. This server does not treat it as ground truth.
        Cache behavior: Semantic notes are not part of the visual cache key.
        Errors: ASSET_NOT_FOUND, INVALID_METADATA.
        Example: update_asset_metadata(project_id="project_01", asset_id="product_png", semantic={"description": "User-provided product still."})
        """
        return call(ctx.assets.update_metadata, project_id, asset_id, semantic)

    @mcp.tool()
    def delete_asset(project_id: str, asset_id: str) -> dict:
        """Purpose: Remove an asset record that no scene references.

        When to use: The user wants an unused file dropped from the project.
        Arguments: project_id, asset_id.
        Returns: {"deleted": asset_id} or ASSET_IN_USE with scene_ids.
        Side effects: Deletes the asset JSON. The content-addressed blob remains if another record shares the hash.
        Cache behavior: Refused when scenes still depend on the asset, so cached renders stay valid.
        Errors: ASSET_IN_USE, ASSET_NOT_FOUND.
        Example: delete_asset(project_id="project_01", asset_id="unused_logo")
        """

        def _delete() -> dict:
            users = ctx.asset_users(project_id, asset_id)
            return ctx.assets.delete(project_id, asset_id, users)

        return call(_delete)

    @mcp.tool()
    def get_asset_preview(project_id: str, asset_id: str) -> dict:
        """Purpose: List visual resources for an asset.

        When to use: You need to look at an image, or at posters and keyframes for a video.
        Arguments: project_id, asset_id.
        Returns: Resource URIs plus a visual_access warning. This tool does not describe the picture.
        Side effects: None. Keyframes were generated at registration.
        Cache behavior: None.
        Errors: ASSET_NOT_FOUND.
        Example: get_asset_preview(project_id="project_01", asset_id="background_mp4")
        """
        return call(ctx.assets.preview_info, project_id, asset_id)

    @mcp.tool()
    def get_asset_keyframes(project_id: str, asset_id: str) -> dict:
        """Purpose: List poster, keyframe, and contact-sheet resources for a video.

        When to use: You need representative frames before deciding how to cut a clip.
        Arguments: project_id, asset_id.
        Returns: Frame names and rendering:// resource URIs. Images and audio return an empty frame list.
        Side effects: None.
        Cache behavior: None.
        Errors: ASSET_NOT_FOUND.
        Example: get_asset_keyframes(project_id="project_01", asset_id="clip")
        """
        return call(ctx.assets.keyframe_info, project_id, asset_id)
