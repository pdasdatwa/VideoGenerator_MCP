"""Reel production MCP server."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.mcp import catalog
from app.mcp.resources import register as register_resources
from app.mcp.tools import assets, cartoon, characters, projects, rendering, scenes, versions
from app.services import AppContext, get_context


def build_server(ctx: AppContext | None = None) -> MCPServer:
    context = ctx or get_context()
    mcp = MCPServer(
        "reel-production",
        instructions=catalog.INSTRUCTIONS,
    )
    projects.register(mcp, context)
    assets.register(mcp, context)
    characters.register(mcp, context)
    scenes.register(mcp, context)
    cartoon.register(mcp, context)
    rendering.register(mcp, context)
    versions.register(mcp, context)
    register_resources(mcp, context)
    return mcp
