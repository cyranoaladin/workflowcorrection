"""RAG service — retrieves relevant knowledge chunks for grading context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.embedding_service import embed_texts


@dataclass
class RetrievedChunk:
    """A knowledge chunk retrieved by similarity search."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    kind: str
    question_id: str | None
    text: str
    latex: str | None
    score: float


def retrieve(
    *,
    db: Session,
    exam_id: uuid.UUID,
    question_id: str | None = None,
    query: str,
    top_k: int | None = None,
    kinds: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Retrieve most relevant knowledge chunks for a given query.

    Args:
        db: SQLAlchemy session.
        exam_id: The exam to scope retrieval to (also includes user-global docs where exam_id IS NULL).
        question_id: Optional question filter (includes chunks with NULL question_id too).
        query: The text query to embed and search for.
        top_k: Number of results (defaults to RAG_TOP_K from config).
        kinds: Optional list of document kinds to filter on.

    Returns:
        List of RetrievedChunk sorted by relevance (highest score first).
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.RAG_TOP_K

    # Embed the query
    query_embedding = embed_texts([query])[0]

    # Build the SQL query
    # pgvector cosine distance: embedding <=> query gives distance, score = 1 - distance
    sql = """
        SELECT
            chunk.id AS chunk_id,
            chunk.document_id,
            kd.kind,
            chunk.question_id,
            chunk.text,
            chunk.latex,
            1 - (chunk.embedding <=> :query_embedding::vector) AS score
        FROM knowledge_chunks chunk
        JOIN knowledge_documents kd ON kd.id = chunk.document_id
        WHERE (kd.exam_id = :exam_id OR kd.exam_id IS NULL)
    """

    params: dict = {
        "exam_id": str(exam_id),
        "query_embedding": _vector_literal(query_embedding),
    }

    if question_id is not None:
        sql += " AND (chunk.question_id = :question_id OR chunk.question_id IS NULL)"
        params["question_id"] = question_id

    if kinds:
        sql += " AND kd.kind = ANY(:kinds)"
        params["kinds"] = kinds

    sql += """
        ORDER BY chunk.embedding <=> :query_embedding::vector
        LIMIT :top_k
    """
    params["top_k"] = top_k

    result = db.execute(sa_text(sql), params)
    rows = result.fetchall()

    # Filter by minimum score
    min_score = settings.RAG_MIN_SCORE
    chunks: list[RetrievedChunk] = []
    for row in rows:
        score = float(row.score)
        if score >= min_score:
            chunks.append(RetrievedChunk(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                kind=row.kind,
                question_id=row.question_id,
                text=row.text,
                latex=row.latex,
                score=score,
            ))

    return chunks


def _vector_literal(embedding: list[float]) -> str:
    """Convert a list of floats to a pgvector literal string '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
