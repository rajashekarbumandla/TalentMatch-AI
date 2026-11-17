"""API smoke tests: the app starts, reports health, and only allows known frontend origins."""
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.database as database
from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_service_and_database():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "TalentMatch AI API"
    assert body["status"] in {"ok", "degraded"}
    assert set(body["database"]) == {"configured", "connected", "message"}
    assert body["model"]["name"] == "all-MiniLM-L6-v2" and isinstance(body["model"]["loaded"], bool)


def test_health_reports_connected_database(database_available):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == {
        "configured": True,
        "connected": True,
        "message": "Connected to Supabase PostgreSQL.",
    }


def test_health_never_leaks_database_url():
    body = client.get("/api/health").text
    assert "postgresql" not in body and "pooler.supabase.com" not in body


def test_get_db_returns_503_when_database_not_configured(monkeypatch):
    monkeypatch.setattr(database, "engine", None)
    monkeypatch.setattr(database, "DB_CONFIG_ERROR", "DATABASE_URL is not set in backend/.env.")
    generator = database.get_db()
    try:
        next(generator)
        raise AssertionError("expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "DATABASE_URL is not set" in exc.detail


def test_cors_allows_vite_dev_server():
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_openapi_docs_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "TalentMatch AI API"
