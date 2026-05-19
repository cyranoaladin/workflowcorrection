"""Backward-compatible wrapper around the pgvector RAG provider."""

from __future__ import annotations

import uuid

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.embedding_service import embed_texts
from app.services.rag.base import RetrievedChunk
from app.services.rag.pgvector_provider import _vector_literal

def retrieve(
    *,
    db: Session,
    exam_id: uuid.UUID,
    question_id: str | None = None,
    query: str,
    top_k: int | None = None,
    kinds: list[str] | None = None,
) -> list[RetrievedChunk]:
    settings = get_settings()
    query_embedding = embed_texts([query])[0]
    sql = """
        SELECT
            chunk.id AS chunk_id,
            chunk.document_id,
            kd.kind,
            chunk.question_id,
            chunk.text,
            chunk.latex,
            chunk.tokens,
            chunk.metadata,
            1 - (chunk.embedding <=> CAST(:query_embedding AS vector)) AS score
        FROM knowledge_chunks chunk
        JOIN knowledge_documents kd ON kd.id = chunk.document_id
        WHERE (kd.exam_id = :exam_id OR kd.exam_id IS NULL)
    """
    params: dict = {
        "exam_id": str(exam_id),
        "query_embedding": _vector_literal(query_embedding),
        "top_k": top_k or settings.RAG_TOP_K,
    }
    if question_id is not None:
        sql += " AND (chunk.question_id = :question_id OR chunk.question_id IS NULL)"
        params["question_id"] = question_id
    if kinds:
        sql += " AND kd.kind = ANY(:kinds)"
        params["kinds"] = kinds
    sql += " ORDER BY chunk.embedding <=> CAST(:query_embedding AS vector) LIMIT :top_k"

    rows = db.execute(sa_text(sql), params).fetchall()
    chunks: list[RetrievedChunk] = []
    for row in rows:
        score = float(row.score)
        if score >= settings.RAG_MIN_SCORE:
            chunks.append(
                RetrievedChunk(
                    id=str(row.chunk_id),
                    document_id=str(row.document_id),
                    chunk_index=int(getattr(row, "chunk_index", 0) or 0),
                    text=row.text,
                    latex=row.latex,
                    question_id=row.question_id,
                    tokens=getattr(row, "tokens", None),
                    metadata=getattr(row, "metadata", None) or {},
                    kind=row.kind,
                    score=score,
                )
            )
    return chunks
