# Reel Production MCP

Authoritative interface for the `reel-production` server. Renderer version `0.3.0`.

The server does not run an LLM. The client LLM is the creative director for any short-form video the renderer can express: travel, product, event, education, personal, music, comedy, or advertising.

## Responsibilities

| Client LLM | This server |
| --- | --- |
| User intent, clarifying questions, creative plan | Project and asset storage |
| Asset understanding from previews | Technical inspection, posters, keyframes |
| Extra assets generated elsewhere | Registration of those files as ordinary assets |
| Scene JSON | Validation, render, cache, mix, version |
| Story, characters, dialogue, direction | Character storage, deterministic animation, camera |

Send JSON specifications only. The server rejects unknown scene fields and does not execute caller JavaScript or shell.

## Tools

Projects: `create_project`, `get_project`, `list_projects`, `update_project`, `delete_project`, `create_or_update_project`.

Assets: `register_asset`, `get_asset`, `list_assets`, `update_asset_metadata`, `delete_asset`, `get_asset_preview`, `get_asset_keyframes`.

Scenes: `create_scene`, `get_scene`, `list_scenes`, `update_scene`, `delete_scene`, `upsert_scene`, `validate_scene`, `validate_project`.

Render: `render_scene`, `render_preview`, `render_project`, `get_render_status`, `get_render`.

Versions: `create_version`, `get_version`, `list_versions`, `restore_version`.

Characters, cartoon mode only: `create_character`, `get_character`, `list_characters`, `update_character`, `delete_character`, `register_character_asset`, `get_character_assets`.

Cartoon scenes, cartoon mode only: `add_character_to_scene`, `update_character_in_scene`, `remove_character_from_scene`, `create_dialogue`, `get_dialogue`, `list_dialogue`, `update_dialogue`, `delete_dialogue`, `add_character_action`, `update_character_action`, `delete_character_action`, `set_scene_camera`, `add_prop_to_scene`, `update_prop_in_scene`, `remove_prop_from_scene`, `set_scene_background`, `validate_cartoon_scene`.

`create_or_update_project` and `upsert_scene` are convenience wrappers. The lower-level tools stay available. `restore_version` writes a new version and keeps the old ones. The cartoon tools are narrow edits on top of `create_scene` and `update_scene`, which also accept a whole `cartoon` block.

## Resources

| URI | Contents |
| --- | --- |
| `rendering://capabilities` | Implemented layers, motion, effects, transitions, audio, and presets |
| `rendering://scene-schema` | Example scene |
| `rendering://animation-primitives` | Motion names and easing |
| `rendering://effects` | Effect fields and ranges |
| `rendering://supported-assets` | File extensions |
| `rendering://project/{project_id}` | Project JSON |
| `rendering://project/{project_id}/scene/{scene_id}` | Scene JSON |
| `rendering://asset/{asset_id}` | Public asset record |
| `rendering://asset/{asset_id}/preview/{name}` | Image bytes |
| `rendering://asset/{asset_id}/keyframes` | Poster, keyframe, and contact-sheet index |
| `rendering://cartoon-schema` | The cartoon block, with an example scene |
| `rendering://character-schema` | The character record and asset resolution order |
| `rendering://cartoon-animation-primitives` | Every implemented action, its family, and its parameters |
| `rendering://project/{project_id}/character/{character_id}` | Character JSON |

Scene ids are chosen per project, so scene resources stay under the project id. Character ids work the same way.

## Project

`create_project` accepts `name`, `description`, `preset`, `width`, `height`, `fps`, `platform`, and `mode`. Presets:

| Preset | Size | Aspect |
| --- | --- | --- |
| `instagram_reels` | 1080x1920 | 9:16 |
| `youtube_shorts` | 1080x1920 | 9:16 |
| `youtube` | 1920x1080 | 16:9 |
| `landscape` | 1920x1080 | 16:9 |
| `square` | 1080x1080 | 1:1 |
| `portrait` | 1080x1350 | 4:5 |

Custom `width` and `height` are allowed. Unspecified fields use defaults.

`mode` is `standard` or `cartoon` and defaults to `standard`. A standard project behaves exactly as it did before cartoon mode existed. Cartoon tools raise `CARTOON_MODE_REQUIRED` on a standard project instead of switching the mode for you; `update_project(fields={"mode": "cartoon"})` switches it deliberately.

