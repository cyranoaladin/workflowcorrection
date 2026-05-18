from __future__ import annotations

import time

import httpx
from openai import OpenAI, RateLimitError

from app.core.config import get_settings

_OPENAI_BATCH_SIZE = 100


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text chunks using the configured embedding provider."""
    if not texts:
        return []

    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "tei":
        return _embed_texts_tei(texts)
    return _embed_texts_openai(texts)


def _embed_texts_openai(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), _OPENAI_BATCH_SIZE):
        batch = texts[start:start + _OPENAI_BATCH_SIZE]
        response = _create_openai_embedding_with_retry(client, settings.EMBEDDING_MODEL, batch)
        embeddings.extend([list(item.embedding) for item in response.data])
    return embeddings


def _create_openai_embedding_with_retry(client: OpenAI, model: str, batch: list[str]):
    delay = 1.0
    for attempt in range(3):
        try:
            return client.embeddings.create(model=model, input=batch)
        except RateLimitError:
            if attempt == 2:
                raise
            time.sleep(delay)
            delay *= 2
        except Exception as exc:
            if "rate" not in str(exc).lower() or attempt == 2:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("embedding retry loop exhausted")


def _embed_texts_tei(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.TEI_ENDPOINT:
        raise RuntimeError("TEI_ENDPOINT is required when EMBEDDING_PROVIDER=tei")

    response = httpx.post(
        f"{settings.TEI_ENDPOINT.rstrip('/')}/embed",
        json={"inputs": texts},
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    return [list(map(float, item)) for item in data]
