"""Character tools. Cartoon mode only."""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def create_character(project_id: str, character: dict) -> dict:
        """Purpose: Store one character identity that persists across every scene.

        When to use: Before placing a character in a scene. Create it once, then reference the character_id.
        Arguments: project_id; character object with character_id, name, and optional description, traits, visual_style, default_position, default_scale, default_size, default_anchor, assets, metadata.
        Returns: The stored character record.
        Side effects: Writes data/projects/<project_id>/characters/<character_id>.json.
        Cache behavior: No render cache is touched until a scene uses the character.
        Errors: CARTOON_MODE_REQUIRED, INVALID_CHARACTER, CHARACTER_EXISTS, INVALID_ASSET_REFERENCE.
        Example: create_character(project_id="project_01", character={"character_id": "raj", "name": "Raj", "traits": ["sarcastic"], "visual_style": "2D comic"})
        Note: You decide the personality and the artwork. This server stores, validates, animates, and renders.
        """
        return call(ctx.characters.create, project_id, character)

    @mcp.tool()
    def get_character(project_id: str, character_id: str) -> dict:
        """Purpose: Read one character, including which asset plays each pose and expression.

        When to use: Before editing a character or deciding which expression a scene can use.
        Arguments: project_id, character_id.
        Returns: The character record.
        Side effects: None.
        Cache behavior: None.
        Errors: CARTOON_MODE_REQUIRED, CHARACTER_NOT_FOUND.
        Example: get_character(project_id="project_01", character_id="raj")
        """
        return call(ctx.characters.get_dict, project_id, character_id)

    @mcp.tool()
    def list_characters(project_id: str) -> dict:
        """Purpose: List every character on a cartoon project.

        When to use: You are continuing a cartoon and need the existing cast.
        Arguments: project_id.
        Returns: {"project_id": ..., "characters": [...]}.
        Side effects: None.
        Cache behavior: None.
        Errors: CARTOON_MODE_REQUIRED, PROJECT_NOT_FOUND.
        Example: list_characters(project_id="project_01")
        """
        return call(ctx.characters.list_characters, project_id)

    @mcp.tool()
    def update_character(project_id: str, character_id: str, fields: dict) -> dict:
        """Purpose: Change a character's description, traits, defaults, or asset wiring.

        When to use: The character's look or resting placement changes for the whole film. For a single scene, use update_character_in_scene instead.
        Arguments: project_id, character_id; fields with any of name, description, traits, visual_style, default_position, default_scale, default_size, default_anchor, assets, metadata.
        Returns: The updated character.
        Side effects: Rewrites the character file.
        Cache behavior: Scenes that place this character recompile, so only those rerender. Other scenes stay cached.
        Errors: CARTOON_MODE_REQUIRED, CHARACTER_NOT_FOUND, INVALID_CHARACTER, INVALID_ASSET_REFERENCE.
        Example: update_character(project_id="project_01", character_id="raj", fields={"default_size": 0.6})
        """
        return call(ctx.characters.update, project_id, character_id, fields)

    @mcp.tool()
    def delete_character(project_id: str, character_id: str) -> dict:
        """Purpose: Remove a character from the project.

        When to use: The character is no longer part of the story and appears in no scene.
        Arguments: project_id, character_id.
        Returns: {"deleted": character_id}.
        Side effects: Deletes the character file. Registered assets stay in the asset library.
        Cache behavior: None. Scenes are untouched.
        Errors: CARTOON_MODE_REQUIRED, CHARACTER_NOT_FOUND, CHARACTER_IN_USE.
        Example: delete_character(project_id="project_01", character_id="raj")
        """
        return call(
            ctx.characters.delete,
            project_id,
            character_id,
            ctx.character_users(project_id, character_id),
        )

    @mcp.tool()
    def register_character_asset(
        project_id: str,
        character_id: str,
        path: str,
        role: str,
        key: str | None = None,
        asset_id: str | None = None,
        replace: bool = False,
    ) -> dict:
        """Purpose: Register artwork for a character and wire it to a pose, expression, part, or accessory.

        When to use: After you generated or obtained the image or SVG and wrote it into an allowed source directory. This server has no image generator.
        Arguments: project_id, character_id, path; role (character_base, character_pose, character_expression, character_part, character_accessory); key for everything except character_base; optional asset_id and replace.
        Returns: The registered asset, the updated asset map, and any warnings.
        Side effects: Registers the file through the ordinary asset registry and updates the character.
        Cache behavior: Replacing a file changes its sha256, so only scenes drawing that character rerender.
        Errors: CARTOON_MODE_REQUIRED, CHARACTER_NOT_FOUND, INVALID_METADATA, UNSUPPORTED_FORMAT, PATH_NOT_ALLOWED, ASSET_EXISTS.
        Example: register_character_asset(project_id="project_01", character_id="raj", path="imports/raj_angry.svg", role="character_expression", key="angry", asset_id="raj_angry")
        Note: key="standing:angry" registers a combined pose and expression variant, which wins over either single lookup.
        """
        return call(
            ctx.characters.register_asset,
            project_id,
            character_id,
            path,
            role=role,
            key=key,
            asset_id=asset_id,
            replace=replace,
        )

    @mcp.tool()
    def get_character_assets(project_id: str, character_id: str) -> dict:
        """Purpose: See every asset a character can draw with, and how a pose and expression resolve.

        When to use: Before assigning a pose or expression in a scene, so you only name ones that exist.
        Arguments: project_id, character_id.
        Returns: The asset map, known poses, expressions, variants, parts, the resolution order, and the public asset records.
        Side effects: None.
        Cache behavior: None.
        Errors: CARTOON_MODE_REQUIRED, CHARACTER_NOT_FOUND.
        Example: get_character_assets(project_id="project_01", character_id="raj")
        """
        return call(ctx.characters.get_assets, project_id, character_id)
