from __future__ import annotations

import pytest


def test_health_routes_remain_public(anon_client):
    assert anon_client.get("/health").status_code == 200
    assert anon_client.get("/health/live").status_code == 200


def test_business_routes_require_admin_token(anon_client):
    r = anon_client.get("/integrations/status")
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "missing_admin_token"


def test_business_routes_reject_wrong_admin_token(anon_client):
    r = anon_client.get("/integrations/status", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "invalid_admin_token"


def test_business_routes_accept_configured_admin_token(client):
    r = client.get("/integrations/status")
    assert r.status_code == 200


def test_production_validation_rejects_placeholder_secrets(monkeypatch):
    from app.core.config import Settings

    settings = Settings(
        APP_ENV="production",
        ADMIN_API_TOKEN="change_me",
        JWT_SECRET="change_me_long_random_secret",
        POSTGRES_PASSWORD="change_me",
        DATABASE_URL="postgresql+psycopg2://correction_user:change_me@postgres:5432/correction_db",
        CORS_ALLOWED_ORIGINS="http://localhost:3000",
        PUBLIC_API_BASE_URL="http://localhost:8000",
    )

    with pytest.raises(ValueError) as exc:
        settings.validate_for_runtime()

    msg = str(exc.value)
    assert "ADMIN_API_TOKEN" in msg
    assert "JWT_SECRET" in msg
    assert "CORS_ALLOWED_ORIGINS" in msg


def test_production_validation_rejects_replace_with_placeholders():
    from app.core.config import Settings

    settings = Settings(
        APP_ENV="production",
        ADMIN_API_TOKEN="replace_with_32plus_random_chars",
        JWT_SECRET="replace_with_32plus_random_chars",
        POSTGRES_PASSWORD="replace_with_strong_database_password",
        DATABASE_URL="postgresql+psycopg2://correction_user:replace_with_strong_database_password@postgres:5432/correction_db",
        CORS_ALLOWED_ORIGINS="https://workflow.example.com",
        PUBLIC_API_BASE_URL="https://workflow.example.com",
    )

    with pytest.raises(ValueError) as exc:
        settings.validate_for_runtime()

    assert "replace_with" not in str(exc.value)
    assert "ADMIN_API_TOKEN" in str(exc.value)


def test_production_validation_accepts_hardened_settings():
    from app.core.config import Settings

    settings = Settings(
        APP_ENV="production",
        ADMIN_API_TOKEN="x" * 40,
        JWT_SECRET="y" * 40,
        POSTGRES_PASSWORD="z" * 24,
        DATABASE_URL="postgresql+psycopg2://correction_user:strong-password@postgres:5432/correction_db",
        CORS_ALLOWED_ORIGINS="https://workflow.company.test",
        PUBLIC_API_BASE_URL="https://api.workflow.company.test",
        RAG_HTTP_BASE_URL="https://rag-api.nexusreussite.academy",
        RAG_HTTP_API_TOKEN="r" * 32,
    )

    settings.validate_for_runtime()
