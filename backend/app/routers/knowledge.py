"""Knowledge / RAG endpoints for exam document embedding and retrieval."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
    metadata: dict
    created_at: str
    updated_at: str

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

    metadata = dict(exam.metadata_json or {})
    metadata["embedding_status"] = "queued"
    metadata["embedded_queued_at"] = datetime.now(UTC).isoformat()
    exam.metadata_json = metadata
    db.add(exam)
    db.commit()

    from app.workers.embed_tasks import embed_exam_task

    try:
        task = embed_exam_task.apply_async(
            args=[str(exam_id)],
            kwargs={"force": force},
            task_id=_new_embed_task_id(exam_id),
        )
    except Exception as err:
        # Broker failure — rollback the queued status
        metadata.pop("embedding_status", None)
        metadata.pop("embedded_queued_at", None)
        exam.metadata_json = metadata
        db.add(exam)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue embedding task. Please try again later.",
        ) from err
    return _build_embed_response(task)


def _build_embed_response(task) -> EmbedResponse:
    if task.ready():
        result = task.result if isinstance(task.result, dict) else {}
        fallback_status = str(getattr(task, "status", "completed")).lower()
        return EmbedResponse(
            status=result.get("status", fallback_status),
            task_id=task.id,
            chunks_count=result.get("chunks_count", 0),
        )
    return EmbedResponse(status="queued", task_id=task.id)


def _new_embed_task_id(exam_id: UUID) -> str:
    return f"embed_exam:{exam_id}:{uuid.uuid4()}"


def _embed_task_belongs_to_exam(task_id: str, exam_id: UUID) -> bool:
    prefix = f"embed_exam:{exam_id}:"
    return task_id.startswith(prefix)


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
        effective_chunks_count = chunk_count or int((doc.metadata_ or {}).get("chunks_count", 0) or 0)
        total_chunks += effective_chunks_count
        documents.append(
            KnowledgeDocumentRead(
                id=doc.id,
                exam_id=doc.exam_id,
                kind=doc.kind,
                source_path=doc.source_path,
                content_hash=doc.content_hash,
                title=doc.title,
                chunks_count=effective_chunks_count,
                metadata=doc.metadata_ or {},
                created_at=doc.created_at.isoformat(),
                updated_at=doc.updated_at.isoformat(),
            )
        )

    return KnowledgeListResponse(documents=documents, total_chunks=total_chunks)


@router.get("/{exam_id}/embed/status", response_model=EmbedResponse)
def embed_status(
    exam_id: UUID,
    task_id: str = Query(..., description="Celery task id returned by POST /embed"),
    db: Session = Depends(get_db),
) -> EmbedResponse:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if not _embed_task_belongs_to_exam(task_id, exam_id):
        raise HTTPException(status_code=404, detail="Embedding task not found")

    from app.workers.celery_app import celery

    task = celery.AsyncResult(task_id)
    if task.ready():
        result = task.result if isinstance(task.result, dict) else {}
        return EmbedResponse(
            status=result.get("status", task.status.lower()),
            task_id=task_id,
            chunks_count=result.get("chunks_count", 0),
        )
    return EmbedResponse(status=task.status.lower(), task_id=task_id)
