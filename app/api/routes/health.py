"""Health and the HTTP MCP client entry."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.renderer.version import RENDERER_VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "renderer_version": RENDERER_VERSION, "mcp_config": "/mcp.json"}


@router.get("/mcp.json")
def mcp_client_config(request: Request) -> dict:
    """Client entry for the MCP server mounted at /mcp on this same process."""
    base = str(request.base_url).rstrip("/")
    return {"mcpServers": {"reel-production": {"url": f"{base}/mcp"}}}