## Assets

Registration measures technical metadata and stores `sha256` and `file_size` on the asset and inside `technical_metadata`.

| Kind | Measured fields |
| --- | --- |
| Image | format, width, height, mime type, file size, alpha, sha256 |
| Video | format, width, height, duration, fps, codec, bitrate, audio presence and codec, sha256, plus poster, keyframes, and a contact sheet |
| Audio | format, duration, sample rate, channels, codec, sha256 |
| SVG | source resource, width and height when `width`/`height` or `viewBox` is present, sha256 |

`semantic_metadata` is LLM-provided and unverified. The record includes that note. The server never claims to know what an asset depicts unless the client stored that text. `semantic_type` and `character_id` are the same kind of caller-supplied label: `semantic_type` is one of `character_base`, `character_pose`, `character_expression`, `character_accessory`, `character_part`, `background`, `prop`, `speech_bubble`, `other`, and `register_character_asset` sets both for you.

Paths must stay inside the configured source directories. Extensions and file headers are checked. SVG script content is stripped before render.

## Scene schema

A scene has `scene_id`, `duration`, `background`, `layers`, optional `audio`, `transition_out`, and, on a cartoon project, an optional `cartoon` block.

Layer types: `image`, `video`, `svg`, `text`, `shape`.

Each layer may set `asset_id`, `start`, `duration`, `z_index`, `position`, `scale`, `rotation`, `opacity`, `crop`, `fit`, `effects`, `animation`, `blend_mode`, and `mask`.

Transforms accept a static value, `{from, to}`, or `{keyframes: [{time, value}]}`. The same forms work for `blur`, `brightness`, `contrast`, `saturation`, `volume`, and `playback_rate`.

Coordinates are normalized. `x=0` is left and `y=0` is top. Text wraps, and text layers respect the project safe area unless `respect_safe_area` is false.

### Motion

`fade`, `fade_up`, `fade_down`, `fade_left`, `fade_right`, `slide_left`, `slide_right`, `slide_up`, `slide_down`, `scale_in`, `scale_out`, `slow_push`, `slow_pull`, `pan_left`, `pan_right`, `pan_up`, `pan_down`, `rotate`, `orbit`, `parallax`, `ken_burns`, `float`, `drift`, `shake`, `handheld`.

Text also supports `word_reveal`, `character_reveal`, and `typewriter`.

### Effects

`blur`, `motion_blur`, `brightness`, `contrast`, `saturation`, `grayscale`, `sepia`, `vignette`, `glow`, `bloom`, `drop_shadow`, `grain`, `color_tint`.

`motion_blur` is velocity-scaled blur. It is not optical-flow blur.

### Masks and blend modes

Masks: `rect`, `rounded_rect`, `circle`, `ellipse`, with animated center, size, and radius.

Blend modes: `normal`, `multiply`, `screen`, `overlay`, `soft_light`.

### Playback

Video layers accept a constant `playback_rate`, including 0.25, 0.5, 0.75, 1, 1.25, 1.5, and 2. Other positive values up to 8 still validate. Keyframed `playback_rate` is a speed ramp: FFmpeg bakes it into a cached intermediate, then Remotion plays that file at 1x.

### Transitions

`cut`, `fade`, `crossfade`, `slide`, `zoom`, `blur`, `whip`, `dip_to_color`.

A transition must be shorter than the outgoing scene and the next scene. `dip_to_color` uses black or white dips; any other hex color dips through black.

### Audio

Audio is optional. Tracks may be `music`, `voiceover`, or `sfx`, with `start`, `duration`, `volume`, `fade_in`, `fade_out`, `trim_start`, and `trim_end`.

A music track may set `duck`:

```json
{"when_role": "voiceover", "to_volume": 0.25, "attack": 0.15, "release": 0.3}
```

Removing every audio track leaves the project valid. The next assembly copies the picture through with no audio stream.

## Cartoon mode

Everything in this section requires a project with `mode="cartoon"`. Cartoon declarations compile into ordinary layers plus a camera track, then go through the same validator, renderer, cache, and version history as a standard scene.

### Characters

A character is an identity that outlives any scene. Scenes reference `character_id` and describe only that appearance.

