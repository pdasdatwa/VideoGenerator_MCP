# Reel Production MCP

A general-purpose AI-directed reel and video production engine exposed through MCP.

The client LLM understands the request and the assets. This server stores the project, validates a declarative scene graph, and renders a real video. It does not run an LLM, and it does not assume the result is a marketing video.

## Architecture

```text
User
  |
  v
Client LLM
  |
  v
MCP
  |
  +-- Scene graph
  +-- Asset registry
  |
  v
Renderer
  |
  v
Video
```

The client LLM provides intent, understanding, and creative decisions. The MCP provides state, capabilities, execution, and cache reuse. The renderer provides pixels, motion, audio, and the encoded file.

## Asset workflow

```text
User assets + LLM-generated assets
        |
        v
  Asset registry
        |
        v
    Scene graph
```

Once a file is registered it is just an asset. Rendering does not care whether the user supplied it or the client LLM generated it. This server does not generate images.

Inspection is deterministic: Pillow for images, FFprobe for video and audio, and a local SVG parse. Videos also get a poster, keyframes, and a contact sheet. Semantic notes are stored only when the client writes them, and they are marked as unverified.

## What the client LLM does

- Read the user's request as the creative brief.
- Inspect assets before deciding how to use them.
- Ask a short question only when duration, aspect ratio, or purpose would change the cut.
- Use a sensible default when the request is already specific.
- Generate any missing stills or graphics with its own tools, then `register_asset`.
- Build the scene graph, validate it, render a preview, and revise from feedback.

## What the MCP does

- Store projects, scenes, assets, and cartoon characters inside a filesystem sandbox.
- Measure technical metadata.
- Validate declarative JSON. It never executes caller code.
- Render with Remotion and assemble with a controlled FFmpeg invocation.
- Cache each scene from its visual spec, asset hashes, renderer version, resolution, fps, and encode settings.
- Rerender only the scenes whose cache key changed.
- Mix audio at assembly time. A project with no audio is valid.
- Snapshot and restore versions without deleting history.

Read `rendering://capabilities` for the motion, effects, transitions, and formats this version actually implements. `RENDERER_VERSION` is `0.3.0` and is part of every cache key.

## Modes

A project has a mode. `standard` is the default and is the general-purpose engine described above.

`cartoon` switches on character production without changing any of it. A cartoon project gains characters that persist across scenes, editable dialogue, named actions, a camera, and props. Those are declared in an optional `cartoon` block on an ordinary scene, which the server compiles into ordinary layers plus a camera track. There is one renderer, one cache, and one version history for both modes, and a cartoon scene may still carry normal layers, effects, and audio.

Cartoon tools refuse to run on a standard project rather than switching the mode themselves. The server still generates no artwork: you produce the character sprites, backgrounds, and props and register them as ordinary assets.

```text
Character record  ->  scene cartoon block  ->  compiled layers + camera  ->  the same renderer
```

See the cartoon walkthrough in `HOW_TO_USE.md` and the reference in `MCP.md`.

## Rendering

`render_preview` and `render_project` validate the project, reuse cached scene pictures, render the misses, stitch transitions, mix audio when tracks exist, and write an MP4.

A preview can wait for the file or return a job id. Jobs are stored as local JSON and move through `queued`, `running`, `completed`, `failed`, and `cancelled`.

Incremental example:

```json
{
  "rendered": ["scene_02"],
  "cached": ["scene_01", "scene_03", "scene_04"],
  "cache_hit_rate": 0.75
}
```

## Install

Python 3.11+, Node, FFmpeg, and FFprobe are required.

```text
pip install -e .
cd renderer && npm install
```

Environment variables use the `REEL_` prefix. A `MARKETING_` variable is still read when the matching `REEL_` variable is unset.

## Run

```text
python -m app.mcp
```

The HTTP app serves MCP at `http://127.0.0.1:8080/mcp`. Point the client at server name `reel-production`.

Demos, all on the same renderer:

```text
python -m app.cli demo --name demo_product
python -m app.cli demo --name demo_travel
python -m app.cli demo --name demo_photo_montage
python -m app.cli demo --name demo_cinematic
```

## Tests

```text
pytest
pytest -m integration
```

The integration tests render real MP4 files.
