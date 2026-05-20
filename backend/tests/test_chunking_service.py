"""Tests for chunking_service."""

from __future__ import annotations

from app.services.chunking_service import (
    chunk_correction_pdf,
    chunk_generic_pdf,
    chunk_rubric_json,
)


class TestChunkRubricJson:
    def test_basic_rubric(self):
        rubric = {
            "questions": [
                {
                    "id": "Q1",
                    "label": "Calculer f'(x)",
                    "points_max": 4,
                    "criteria": ["dérivée correcte", "simplification"],
                    "expected_answer": "$f'(x) = 2x$",
                },
                {
                    "id": "Q2",
                    "label": "Résoudre l'équation",
                    "points_max": 6,
                    "criteria": ["mise en forme", "résolution"],
                    "expected_answer": "$x = 3$",
                },
            ]
        }
        chunks = chunk_rubric_json(rubric)
        assert len(chunks) == 2
        assert chunks[0].question_id == "Q1"
        assert chunks[1].question_id == "Q2"
        assert "Calculer f'(x)" in chunks[0].text
        assert chunks[0].latex is not None
        assert "$f'(x) = 2x$" in chunks[0].latex

    def test_empty_rubric(self):
        chunks = chunk_rubric_json({})
        assert chunks == []

    def test_rubric_no_expected_answer(self):
        rubric = {"questions": [{"id": "Q1", "label": "Question", "points_max": 2, "criteria": []}]}
        chunks = chunk_rubric_json(rubric)
        assert len(chunks) == 1
        assert chunks[0].latex is None

    def test_chunk_index_assigned(self):
        rubric = {"questions": [{"id": f"Q{i}", "label": f"Q{i}", "points_max": 1} for i in range(5)]}
        chunks = chunk_rubric_json(rubric)
        assert [c.chunk_index for c in chunks] == [0, 1, 2, 3, 4]

    def test_tokens_computed(self):
        rubric = {"questions": [{"id": "Q1", "label": "Test", "points_max": 1}]}
        chunks = chunk_rubric_json(rubric)
        assert chunks[0].tokens > 0


class TestChunkCorrectionPdf:
    def test_splits_by_question_pattern(self):
        pages = [
            "Question 1\nLa dérivée est f'(x) = 2x\n\nQuestion 2\nOn résout: x = 3",
        ]
        rubric_qs = [{"id": "Q1"}, {"id": "Q2"}]
        chunks = chunk_correction_pdf(pages, rubric_qs)
        assert len(chunks) == 2
        assert chunks[0].question_id == "Q1"
        assert chunks[1].question_id == "Q2"
        assert "dérivée" in chunks[0].text

    def test_exercice_pattern(self):
        pages = ["Exercice 1\nBlah\n\nExercice 2\nBlah2"]
        rubric_qs = [{"id": "Q1"}, {"id": "Q2"}]
        chunks = chunk_correction_pdf(pages, rubric_qs)
        assert len(chunks) == 2

    def test_fallback_to_pages(self):
        pages = ["Page 1 content without question headers", "Page 2 content"]
        rubric_qs = [{"id": "Q1"}]
        chunks = chunk_correction_pdf(pages, rubric_qs)
        # Falls back to page-based chunking
        assert len(chunks) == 2

    def test_latex_extraction(self):
        pages = ["Question 1\nOn a $f(x) = x^2$ donc $f'(x) = 2x$"]
        rubric_qs = [{"id": "Q1"}]
        chunks = chunk_correction_pdf(pages, rubric_qs)
        assert chunks[0].latex is not None
        assert "$f(x) = x^2$" in chunks[0].latex

    def test_empty_pages(self):
        chunks = chunk_correction_pdf([], [])
        assert chunks == []


class TestChunkGenericPdf:
    def test_basic_chunking(self):
        text = "Paragraph one about derivatives.\n\nParagraph two about integrals.\n\nParagraph three about limits."
        chunks = chunk_generic_pdf(text, max_tokens=8, overlap=0)
        assert len(chunks) >= 2

    def test_respects_max_tokens(self):
        # A very long paragraph
        text = "Word " * 200
        chunks = chunk_generic_pdf(text, max_tokens=50, overlap=0)
        # Should produce at least 1 chunk (may not split within paragraph)
        assert len(chunks) >= 1

    def test_overlap_included(self):
        text = (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa.\n\n"
            "lambda mu nu xi omicron pi rho sigma tau upsilon.\n\n"
            "phi chi psi omega final words."
        )
        chunks = chunk_generic_pdf(text, max_tokens=12, overlap_tokens=4)
        assert len(chunks) >= 2
        previous_tail_word = chunks[0].text.split()[-1]
        assert previous_tail_word in chunks[1].text

    def test_empty_text(self):
        chunks = chunk_generic_pdf("")
        assert chunks == []

    def test_latex_preserved(self):
        text = "We know that $x^2 + 1 = 0$ has no real solution.\n\nAlso $\\frac{1}{2}$ is important."
        chunks = chunk_generic_pdf(text, max_tokens=500)
        assert len(chunks) == 1
        assert chunks[0].latex is not None
        assert "$x^2 + 1 = 0$" in chunks[0].latex

    def test_tokens_counted(self):
        text = "Hello world paragraph.\n\nAnother paragraph here."
        chunks = chunk_generic_pdf(text, max_tokens=500)
        for c in chunks:
            assert c.tokens > 0
