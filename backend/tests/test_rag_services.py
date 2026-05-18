from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_chunk_rubric_json_creates_one_chunk_per_question():
    from app.services.chunking_service import chunk_rubric_json

    chunks = chunk_rubric_json(
        {
            "questions": [
                {
                    "id": "Q1",
                    "label": "Calculer f'(x)",
                    "points_max": 4,
                    "criteria": ["Méthode correcte", "Résultat exact"],
                    "expected_answer": "f'(x)=2x",
                },
                {"id": "Q2", "label": "Calculer une intégrale", "points_max": 6, "criteria": ["Primitive"]},
            ]
        }
    )

    assert [c.question_id for c in chunks] == ["Q1", "Q2"]
    assert "Méthode correcte" in chunks[0].text
    assert chunks[0].metadata["points_max"] == 4


def test_chunk_correction_pdf_tags_french_question_sections():
    from app.services.chunking_service import chunk_correction_pdf

    chunks = chunk_correction_pdf(
        [
            "Question 1\nOn dérive x^2 et on obtient 2x.\n\nQuestion 2\nUne primitive est x^3/3.",
        ],
        [{"id": "Q1", "label": "Dérivée"}, {"id": "Q2", "label": "Intégrale"}],
    )

    assert len(chunks) == 2
    assert chunks[0].question_id == "Q1"
    assert "2x" in chunks[0].text
    assert chunks[1].question_id == "Q2"
    assert "x^3/3" in chunks[1].text


def test_chunk_generic_pdf_keeps_inline_latex_together():
    from app.services.chunking_service import chunk_generic_pdf

    text = "Premier paragraphe avec $x^2+1$ intact.\n\nDeuxième paragraphe avec une conclusion."
    chunks = chunk_generic_pdf(text, max_tokens=6, overlap=1)

    assert chunks
    assert any("$x^2+1$" in c.text for c in chunks)
    assert all(chunk.text.strip() for chunk in chunks)


def test_embed_texts_openai_batches_100_and_retries(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")

    from app.core.config import get_settings

    get_settings.cache_clear()

    first_error = Exception("rate limited")
    calls: list[int] = []

    def create_side_effect(*, model: str, input: list[str]):
        calls.append(len(input))
        if len(calls) == 1:
            raise first_error
        response = MagicMock()
        response.data = [MagicMock(embedding=[float(i), 0.0]) for i, _ in enumerate(input)]
        return response

    with patch("app.services.embedding_service.OpenAI") as mock_client, \
            patch("app.services.embedding_service.time.sleep"):
        mock_client.return_value.embeddings.create.side_effect = create_side_effect

        from app.services.embedding_service import embed_texts

        result = embed_texts([f"chunk {i}" for i in range(101)])

    assert calls == [100, 100, 1]
    assert len(result) == 101


def test_embed_texts_tei_posts_inputs(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "tei")
    monkeypatch.setenv("TEI_ENDPOINT", "http://tei:80")

    from app.core.config import get_settings

    get_settings.cache_clear()

    response = MagicMock()
    response.json.return_value = [[0.1, 0.2], [0.3, 0.4]]
    response.raise_for_status.return_value = None

    with patch("app.services.embedding_service.httpx.post", return_value=response) as mock_post:
        from app.services.embedding_service import embed_texts

        result = embed_texts(["a", "b"])

    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"] == {"inputs": ["a", "b"]}
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_retrieve_filters_by_min_score(monkeypatch):
    monkeypatch.setenv("RAG_MIN_SCORE", "0.35")

    from app.core.config import get_settings

    get_settings.cache_clear()

    rows = [
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "chunk_index": 0,
            "text": "corrigé utile",
            "latex": None,
            "question_id": "Q1",
            "tokens": 12,
            "metadata": {},
            "kind": "correction",
            "score": 0.9,
        },
        {
            "id": "chunk-2",
            "document_id": "doc-2",
            "chunk_index": 1,
            "text": "bruit",
            "latex": None,
            "question_id": None,
            "tokens": 4,
            "metadata": {},
            "kind": "rubric",
            "score": 0.2,
        },
    ]

    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = rows

    with patch("app.services.rag_service.embed_texts", return_value=[[0.1, 0.2]]):
        from app.services.rag_service import retrieve

        result = retrieve(
            db=db,
            exam_id="00000000-0000-0000-0000-000000000001",
            question_id="Q1",
            query="dériver x^2",
            kinds=["correction", "rubric"],
        )

    assert len(result) == 1
    assert result[0].text == "corrigé utile"
    assert result[0].score == 0.9


@pytest.mark.parametrize(
    ("score", "expected_count"),
    [
        (0.10, 0),
        (0.20, 0),
        (0.34, 0),
        (0.35, 1),
        (0.36, 1),
        (0.50, 1),
        (0.70, 1),
        (0.85, 1),
        (0.99, 1),
        (1.00, 1),
    ],
)
def test_retrieve_min_score_threshold_cases(monkeypatch, score, expected_count):
    monkeypatch.setenv("RAG_MIN_SCORE", "0.35")

    from app.core.config import get_settings

    get_settings.cache_clear()

    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "id": "chunk",
            "document_id": "doc",
            "chunk_index": 0,
            "text": "contenu",
            "latex": None,
            "question_id": "Q1",
            "tokens": 3,
            "metadata": {},
            "kind": "rubric",
            "score": score,
        }
    ]

    with patch("app.services.rag_service.embed_texts", return_value=[[0.1, 0.2]]):
        from app.services.rag_service import retrieve

        result = retrieve(
            db=db,
            exam_id="00000000-0000-0000-0000-000000000001",
            question_id="Q1",
            query="barème",
            top_k=3,
            kinds=["rubric"],
        )

    params = db.execute.call_args.args[1]
    assert params["exam_id"] == "00000000-0000-0000-0000-000000000001"
    assert params["question_id"] == "Q1"
    assert params["kinds"] == ["rubric"]
    assert params["top_k"] == 3
    assert len(result) == expected_count
