from __future__ import annotations

from typing import Any

from sqlalchemy import text as sa_text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.embedding_service import embed_texts
from app.services.rag.base import RetrievedChunk


class PgvectorRagProvider:
    def health(self) -> bool:
        return True

    def retrieve(
        self,
        *,
        exam_id: str | None,
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
                chunk.chunk_index,
                kd.kind,
                chunk.question_id,
                chunk.text,
                chunk.latex,
                chunk.tokens,
                chunk.metadata,
                1 - (chunk.embedding <=> CAST(:query_embedding AS vector)) AS score
            FROM knowledge_chunks chunk
            JOIN knowledge_documents kd ON kd.id = chunk.document_id
            WHERE (:exam_id IS NULL OR kd.exam_id = :exam_id OR kd.exam_id IS NULL)
        """
        params: dict[str, Any] = {
            "exam_id": str(exam_id) if exam_id else None,
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

        with SessionLocal() as db:
            rows = db.execute(sa_text(sql), params).fetchall()

        return [
            RetrievedChunk(
                id=str(row.chunk_id),
                document_id=str(row.document_id),
                chunk_index=int(row.chunk_index),
                text=row.text,
                latex=row.latex,
                question_id=row.question_id,
                tokens=row.tokens,
                metadata=row.metadata or {},
                kind=row.kind,
                score=float(row.score),
            )
            for row in rows
            if float(row.score) >= settings.RAG_MIN_SCORE
        ]

    def ingest_document(self, **_: Any) -> dict[str, Any]:
        raise NotImplementedError("pgvector ingestion is handled by embed_exam_task")


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
