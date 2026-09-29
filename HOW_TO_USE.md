# How to use Reel Production MCP

Start the server from this repository:

```text
python -m app.mcp
```

In Cursor, enable **reel-production**. The project config is `.cursor/mcp.json` and points at `http://127.0.0.1:8080/mcp`.

Put source files in `imports/` or `demos/assets/`. The server will not read paths outside those directories.

## A specific request can start immediately

```text
Using the reel-production MCP, make a 15-second cinematic Instagram reel from imports/photo.png.
Use slow motion and no music.
```

The client should inspect the asset, create a vertical project, register the file, write scenes, validate, and render a preview. It should not ask for the platform or duration, because both were given.

## A vague request should ask one question

```text
User: Make a reel from these photos.

LLM: What platform should it target, and roughly how long should it be?

User: Instagram, around 15 seconds.
```

Then the client uses the MCP.

## Useful calls

- `rendering://capabilities` lists layers, motion, effects, transitions, and presets.
- `register_asset` copies a file in and returns measured metadata.
- `get_asset_preview` and `get_asset_keyframes` return resource URIs. They do not describe the picture.
- `update_asset_metadata` stores your own semantic notes. Those notes are not verified.
- `upsert_scene` writes a whole scene in one call.
- `render_preview` returns a playable MP4, plus which scenes rendered and which were cached.

Audio is optional. Clearing `audio_tracks` leaves the project valid.

## Cartoon mode

Cartoon mode is the same engine with character production switched on. A project is `standard` unless
you say otherwise, and standard projects behave exactly as they always have. Cartoon mode adds
characters that persist across scenes, editable dialogue, named actions, a camera, and props.

Choose it when the user asks for a cartoon, an animated story, or talking characters:

```text
Using the reel-production MCP, make a 20-second cartoon where two engineers argue
about who broke production, then make up over pizza.
```

Cartoon tools refuse to run on a standard project rather than switching the mode for you, so decide
up front. You can still change it later with `update_project(fields={"mode": "cartoon"})`.

### Walkthrough

This is the shortest path from nothing to a playable cartoon. Every call is an MCP tool.

**1. Read the vocabulary.** Before directing, fetch `rendering://cartoon-schema`,
`rendering://character-schema`, and `rendering://cartoon-animation-primitives`. The last one lists
every action this renderer implements, with the parameters each one accepts. Do not invent action
names, and do not write keyframes by hand.

**2. Create a cartoon project.**

```json
create_project({"name": "Friday deploy", "preset": "portrait", "fps": 24, "mode": "cartoon"})
```

**3. Make the artwork yourself and register it.** This server has no image generator. Produce the
character sprites, backgrounds, and props with your own tools, write them into `imports/`, and
register them. Draw each character facing the camera on a transparent background, and give SVG files
a `viewBox` so they can be scaled to fit their layer.

```json
register_asset({"project_id": "...", "path": "imports/office.svg", "asset_id": "office", "semantic_type": "background"})
register_asset({"project_id": "...", "path": "imports/pizza.svg", "asset_id": "pizza", "semantic_type": "prop"})
```

**4. Create the cast, then wire artwork to each character.**

```json
create_character({"project_id": "...", "character": {
  "character_id": "raj",
  "name": "Raj",
  "description": "Backend engineer, one incident away from the edge.",
  "traits": ["sarcastic", "loyal"],
  "visual_style": "2D flat comic, thick outlines",
  "default_position": {"x": 0.32, "y": 0.8},
  "default_size": 0.55
}})

register_character_asset({"project_id": "...", "character_id": "raj",
  "path": "imports/raj_base.svg", "role": "character_base", "asset_id": "raj_base"})

register_character_asset({"project_id": "...", "character_id": "raj",
  "path": "imports/raj_angry.svg", "role": "character_expression", "key": "angry", "asset_id": "raj_angry"})
```

`role` is one of `character_base`, `character_pose`, `character_expression`, `character_part`, or
`character_accessory`. Everything except `character_base` needs a `key`, which is the name a scene
uses. A key containing a colon, such as `standing:angry`, registers a combined pose and expression
variant. When a scene asks for a pose and an expression the server resolves, in order,
`variants['pose:expression']`, then `expressions[expression]`, then `poses[pose]`, then `base`.

