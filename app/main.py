"""FastAPI application. Starting uvicorn also starts the MCP server."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.errors import ReelError
from app.mcp.server import build_server
from app.services import get_context


def create_app() -> FastAPI:
    ctx = get_context()
    mcp = build_server(ctx)
    mcp_app = mcp.streamable_http_app(streamable_http_path="/", host=ctx.settings.api_host)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="Reel Production", version="0.2.0", lifespan=lifespan)
    app.state.ctx = ctx
    app.state.mcp = mcp
    app.include_router(health_router)
    app.include_router(projects_router)
    app.mount("/mcp", mcp_app)

    @app.exception_handler(ReelError)
    async def reel_error(_: Request, exc: ReelError) -> JSONResponse:
        return JSONResponse(status_code=400, content=exc.to_dict())

    return app


app = create_app()