| Field | Meaning |
| --- | --- |
| `character_id`, `name` | Identity |
| `description`, `traits`, `visual_style`, `metadata` | Your text. Stored, never verified, never interpreted |
| `default_position`, `default_scale`, `default_size`, `default_anchor` | Resting placement when a scene does not override it |
| `assets` | `base`, `poses`, `expressions`, `variants`, `parts`, `accessories` |

`default_size` is the sprite height as a fraction of the frame; the width follows the artwork's aspect ratio. `default_anchor` defaults to `{x: 0.5, y: 1}`, so `position` names where the feet stand.

`register_character_asset` registers a file through the ordinary asset registry and wires it into one slot. `role` is one of `character_base`, `character_pose`, `character_expression`, `character_part`, `character_accessory`. Everything except `character_base` needs a `key`. A key containing a colon, such as `standing:angry`, becomes a combined variant.

A scene's pose and expression resolve in this order:

```text
assets.variants["<pose>:<expression>"] -> assets.expressions[expression] -> assets.poses[pose] -> assets.base
```

Recognized part names are `mouth_open`, `mouth_closed`, `eyes_open`, `eyes_closed`. Registering both mouth parts makes `talk` move a mouth; without them `talk` animates the head and reports a warning. Other part names are accepted with a warning and drawn as overlays.

Character artwork is an ordinary asset carrying `semantic_type` and `character_id`, so `list_assets`, previews, replacement, and hashing all behave normally. Deleting a character used by a scene returns `CHARACTER_IN_USE`; deleting one that is unused leaves its assets registered.

### The cartoon block

`cartoon` is an optional field on any scene. It holds `background`, `characters`, `dialogue`, `camera`, and `props`.

```json
{
  "background": {"asset_id": "office", "fit": "cover"},
  "characters": [{"character_id": "raj", "expression": "angry", "actions": [{"type": "wave"}]}],
  "dialogue": [{"dialogue_id": "d1", "character_id": "raj", "text": "Hello", "start": 1, "duration": 2}],
  "camera": {"shot": "two_shot", "animation": {"type": "push_in", "duration": 2}},
  "props": [{"prop_id": "mug", "asset_id": "mug", "position": {"x": 0.6, "y": 0.8}}]
}
```

A scene character accepts `character_id`, `pose`, `expression`, `position`, `scale`, `size`, `anchor`, `rotation`, `opacity`, `z_index`, `start`, `duration`, `accessories`, and `actions`. Anything it omits falls back to the character record.

`background` takes either a single `asset_id` or layered `background`, `midground`, and `foreground` plates with `parallax` between 0 and 1. Layered plates drift against a moving camera by depth, so the far plate moves least. SVG plates should carry a `viewBox` so they can be sized to the frame.

`props` are registered assets placed in the scene: `prop_id`, `asset_id`, the usual placement fields, and an optional `animation` that takes any action.

Compiled layers use the reserved id prefixes `cbg_`, `char_`, `prop_`, and `dlg_`. A hand-written layer using one of those is rejected. A cartoon scene may otherwise carry any normal layer, effect, transition, or audio track, and those layers draw above the cartoon unless you set `z_index`.

### Dialogue

Dialogue is data. It is never baked into a character asset, and rewriting a line never touches artwork.

A line has `dialogue_id`, `text`, `start`, `duration`, optional `character_id`, `style`, and `animation`. Omit `character_id` for a narrator caption. The line must finish inside the scene duration.

`style` accepts `bubble`, `bubble_asset_id`, `bubble_color`, `bubble_opacity`, `text_color`, `font_family`, `font_size`, `font_weight`, `align`, `max_width`, `position`, `offset`, and `z_index`. Without a `bubble_asset_id` the bubble is a rounded shape layer.

The bubble is anchored above the speaker, sampled at the moment the line starts, so a walking character does not drag it mid-sentence. It is then kept inside the region the camera actually shows for the whole scene, so a zoomed shot never cuts a line in half.

Animations: `fade`, `fade_up`, `fade_down`, `scale_in`, `word_reveal`, `character_reveal`, `typewriter`.

### Actions

Direct characters with named actions. The compiler samples them deterministically at a fixed rate, independent of project fps. Do not write keyframes yourself.

