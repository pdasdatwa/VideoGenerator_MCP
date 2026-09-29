"""Minimal project reads. MCP is the editing interface."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["projects"])


@router.get("/projects")
def list_projects(request: Request) -> dict:
    return {"projects": request.app.state.ctx.projects.list_projects()}


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    return request.app.state.ctx.projects.get_dict(project_id)
