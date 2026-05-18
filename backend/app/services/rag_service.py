from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.embedding_service import embed_texts


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    document_id: str
    chunk_index: int
    text: str
    latex: str | None
    question_id: str | None
    tokens: int | None
    metadata: dict[str, Any]
    kind: str
    score: float


def retrieve(
    *,
    db: Session,
    exam_id: Any,
    question_id: str | None,
    query: str,
    top_k: int | None = None,
    kinds: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Retrieve semantically similar knowledge chunks for an exam/question."""
    settings = get_settings()
    requested_top_k = top_k or settings.RAG_TOP_K
    query_embedding = _vector_literal(embed_texts([query])[0])

    sql = text(
        """
        SELECT
          kc.id::text AS id,
          kc.document_id::text AS document_id,
          kc.chunk_index,
          kc.text,
          kc.latex,
          kc.question_id,
          kc.tokens,
          kc.metadata,
          kd.kind,
          1 - (kc.embedding <=> CAST(:query_embedding AS vector)) AS score
        FROM knowledge_chunks kc
        JOIN knowledge_documents kd ON kd.id = kc.document_id
        WHERE (kd.exam_id = :exam_id OR kd.exam_id IS NULL)
          AND (:question_id IS NULL OR kc.question_id = :question_id OR kc.question_id IS NULL)
          AND (:kinds IS NULL OR kd.kind = ANY(:kinds))
        ORDER BY kc.embedding <=> CAST(:query_embedding AS vector)
        LIMIT :top_k
        """
    )
    rows = db.execute(
        sql,
        {
            "exam_id": str(exam_id),
            "question_id": question_id,
            "kinds": kinds,
            "query_embedding": query_embedding,
            "top_k": requested_top_k,
        },
    ).mappings().all()

    return [
        RetrievedChunk(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
            latex=row["latex"],
            question_id=row["question_id"],
            tokens=row["tokens"],
            metadata=row["metadata"] or {},
            kind=str(row["kind"]),
            score=float(row["score"]),
        )
        for row in rows
        if float(row["score"]) >= settings.RAG_MIN_SCORE
    ]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"
