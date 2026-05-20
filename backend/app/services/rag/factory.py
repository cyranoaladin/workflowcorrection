from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.rag.base import RagProvider
from app.services.rag.http_provider import HttpRagProvider
from app.services.rag.pgvector_provider import PgvectorRagProvider


@lru_cache(maxsize=1)
def get_rag_provider() -> RagProvider:
    settings = get_settings()
    if settings.RAG_PROVIDER == "http":
        return HttpRagProvider(
            base_url=settings.RAG_HTTP_BASE_URL,
            token=settings.RAG_HTTP_API_TOKEN,
            auth_header=settings.RAG_HTTP_AUTH_HEADER,
            timeout=settings.RAG_HTTP_TIMEOUT_SECONDS,
            collection=settings.RAG_HTTP_COLLECTION,
        )
    return PgvectorRagProvider()
