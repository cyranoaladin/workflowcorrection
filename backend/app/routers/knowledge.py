"""Knowledge / RAG endpoints for exam document embedding and retrieval."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.exam import Exam
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

router = APIRouter(prefix="/exams", tags=["knowledge"])


class EmbedResponse(BaseModel):
    status: str
    task_id: str | None = None
    chunks_count: int | None = None


class KnowledgeDocumentRead(BaseModel):
    id: UUID
    exam_id: UUID | None
    kind: str
    source_path: str
    content_hash: str
    title: str | None
    chunks_count: int

    class Config:
        from_attributes = True


class KnowledgeListResponse(BaseModel):
    documents: list[KnowledgeDocumentRead]
    total_chunks: int


@router.post("/{exam_id}/embed", response_model=EmbedResponse)
def embed_exam(
    exam_id: UUID,
    force: bool = Query(False, description="Re-embed even if documents haven't changed"),
    db: Session = Depends(get_db),
) -> EmbedResponse:
    """Launch embedding of all exam documents into the knowledge base.

    This is idempotent: if documents haven't changed and force=False, they are skipped.
    """
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    from app.workers.embed_tasks import embed_exam_task

    task = embed_exam_task.delay(str(exam_id), force=force)
    return _build_embed_response(task)


def _build_embed_response(task) -> EmbedResponse:
    if task.ready():
        result = task.result or {}
        return EmbedResponse(
            status=result.get("status", "completed"),
            task_id=task.id,
            chunks_count=result.get("chunks_count", 0),
        )
    return EmbedResponse(status="queued", task_id=task.id)


@router.get("/{exam_id}/knowledge", response_model=KnowledgeListResponse)
def list_knowledge(exam_id: UUID, db: Session = Depends(get_db)) -> KnowledgeListResponse:
    """List all knowledge documents and their status for an exam."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    docs_with_count = (
        db.query(KnowledgeDocument, func.count(KnowledgeChunk.id).label("chunk_count"))
        .outerjoin(KnowledgeChunk)
        .filter((KnowledgeDocument.exam_id == exam_id) | (KnowledgeDocument.exam_id.is_(None)))
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )

    documents: list[KnowledgeDocumentRead] = []
    total_chunks = 0
    for doc, chunk_count in docs_with_count:
        total_chunks += chunk_count
        documents.append(KnowledgeDocumentRead(
            id=doc.id,
            exam_id=doc.exam_id,
            kind=doc.kind,
            source_path=doc.source_path,
            content_hash=doc.content_hash,
            title=doc.title,
            chunks_count=chunk_count,
        ))

    return KnowledgeListResponse(documents=documents, total_chunks=total_chunks)
