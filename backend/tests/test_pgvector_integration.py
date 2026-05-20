from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

from app.core.database import SessionLocal
from app.models.exam import Exam
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.rag.pgvector_provider import PgvectorRagProvider


def test_pgvector_retrieve_orders_by_cosine_similarity() -> None:
    db = SessionLocal()
    try:
        exam = Exam(
            title=f"pgvector-{uuid.uuid4()}",
            total_points=Decimal("10"),
            rubric_json={"questions": []},
        )
        db.add(exam)
        db.flush()
        doc = KnowledgeDocument(
            exam_id=exam.id,
            kind="correction",
            source_path="synthetic.md",
            content_hash=f"hash-{uuid.uuid4()}",
            title="Synthetic",
        )
        db.add(doc)
        db.flush()
        vectors = [
            ([1.0] + [0.0] * 1535, "best"),
            ([0.8, 0.2] + [0.0] * 1534, "second"),
            ([0.2, 0.8] + [0.0] * 1534, "third"),
            ([-1.0] + [0.0] * 1535, "opposite"),
            ([0.0, -1.0] + [0.0] * 1534, "other"),
        ]
        for index, (embedding, label) in enumerate(vectors):
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    chunk_index=index,
                    text=label,
                    question_id="Q1",
                    embedding=embedding,
                )
            )
        db.commit()

        settings = type("Settings", (), {"RAG_TOP_K": 5, "RAG_MIN_SCORE": -1.0})()
        with (
            patch("app.services.rag.pgvector_provider.embed_texts", return_value=[[1.0] + [0.0] * 1535]),
            patch("app.services.rag.pgvector_provider.get_settings", return_value=settings),
        ):
            chunks = PgvectorRagProvider().retrieve(
                exam_id=exam.id,
                question_id="Q1",
                query="synthetic",
                top_k=3,
            )

        assert [chunk.text for chunk in chunks[:3]] == ["best", "second", "third"]
        assert [chunk.chunk_index for chunk in chunks[:3]] == [0, 1, 2]
    finally:
        db.rollback()
        if "exam" in locals():
            db.query(Exam).filter(Exam.id == exam.id).delete(synchronize_session=False)
            db.commit()
        db.close()
