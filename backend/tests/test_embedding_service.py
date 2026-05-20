"""Tests for embedding_service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.services.embedding_service import embed_texts


class TestEmbedTexts:
    @patch("app.services.embedding_service.get_settings")
    @patch("app.services.embedding_service.OpenAI")
    def test_openai_single_text(self, mock_openai_cls, mock_settings):
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "openai"
        settings.EMBEDDING_MODEL = "text-embedding-3-small"
        settings.EMBEDDING_DIMENSION = 1536
        settings.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value = settings

        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_client.embeddings.create.return_value = mock_response

        result = embed_texts(["hello world"])
        assert len(result) == 1
        assert len(result[0]) == 1536
        mock_client.embeddings.create.assert_called_once()

    @patch("app.services.embedding_service.get_settings")
    @patch("app.services.embedding_service.OpenAI")
    def test_openai_batching(self, mock_openai_cls, mock_settings):
        """Texts beyond batch size should be split into multiple API calls."""
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "openai"
        settings.EMBEDDING_MODEL = "text-embedding-3-small"
        settings.EMBEDDING_DIMENSION = 1536
        settings.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value = settings

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # 150 texts should require 2 batches (100 + 50)
        texts = [f"text {i}" for i in range(150)]

        def mock_create(**kwargs):
            batch = kwargs["input"]
            resp = MagicMock()
            resp.data = [MagicMock(embedding=[0.5] * 1536) for _ in batch]
            return resp

        mock_client.embeddings.create.side_effect = mock_create
        result = embed_texts(texts)

        assert len(result) == 150
        assert mock_client.embeddings.create.call_count == 2

    @patch("app.services.embedding_service.get_settings")
    def test_empty_list(self, mock_settings):
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "openai"
        mock_settings.return_value = settings

        result = embed_texts([])
        assert result == []

    @patch("app.services.embedding_service.get_settings")
    def test_openai_missing_key_raises(self, mock_settings):
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "openai"
        settings.EMBEDDING_MODEL = "text-embedding-3-small"
        settings.EMBEDDING_DIMENSION = 1536
        settings.OPENAI_API_KEY = ""
        mock_settings.return_value = settings

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            embed_texts(["test"])

    @patch("app.services.embedding_service.get_settings")
    def test_tei_missing_endpoint_raises(self, mock_settings):
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "tei"
        settings.TEI_ENDPOINT = ""
        mock_settings.return_value = settings

        with pytest.raises(ValueError, match="TEI_ENDPOINT"):
            embed_texts(["test"])

    @patch("app.services.embedding_service.get_settings")
    @patch("app.services.embedding_service.httpx.Client")
    def test_tei_provider(self, mock_httpx_client, mock_settings):
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "tei"
        settings.TEI_ENDPOINT = "http://tei:80"
        mock_settings.return_value = settings

        mock_ctx = MagicMock()
        mock_httpx_client.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_httpx_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [[0.2] * 1024]
        mock_resp.raise_for_status = MagicMock()
        mock_ctx.post.return_value = mock_resp

        result = embed_texts(["test tei"])
        assert len(result) == 1
        mock_ctx.post.assert_called_once_with("http://tei:80/embed", json={"inputs": ["test tei"]})

    @patch("app.services.embedding_service.get_settings")
    def test_unknown_provider_raises(self, mock_settings):
        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "unknown"
        mock_settings.return_value = settings

        with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
            embed_texts(["test"])

    @patch("app.services.embedding_service.get_settings")
    @patch("app.services.embedding_service.OpenAI")
    @patch("app.services.embedding_service.time.sleep")
    def test_openai_retry_on_rate_limit(self, mock_sleep, mock_openai_cls, mock_settings):
        """Should retry on RateLimitError with exponential backoff."""
        from openai import RateLimitError

        settings = MagicMock()
        settings.EMBEDDING_PROVIDER = "openai"
        settings.EMBEDDING_MODEL = "text-embedding-3-small"
        settings.EMBEDDING_DIMENSION = 1536
        settings.OPENAI_API_KEY = "sk-test"
        mock_settings.return_value = settings

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Fail twice then succeed
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1] * 1536)]

        mock_error = RateLimitError(
            message="Rate limit",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.embeddings.create.side_effect = [mock_error, mock_error, mock_resp]

        # Should not raise (3 retries configured, fails 2 times then succeeds)
        # Actually _MAX_RETRIES is 3 so attempt 0 fails, attempt 1 fails, attempt 2 succeeds
        result = embed_texts(["test"])
        assert len(result) == 1
        assert mock_sleep.call_count == 2
