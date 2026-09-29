"""Cartoon scene tools: placement, dialogue, actions, camera, and props. Cartoon mode only.

These are narrow edits on top of the ordinary scene tools. create_scene and update_scene still
accept a whole cartoon block, and every one of these calls routes through the same validation.
"""

from __future__ import annotations

from typing import Any

from app.mcp.tooling import call
from app.services import AppContext


def register(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool()
    def add_character_to_scene(project_id: str, scene_id: str, character: dict) -> dict:
        """Purpose: Place an existing character in one scene.

        When to use: The character is on screen in this shot. Identity and artwork come from the character record, so you only describe this appearance.
        Arguments: project_id, scene_id; character object with character_id and optional pose, expression, position, scale, size, anchor, rotation, opacity, z_index, start, duration, accessories, actions.
        Returns: The updated scene with timeline placement.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders. Other scenes stay cached.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, CHARACTER_NOT_FOUND, DUPLICATE_CHARACTER, INVALID_POSE, INVALID_EXPRESSION.
        Example: add_character_to_scene(project_id="project_01", scene_id="scene_03", character={"character_id": "raj", "expression": "angry", "position": {"x": 0.35, "y": 0.78}})
        """
        return call(ctx.cartoon.add_character_to_scene, project_id, scene_id, character)

    @mcp.tool()
    def update_character_in_scene(project_id: str, scene_id: str, character_id: str, fields: dict) -> dict:
        """Purpose: Change how a character appears in one scene.

        When to use: "Make Raj angry in scene 4" or "move Sam closer to Raj". The character keeps its identity and assets.
        Arguments: project_id, scene_id, character_id; fields with any placement field such as pose, expression, position, scale, size, rotation, z_index, actions.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, CHARACTER_NOT_IN_SCENE, INVALID_EXPRESSION, INVALID_POSE.
        Example: update_character_in_scene(project_id="project_01", scene_id="scene_04", character_id="raj", fields={"expression": "angry"})
        """
        return call(ctx.cartoon.update_character_in_scene, project_id, scene_id, character_id, fields)

    @mcp.tool()
    def remove_character_from_scene(project_id: str, scene_id: str, character_id: str) -> dict:
        """Purpose: Take a character out of one scene.

        When to use: The character is no longer in that shot. The character record and its assets are kept.
        Arguments: project_id, scene_id, character_id.
        Returns: The updated scene.
        Side effects: Removes the placement and any dialogue spoken by that character in this scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, CHARACTER_NOT_IN_SCENE.
        Example: remove_character_from_scene(project_id="project_01", scene_id="scene_02", character_id="sam")
        """
        return call(ctx.cartoon.remove_character_from_scene, project_id, scene_id, character_id)

    @mcp.tool()
    def create_dialogue(project_id: str, scene_id: str, dialogue: dict) -> dict:
        """Purpose: Add one spoken line or caption to a scene.

        When to use: A character speaks, or you want a narrator caption. Text stays editable data and is never baked into artwork.
        Arguments: project_id, scene_id; dialogue object with dialogue_id, text, start, duration, optional character_id, style, animation.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, DIALOGUE_EXISTS, INVALID_DIALOGUE, INVALID_DURATION.
        Example: create_dialogue(project_id="project_01", scene_id="scene_03", dialogue={"dialogue_id": "d1", "character_id": "raj", "text": "WHO BROKE PRODUCTION?", "start": 2.0, "duration": 2.0})
        Note: Omit character_id for a narrator caption. A line must finish inside the scene duration.
        """
        return call(ctx.cartoon.create_dialogue, project_id, scene_id, dialogue)

    @mcp.tool()
    def get_dialogue(project_id: str, scene_id: str, dialogue_id: str) -> dict:
        """Purpose: Read one line of dialogue.

        When to use: Before rewriting a line, so you can send back the fields you want to keep.
        Arguments: project_id, scene_id, dialogue_id.
        Returns: The dialogue object.
        Side effects: None.
        Cache behavior: None.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, DIALOGUE_NOT_FOUND.
        Example: get_dialogue(project_id="project_01", scene_id="scene_03", dialogue_id="d1")
        """
        return call(ctx.cartoon.get_dialogue, project_id, scene_id, dialogue_id)

    @mcp.tool()
    def list_dialogue(project_id: str, scene_id: str) -> dict:
        """Purpose: List a scene's dialogue in speaking order.

        When to use: You are revising the script for a scene.
        Arguments: project_id, scene_id.
        Returns: {"dialogue": [...]} sorted by start time.
        Side effects: None.
        Cache behavior: None.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND.
        Example: list_dialogue(project_id="project_01", scene_id="scene_03")
        """
        return call(ctx.cartoon.list_dialogue, project_id, scene_id)

    @mcp.tool()
    def update_dialogue(project_id: str, scene_id: str, dialogue_id: str, fields: dict) -> dict:
        """Purpose: Rewrite or retime one line.

        When to use: "Change the dialogue to 'You deployed on Friday?!'". Only this line changes.
        Arguments: project_id, scene_id, dialogue_id; fields with any of text, character_id, start, duration, style, animation.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders. Every other scene stays cached.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, DIALOGUE_NOT_FOUND, INVALID_DURATION.
        Example: update_dialogue(project_id="project_01", scene_id="scene_03", dialogue_id="d1", fields={"text": "You deployed on Friday?!"})
        """
        return call(ctx.cartoon.update_dialogue, project_id, scene_id, dialogue_id, fields)

    @mcp.tool()
    def delete_dialogue(project_id: str, scene_id: str, dialogue_id: str) -> dict:
        """Purpose: Remove one line from a scene.

        When to use: The line is cut from the script.
        Arguments: project_id, scene_id, dialogue_id.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, DIALOGUE_NOT_FOUND.
        Example: delete_dialogue(project_id="project_01", scene_id="scene_03", dialogue_id="d2")
        """
        return call(ctx.cartoon.delete_dialogue, project_id, scene_id, dialogue_id)

    @mcp.tool()
    def add_character_action(project_id: str, scene_id: str, character_id: str, action: dict) -> dict:
        """Purpose: Direct a character with a named action instead of hand written keyframes.

        When to use: "Make Raj enter from the left", "have Sam shake his head". The engine turns the direction into deterministic motion.
        Arguments: project_id, scene_id, character_id; action object with type and optional action_id, start, duration, direction, distance, intensity, repeat, target, to.
        Returns: The updated scene. An action_id is assigned when you omit one.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, CHARACTER_NOT_IN_SCENE, INVALID_ACTION, INVALID_ACTION_PARAMETER, ACTION_EXISTS.
        Example: add_character_action(project_id="project_01", scene_id="scene_01", character_id="raj", action={"type": "walk_in", "direction": "left", "duration": 2})
        Note: Read rendering://cartoon-animation-primitives for the supported actions and their parameters.
        """
        return call(ctx.cartoon.add_character_action, project_id, scene_id, character_id, action)

    @mcp.tool()
    def update_character_action(
        project_id: str, scene_id: str, character_id: str, action_id: str, fields: dict
    ) -> dict:
        """Purpose: Retime or retune one action.

        When to use: The entrance should be slower, softer, or from the other side.
        Arguments: project_id, scene_id, character_id, action_id; fields with any of type, start, duration, direction, distance, intensity, repeat, target, to.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, CHARACTER_NOT_IN_SCENE, ACTION_NOT_FOUND, INVALID_ACTION.
        Example: update_character_action(project_id="project_01", scene_id="scene_01", character_id="raj", action_id="act_1", fields={"duration": 3})
        """
        return call(
            ctx.cartoon.update_character_action, project_id, scene_id, character_id, action_id, fields
        )

    @mcp.tool()
    def delete_character_action(project_id: str, scene_id: str, character_id: str, action_id: str) -> dict:
        """Purpose: Remove one action from a character in a scene.

        When to use: The move is cut. The character keeps its placement.
        Arguments: project_id, scene_id, character_id, action_id.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, CHARACTER_NOT_IN_SCENE, ACTION_NOT_FOUND.
        Example: delete_character_action(project_id="project_01", scene_id="scene_01", character_id="raj", action_id="act_1")
        """
        return call(ctx.cartoon.delete_character_action, project_id, scene_id, character_id, action_id)

    @mcp.tool()
    def set_scene_camera(project_id: str, scene_id: str, camera: dict | None = None) -> dict:
        """Purpose: Frame a scene with a shot preset and an optional camera move.

        When to use: "Zoom in when Raj realises what happened". Describe the direction; the engine animates it.
        Arguments: project_id, scene_id; camera object with optional shot (wide, medium, close_up, extreme_close_up, over_shoulder, two_shot), zoom, position, focus, rotation, animation, keyframes. Pass no camera to clear it.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, INVALID_CAMERA, INVALID_DURATION.
        Example: set_scene_camera(project_id="project_01", scene_id="scene_05", camera={"shot": "close_up", "focus": "raj", "animation": {"type": "push_in", "duration": 2}})
        """
        return call(ctx.cartoon.set_scene_camera, project_id, scene_id, camera)

    @mcp.tool()
    def add_prop_to_scene(project_id: str, scene_id: str, prop: dict) -> dict:
        """Purpose: Put a registered asset in the scene as a prop.

        When to use: A pizza box, a laptop, a sign. Props use the ordinary asset registry.
        Arguments: project_id, scene_id; prop object with prop_id, asset_id and optional position, scale, size, anchor, rotation, opacity, z_index, start, duration, animation.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, PROP_EXISTS, INVALID_PROP, INVALID_ASSET_REFERENCE.
        Example: add_prop_to_scene(project_id="project_01", scene_id="scene_02", prop={"prop_id": "pizza_box", "asset_id": "pizza_box_svg", "position": {"x": 0.5, "y": 0.7}, "scale": 1})
        """
        return call(ctx.cartoon.add_prop_to_scene, project_id, scene_id, prop)

    @mcp.tool()
    def update_prop_in_scene(project_id: str, scene_id: str, prop_id: str, fields: dict) -> dict:
        """Purpose: Move, resize, or animate a prop.

        When to use: The prop is in the wrong place or should react to the action.
        Arguments: project_id, scene_id, prop_id; fields with any of asset_id, position, scale, size, anchor, rotation, opacity, z_index, start, duration, animation.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, PROP_NOT_FOUND, INVALID_ASSET_REFERENCE.
        Example: update_prop_in_scene(project_id="project_01", scene_id="scene_02", prop_id="pizza_box", fields={"animation": {"type": "bounce"}})
        """
        return call(ctx.cartoon.update_prop_in_scene, project_id, scene_id, prop_id, fields)

    @mcp.tool()
    def remove_prop_from_scene(project_id: str, scene_id: str, prop_id: str) -> dict:
        """Purpose: Take a prop out of a scene.

        When to use: The prop is cut from the shot. The asset stays registered.
        Arguments: project_id, scene_id, prop_id.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, PROP_NOT_FOUND.
        Example: remove_prop_from_scene(project_id="project_01", scene_id="scene_02", prop_id="pizza_box")
        """
        return call(ctx.cartoon.remove_prop_from_scene, project_id, scene_id, prop_id)

    @mcp.tool()
    def set_scene_background(project_id: str, scene_id: str, background: dict | None = None) -> dict:
        """Purpose: Set or replace the cartoon background of a scene.

        When to use: "Replace the kitchen background". Use layered plates when you want parallax.
        Arguments: project_id, scene_id; background object with either asset_id, or background, midground, and foreground plus parallax, plus optional color and fit. Pass no background to clear it.
        Returns: The updated scene.
        Side effects: Rewrites the scene.
        Cache behavior: Only this scene rerenders.
        Errors: CARTOON_MODE_REQUIRED, SCENE_NOT_FOUND, INVALID_ASSET_REFERENCE, INVALID_CARTOON_SCENE.
        Example: set_scene_background(project_id="project_01", scene_id="scene_04", background={"asset_id": "office_night"})
        """
        return call(ctx.cartoon.set_scene_background, project_id, scene_id, background)

    @mcp.tool()
    def validate_cartoon_scene(project_id: str, scene: dict) -> dict:
        """Purpose: Check a cartoon scene and prove it compiles into renderable layers, without saving it.

        When to use: Before create_scene or update_scene when the scene has a cartoon block.
        Arguments: project_id and a scene object containing cartoon. Characters and assets must already be registered.
        Returns: valid, the compiled layer ids, the resolved camera, and any warnings, or a structured error.
        Side effects: None.
        Cache behavior: None.
        Errors: CARTOON_MODE_REQUIRED, INVALID_CARTOON_SCENE, CHARACTER_NOT_FOUND, INVALID_EXPRESSION, INVALID_POSE, INVALID_ACTION, INVALID_DIALOGUE, INVALID_CAMERA, INVALID_PROP, INVALID_DURATION.
        Example: validate_cartoon_scene(project_id="project_01", scene={"scene_id": "scene_03", "duration": 8, "cartoon": {"characters": [{"character_id": "raj"}]}})
        """
        return call(ctx.scenes.validate_cartoon_scene, project_id, scene)