Register `mouth_open` and `mouth_closed` parts if you want the `talk` action to move a mouth.
Without them `talk` still animates the head and returns a warning.

`get_character_assets` tells you exactly which poses and expressions a scene is allowed to name.

**5. Write the scene.** The cartoon block hangs off an ordinary scene, so a scene can carry both a
cartoon block and normal layers, effects, and audio.

```json
create_scene({"project_id": "...", "scene": {
  "scene_id": "scene_01",
  "duration": 8,
  "cartoon": {
    "background": {"asset_id": "office"},
    "characters": [
      {"character_id": "raj", "expression": "angry", "position": {"x": 0.32, "y": 0.8},
       "actions": [
         {"action_id": "act_1", "type": "walk_in", "direction": "left", "duration": 1.5},
         {"action_id": "act_2", "type": "talk", "start": 2, "duration": 2}
       ]},
      {"character_id": "sam", "expression": "nervous", "position": {"x": 0.68, "y": 0.8},
       "actions": [{"action_id": "act_1", "type": "recoil", "start": 2.2, "duration": 1}]}
    ],
    "dialogue": [
      {"dialogue_id": "d1", "character_id": "raj", "text": "WHO BROKE PRODUCTION?", "start": 2, "duration": 2},
      {"dialogue_id": "d2", "character_id": "sam", "text": "It was a small change...", "start": 4.5, "duration": 2.5}
    ],
    "camera": {"shot": "two_shot", "animation": {"type": "push_in", "start": 2, "duration": 2}},
    "props": [{"prop_id": "pizza", "asset_id": "pizza", "position": {"x": 0.5, "y": 0.93}, "size": 0.2}]
  }
}})
```

Call `validate_cartoon_scene` first if you want to see the compiled layer ids, the resolved camera,
and any warnings without saving anything.

**6. Render.**

```json
render_preview({"project_id": "...", "wait": true})
```

`render_preview` returns a playable MP4, the scenes it rendered, the scenes it reused from cache, and
any compiler warnings.

### Revising a cartoon

Every part of a cartoon scene is addressable, so a revision touches one thing and rerenders one
scene. The dialogue is data and is never baked into artwork, so rewriting a line never touches a
character asset.

| The user says | The call |
| --- | --- |
| "Change that line" | `update_dialogue(project_id, scene_id, dialogue_id, {"text": "..."})` |
| "Make Raj angry in scene 4" | `update_character_in_scene(project_id, "scene_04", "raj", {"expression": "angry"})` |
| "Have Sam enter from the right" | `add_character_action(project_id, scene_id, "sam", {"type": "walk_in", "direction": "right"})` |
| "Slow that entrance down" | `update_character_action(project_id, scene_id, "sam", "act_1", {"duration": 3})` |
| "Zoom in on Raj here" | `set_scene_camera(project_id, scene_id, {"shot": "close_up", "focus": "raj", "animation": {"type": "push_in", "duration": 2}})` |
| "Replace the kitchen background" | `set_scene_background(project_id, scene_id, {"asset_id": "kitchen_night"})` |
| "Give Raj a new look everywhere" | `register_character_asset(..., replace=true)` or `update_character` |
| "Drop the pizza box" | `remove_prop_from_scene(project_id, scene_id, "pizza")` |

Editing one line of dialogue rerenders only that scene. Replacing a character's artwork rerenders
only the scenes that draw that character. Everything else comes from cache.

### Mixing cartoon and standard content

A cartoon scene may also carry ordinary layers, so a title card, a logo, a real photograph, or a
music track works the same as it does in standard mode. Compiled cartoon layers use the id prefixes
`cbg_`, `char_`, `prop_`, and `dlg_`, which are reserved. Name your own layers something else.

### What the server will not do

It does not generate artwork, write your script, choose the story, or decide a character's
personality. It stores the cast, validates the direction, turns named actions into deterministic
motion, renders, caches, and versions. The creative work is yours.
