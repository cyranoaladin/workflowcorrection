from __future__ import annotations

from unittest.mock import patch


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_live(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "live"


def test_health_ready(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"]["ok"] is True
    assert data["checks"]["redis"]["ok"] is True
    assert data["checks"]["storage"]["ok"] is True
    assert data["checks"]["rag"]["ok"] is True
    assert data["checks"]["rag"]["provider"] == "pgvector"


def test_health_ready_returns_503_when_rag_fails(client, monkeypatch):
    monkeypatch.setenv("RAG_PROVIDER", "http")

    from app.core.config import get_settings
    from app.services.rag.factory import get_rag_provider

    get_settings.cache_clear()
    get_rag_provider.cache_clear()

    with patch("app.routers.health.get_rag_provider") as mock_factory:
        mock_factory.return_value.health.return_value = False
        r = client.get("/health/ready")

    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "degraded"
    assert data["checks"]["rag"]["ok"] is False
    assert data["checks"]["rag"]["provider"] == "http"
