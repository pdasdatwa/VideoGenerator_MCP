from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_project_routes(ctx, monkeypatch):
    monkeypatch.setattr("app.main.get_context", lambda: ctx)
    app = create_app()
    app.state.ctx = ctx
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    config = client.get("/mcp.json")
    assert config.status_code == 200
    assert config.json()["mcpServers"]["reel-production"]["url"].endswith("/mcp")
    created = ctx.projects.create("API", preset="square")
    listing = client.get("/projects")
    assert listing.status_code == 200
    assert any(item["project_id"] == created["project_id"] for item in listing.json()["projects"])
    one = client.get(f"/projects/{created['project_id']}")
    assert one.json()["name"] == "API"