Every action accepts `action_id`, `start`, and `duration`, plus the parameters listed below. `intensity` scales the amount and defaults to 1. `repeat` sets the cycle count. `direction` is `left`, `right`, `up`, or `down`. An action must finish inside the scene.

Actions on the same character compose: offsets add, scale and opacity multiply.

| Action | Extra parameters | Behaviour |
| --- | --- | --- |
| `enter` | direction, distance | Slide in from off frame and fade up. No walk bob. |
| `exit` | direction, distance | Slide off frame and fade out. No walk bob. |
| `jump` | intensity, repeat | Anticipate, leave the ground, squash on landing. |
| `run` | direction, distance, intensity | Like walk with a faster bob and a forward lean. |
| `slide` | direction, distance | Move by distance in one direction and stay there. |
| `walk` | direction, distance, intensity | Travel across the frame with a walking bob. |
| `walk_in` | direction, distance, intensity | Walk in from off frame to the placed position. `direction` is the side entered from. |
| `walk_out` | direction, distance, intensity | Walk from the placed position off frame. `direction` is the side exited to. |
| `bounce` | intensity, repeat | Repeated vertical bounce that settles at the placed position. |
| `lean` | direction, intensity | Tilt toward one side and hold. |
| `nod` | intensity, repeat | Vertical agreement nod. |
| `point` | direction, target, intensity | Lean and rotate toward a direction, a point, or another character. |
| `recoil` | direction, intensity | Snap away from an impact and settle back. |
| `shake` | intensity, repeat | Rapid horizontal tremor that decays to zero. |
| `shake_head` | intensity, repeat | Horizontal disagreement shake. |
| `sit` | intensity | Lower and compress into a seated offset. |
| `squash` | intensity | Compress vertically and widen, then return. |
| `stand` | intensity | Rise from a seated offset to full height. |
| `stretch` | intensity | Extend vertically and narrow, then return. |
| `turn` | direction, intensity | Rotate in place toward a side and hold. Register a pose or variant asset for a real turnaround. |
| `wave` | intensity, repeat | Rocking wave built from a rotation oscillation. |
| `blink` | repeat | Hides the `eyes_open` part in short beats. Needs an eyes part, otherwise a no-op warning. |
| `expression_change` | to, intensity | Cross fade from the current expression asset to another registered expression. |
| `look_at` | target, intensity | Turn toward a normalized point or another character in the scene. |
| `look_left`, `look_right` | intensity | Shift attention with a small offset and tilt. |
| `talk` | intensity, repeat | Speaking bob. Swaps `mouth_open` and `mouth_closed` when both are registered. |
| `angry_reaction` | intensity | Lean in, scale up, and tremble. |
| `confused_reaction` | intensity | Slow head tilt one way then the other. |
| `cry` | intensity, repeat | Slow shoulder shudder while sunk down. |
| `happy_reaction` | intensity | Two light hops with a rotation lilt. |
| `laugh` | intensity, repeat | Rocking bounce with a rotation wobble. |
| `sad_reaction` | intensity | Sink down and compress, then hold low. |
| `shocked_reaction` | intensity | Hard recoil backwards with a scale spike. |
| `surprised_reaction` | intensity | Pop up and back with a scale overshoot. |
| `anticipation` | direction, intensity | Pull back before moving forward. Use before a movement action. |
| `impact` | direction, intensity | Single hard displacement and squash on the hit frame. |
| `overshoot` | direction, distance, intensity | Travel past the target and ease back to it. |
| `pop` | intensity | Scale from nothing to slightly over size, then settle. |

`rendering://cartoon-animation-primitives` returns this same list from the implementation, so trust it over any copy.

### Camera

The camera frames the whole compiled scene. It is a transform on the composition, not a layer.

Shots and their base zoom: `wide` 1.0, `medium` 1.25, `close_up` 1.6, `extreme_close_up` 2.2, `over_shoulder` 1.45, `two_shot` 1.1. An explicit `zoom` overrides the preset.

`focus` names a character placed in the same scene and frames their upper body. `position` sets the point directly and wins over `focus`.

Moves: `hold`, `push_in`, `pull_out`, `pan_left`, `pan_right`, `tilt_up`, `tilt_down`, `shake`. Give `animation` a `type`, `start`, `duration`, and optional `amount`, `intensity`, and `easing`. For full manual control pass `keyframes` with `time`, `position`, `zoom`, and `rotation`.

