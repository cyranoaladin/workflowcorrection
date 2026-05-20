from __future__ import annotations

import pytest

from app.core.config import Settings


def _prod_settings(**overrides: object) -> Settings:
    values = {
        "APP_ENV": "production",
        "ADMIN_API_TOKEN": "a" * 32,
        "JWT_SECRET": "b" * 32,
        "POSTGRES_PASSWORD": "c" * 16,
        "DATABASE_URL": "postgresql+psycopg2://user:securepass@postgres:5432/db",
        "CORS_ALLOWED_ORIGINS": "https://maths.labomaths.tn",
        "PUBLIC_API_BASE_URL": "https://maths.labomaths.tn/correction/api",
        "RAG_PROVIDER": "http",
        "RAG_HTTP_BASE_URL": "https://rag-api.nexusreussite.academy",
        "RAG_HTTP_API_TOKEN": "r" * 32,
    }
    values.update(overrides)
    return Settings(**values)


def test_prod_http_rag_rejects_public_http_base_url() -> None:
    settings = _prod_settings(RAG_HTTP_BASE_URL="http://rag-api.nexusreussite.academy")

    with pytest.raises(ValueError, match="RAG_HTTP_BASE_URL"):
        settings.validate_for_runtime()


def test_prod_http_rag_allows_internal_docker_http_base_url() -> None:
    settings = _prod_settings(RAG_HTTP_BASE_URL="http://compose-ingestor-1:8001")

    settings.validate_for_runtime()


def test_prod_http_rag_requires_safe_token() -> None:
    settings = _prod_settings(RAG_HTTP_API_TOKEN="short")

    with pytest.raises(ValueError, match="RAG_HTTP_API_TOKEN"):
        settings.validate_for_runtime()
