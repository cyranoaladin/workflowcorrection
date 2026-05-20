"""Embedding service — wraps OpenAI or TEI for text → vector conversion."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import httpx
from openai import OpenAI, RateLimitError

from app.core.config import get_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Max texts per batch for OpenAI embeddings API
_OPENAI_BATCH_SIZE = 100
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the configured provider.

    Returns a list of float vectors, one per input text.
    Raises ValueError if provider is misconfigured.
    """
    settings = get_settings()

    if not texts:
        return []

    if settings.EMBEDDING_PROVIDER == "openai":
        embeddings = _embed_openai(texts, settings.EMBEDDING_MODEL, settings.EMBEDDING_DIMENSION)
    elif settings.EMBEDDING_PROVIDER == "tei":
        embeddings = _embed_tei(texts, settings.TEI_ENDPOINT)
    else:
        raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")

    expected = getattr(settings, "EMBEDDING_DIMENSION", None)
    if not isinstance(expected, int):
        expected = len(embeddings[0]) if embeddings else 0
    for index, embedding in enumerate(embeddings):
        if len(embedding) != expected:
            raise ValueError(
                f"embedding_dimension_mismatch: provider returned dim={len(embedding)} "
                f"but EMBEDDING_DIMENSION={expected} (chunk #{index})"
            )
    return embeddings


def _embed_openai(texts: list[str], model: str, dimensions: int) -> list[list[float]]:
    """Batch embed via OpenAI API with retry on rate limit."""
    settings = get_settings()

    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai. " "Set it in your .env file.")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _OPENAI_BATCH_SIZE):
        batch = texts[i : i + _OPENAI_BATCH_SIZE]
        embedding = _call_openai_with_retry(client, batch, model, dimensions)
        all_embeddings.extend(embedding)

    return all_embeddings


def _call_openai_with_retry(client: OpenAI, texts: list[str], model: str, dimensions: int) -> list[list[float]]:
    """Call OpenAI embeddings with exponential backoff retry on RateLimitError."""
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.embeddings.create(
                input=texts,
                model=model,
                dimensions=dimensions,
            )
            return [item.embedding for item in response.data]
        except RateLimitError as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "OpenAI rate limit hit (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                _MAX_RETRIES,
                delay,
                str(e),
            )
            time.sleep(delay)

    # Should not reach here
    raise RuntimeError("Exhausted retries for OpenAI embedding call")


def _embed_tei(texts: list[str], endpoint: str) -> list[list[float]]:
    """Embed via Hugging Face Text Embeddings Inference (TEI) server."""
    if not endpoint:
        raise ValueError("TEI_ENDPOINT is required when EMBEDDING_PROVIDER=tei. " "Set it in your .env file.")

    url = endpoint.rstrip("/") + "/embed"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json={"inputs": texts})
        response.raise_for_status()
        return response.json()
