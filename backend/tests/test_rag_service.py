"""Tests for the pgvector RAG provider with mocked embedding + DB calls."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.rag import _vector_literal
from app.services.rag.pgvector_provider import PgvectorRagProvider


class TestVectorLiteral:
    def test_format(self):
        result = _vector_literal([0.1, 0.2, 0.3])
        assert result.startswith("[")
        assert result.endswith("]")
        assert "0.10000000" in result

    def test_empty(self):
        result = _vector_literal([])
        assert result == "[]"


class TestRetrieve:
    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_basic_retrieval(self, mock_settings, mock_embed, mock_session_local):
        """Should call embed_texts, execute SQL, and filter by min_score."""
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.3
        mock_settings.return_value = settings

        mock_embed.return_value = [[0.1] * 1536]

        # Mock DB session
        db = MagicMock()
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.chunk_id = chunk_id
        mock_row.document_id = doc_id
        mock_row.chunk_index = 7
        mock_row.kind = "correction"
        mock_row.question_id = "Q1"
        mock_row.text = "La dérivée de x^2 est 2x"
        mock_row.latex = "$f'(x) = 2x$"
        mock_row.score = 0.85

        db.execute.return_value.fetchall.return_value = [mock_row]
        mock_session_local.return_value.__enter__.return_value = db

        exam_id = uuid.uuid4()
        results = PgvectorRagProvider().retrieve(
            exam_id=exam_id,
            question_id="Q1",
            query="Quelle est la dérivée de f?",
        )

        assert len(results) == 1
        assert results[0].score == 0.85
        assert results[0].chunk_index == 7
        assert results[0].kind == "correction"
        assert results[0].question_id == "Q1"
        mock_embed.assert_called_once_with(["Quelle est la dérivée de f?"])

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_filters_below_min_score(self, mock_settings, mock_embed, mock_session_local):
        """Chunks with score below RAG_MIN_SCORE should be excluded."""
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.5
        mock_settings.return_value = settings

        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        low_score_row = MagicMock()
        low_score_row.chunk_id = uuid.uuid4()
        low_score_row.document_id = uuid.uuid4()
        low_score_row.chunk_index = 0
        low_score_row.kind = "rubric"
        low_score_row.question_id = None
        low_score_row.text = "Low relevance text"
        low_score_row.latex = None
        low_score_row.score = 0.3

        db.execute.return_value.fetchall.return_value = [low_score_row]

        results = PgvectorRagProvider().retrieve(exam_id=uuid.uuid4(), query="test")
        assert len(results) == 0

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_custom_top_k(self, mock_settings, mock_embed, mock_session_local):
        """Should use custom top_k when provided."""
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.0
        mock_settings.return_value = settings

        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        db.execute.return_value.fetchall.return_value = []

        PgvectorRagProvider().retrieve(exam_id=uuid.uuid4(), query="test", top_k=3)
        # Check that the SQL uses our top_k
        call_args = db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert params["top_k"] == 3

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_kinds_filter(self, mock_settings, mock_embed, mock_session_local):
        """Should pass kinds filter in SQL when provided."""
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.0
        mock_settings.return_value = settings

        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        db.execute.return_value.fetchall.return_value = []

        PgvectorRagProvider().retrieve(exam_id=uuid.uuid4(), query="test", kinds=["correction", "rubric"])
        call_args = db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert params["kinds"] == ["correction", "rubric"]

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_no_question_filter(self, mock_settings, mock_embed, mock_session_local):
        """When question_id is None, SQL should not filter by question."""
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.0
        mock_settings.return_value = settings

        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        db.execute.return_value.fetchall.return_value = []

        PgvectorRagProvider().retrieve(exam_id=uuid.uuid4(), query="test", question_id=None)
        call_args = db.execute.call_args
        sql_text = str(call_args[0][0])
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]["params"]
        assert "question_id" not in params or params["question_id"] is None
        assert "chunk.question_id = :question_id" not in sql_text

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_multiple_results_sorted(self, mock_settings, mock_embed, mock_session_local):
        """Multiple results should be returned in score order (DB handles ordering)."""
        settings = MagicMock()
        settings.RAG_TOP_K = 10
        settings.RAG_MIN_SCORE = 0.3
        mock_settings.return_value = settings

        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        rows = []
        for i, score in enumerate([0.9, 0.7, 0.5, 0.2]):
            row = MagicMock()
            row.chunk_id = uuid.uuid4()
            row.document_id = uuid.uuid4()
            row.chunk_index = i
            row.kind = "correction"
            row.question_id = f"Q{i+1}"
            row.text = f"chunk {i}"
            row.latex = None
            row.score = score
            rows.append(row)

        db.execute.return_value.fetchall.return_value = rows

        results = PgvectorRagProvider().retrieve(exam_id=uuid.uuid4(), query="test")
        # Should filter out score=0.2 (below 0.3)
        assert len(results) == 3
        assert results[0].score == 0.9
        assert results[2].score == 0.5

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_empty_db_returns_empty(self, mock_settings, mock_embed, mock_session_local):
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.3
        mock_settings.return_value = settings
        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        db.execute.return_value.fetchall.return_value = []

        results = PgvectorRagProvider().retrieve(exam_id=uuid.uuid4(), query="anything")
        assert results == []

    @patch("app.services.rag.pgvector_provider.SessionLocal")
    @patch("app.services.rag.pgvector_provider.embed_texts")
    @patch("app.services.rag.pgvector_provider.get_settings")
    def test_exam_scoping(self, mock_settings, mock_embed, mock_session_local):
        """SQL should scope to exam_id OR exam_id IS NULL (user global docs)."""
        settings = MagicMock()
        settings.RAG_TOP_K = 5
        settings.RAG_MIN_SCORE = 0.0
        mock_settings.return_value = settings
        mock_embed.return_value = [[0.1] * 1536]

        db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = db
        db.execute.return_value.fetchall.return_value = []

        exam_id = uuid.uuid4()
        PgvectorRagProvider().retrieve(exam_id=exam_id, query="test")
        call_args = db.execute.call_args
        params = call_args[0][1]
        assert params["exam_id"] == str(exam_id)
        sql_str = str(call_args[0][0])
        assert "exam_id IS NULL" in sql_str
