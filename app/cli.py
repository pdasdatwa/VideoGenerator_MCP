"""Local debugging CLI. Business logic lives in the services."""

from __future__ import annotations

import argparse
import json

from app.services import get_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Reel production CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-project")
    create.add_argument("--name", required=True)
    create.add_argument("--preset", default="instagram_reels")

    sub.add_parser("list-projects")

    validate = sub.add_parser("validate-project")
    validate.add_argument("project_id")

    render = sub.add_parser("render-project")
    render.add_argument("project_id")
    render.add_argument("--preview", action="store_true")

    inspect = sub.add_parser("inspect-asset")
    inspect.add_argument("project_id")
    inspect.add_argument("asset_id")

    demo = sub.add_parser("demo")
    demo.add_argument("--name", default="demo_product", choices=["demo_product", "demo_travel", "demo_photo_montage", "demo_cinematic"])
    demo.add_argument("--final", action="store_true")

    args = parser.parse_args()
    ctx = get_context()
    if args.command == "create-project":
        payload = ctx.projects.create(args.name, preset=args.preset)
    elif args.command == "list-projects":
        payload = {"projects": ctx.projects.list_projects()}
    elif args.command == "validate-project":
        payload = ctx.scenes.validate_project(args.project_id)
    elif args.command == "render-project":
        if args.preview:
            payload = ctx.renders.render_preview(args.project_id, wait=True)
        else:
            payload = ctx.renders.render_project(args.project_id, wait=True)
    elif args.command == "inspect-asset":
        payload = ctx.assets.preview_info(args.project_id, args.asset_id)
    else:
        payload = build_demo_command(ctx, name=args.name, final=args.final)
    print(json.dumps(payload, indent=2))


def build_demo_command(ctx, *, name: str, final: bool) -> dict:
    from app.demo import build_demo

    return build_demo(ctx, name=name, profile="final" if final else "preview")


if __name__ == "__main__":
    main()