A scene with no camera renders with no camera transform at all, exactly like a standard scene.

### Consistency and caching

The same `character_id` resolves to the same artwork everywhere, so a character looks the same across scenes without you restating anything. Defaults live on the character; per-scene fields are overrides.

The cache key of a cartoon scene hashes the compiled output, the compiler version, and the hashes of every asset it draws. Dependency-aware invalidation follows:

| Change | Rerendered |
| --- | --- |
| One line of dialogue | That scene |
| A character's expression in one scene | That scene |
| A character record or one of its assets | Only the scenes that draw that character |
| A background or prop asset | Only the scenes that use it |
| Audio | Nothing. Audio is mixed at assembly |

`create_version` snapshots characters alongside scenes, and `restore_version` restores the cast with them.

### Cartoon errors

`CARTOON_MODE_REQUIRED`, `INVALID_CARTOON_SCENE`, `CHARACTER_NOT_FOUND`, `CHARACTER_EXISTS`, `CHARACTER_IN_USE`, `CHARACTER_NOT_IN_SCENE`, `DUPLICATE_CHARACTER`, `INVALID_CHARACTER`, `INVALID_POSE`, `INVALID_EXPRESSION`, `MISSING_CHARACTER_ASSET`, `INVALID_ACTION`, `INVALID_ACTION_PARAMETER`, `ACTION_EXISTS`, `ACTION_NOT_FOUND`, `INVALID_DIALOGUE`, `DIALOGUE_EXISTS`, `DIALOGUE_NOT_FOUND`, `INVALID_CAMERA`, `INVALID_PROP`, `PROP_EXISTS`, `PROP_NOT_FOUND`.

Each one names the field and the fix. Unknown expressions and poses list the registered ones.

### What cartoon mode does not do

It does not generate artwork, write scripts, choose the story, decide a character's personality, invent dialogue you did not ask for, or call an external AI provider. It has no cartoon templates and no built-in characters. You direct; it validates, animates, renders, caches, and versions.

## Render, cache, and versions

Pipeline: validate, resolve dependencies, check the scene cache, render misses, stitch, mix audio if present, encode.

The cache key includes the visual scene spec, SHA-256 hashes of referenced visual assets, `RENDERER_VERSION`, resolution, fps, and encode settings. Audio changes do not rerender pictures. An asset hash change misses only the scenes that reference that asset.

`render_preview` and `render_project` accept `wait=true` or `wait=false`. A waiting call returns `output_path`, rendered scenes, cached scenes, duration, and warnings through the job report. A non-waiting call returns a job id. Jobs are JSON files on disk, not a queue service.

`create_version` snapshots the project and scene specs. `restore_version` copies that snapshot forward and appends a new version. Older versions remain.

## Errors

Domain errors return `error`, `message`, and `suggested_action`. Common codes: `INVALID_SCENE`, `INVALID_LAYER`, `INVALID_ANIMATION`, `INVALID_COORDINATES`, `INVALID_DURATION`, `INVALID_ASSET_REFERENCE`, `ASSET_NOT_FOUND`, `ASSET_IN_USE`, `PROJECT_NOT_FOUND`, `SCENE_NOT_FOUND`, `PATH_NOT_ALLOWED`, `UNSUPPORTED_FORMAT`, `RENDER_FAILURE`.

## Security

Source paths are jailed. IDs are restricted. Scene models forbid extra fields. FFmpeg and Remotion are invoked with argument lists, not shell strings. SVG is sanitized. Logs include project, scene, asset, and job ids, cache hits and misses, render duration, and render errors. They do not include media bytes or semantic descriptions.

## Example conversation

```text
User:
Make a reel from these photos.

LLM:
I can do that. What platform should it target, and roughly how long should it be?

User:
Instagram, around 15 seconds.

LLM:
Understood.
```

The client then reads `rendering://capabilities`, registers the photos, writes scenes for a 15-second 9:16 reel, calls `validate_project`, and calls `render_preview`.

A request that already says "15-second cinematic Instagram reel" does not need that question.

Later:

```text
User: Make the second shot slower and remove the music.

LLM: updates scene 2 playback_rate and clears audio_tracks.
MCP: rerenders scene 2, reuses the other scene caches, and exports a silent MP4.
```
