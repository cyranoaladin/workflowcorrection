"""Celery tasks for embedding exam documents into the knowledge base."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import get_storage
from app.models.exam import Exam
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.chunking_service import (
    Chunk,
    chunk_correction_pdf,
    chunk_generic_pdf,
    chunk_rubric_json,
)
from app.services.embedding_service import embed_texts
from app.services.rag.factory import get_rag_provider
from app.workers.celery_app import celery

logger = get_task_logger(__name__)


@celery.task(name="embed_exam", bind=True, max_retries=2, default_retry_delay=30)
def embed_exam_task(self, exam_id: str, force: bool = False) -> dict:
    """Embed all documents for an exam into the knowledge base.

    Steps:
        1. Load exam and its documents (correction_pdf, rubric_json, rubric_pdf).
        2. For each document, compute content_hash.
        3. If already embedded and force=False, skip.
        4. Otherwise: extract text, chunk, embed, persist.
        5. Update exam metadata with embedding status.

    Returns:
        Dict with status and chunks_count.
    """
    db: Session = SessionLocal()
    try:
        exam = db.query(Exam).filter(Exam.id == uuid.UUID(exam_id)).first()
        if not exam:
            return {"status": "error", "message": "Exam not found"}

        storage = get_storage()
        use_http_rag = get_settings().RAG_PROVIDER == "http"
        total_chunks = 0

        # 1. Embed rubric JSON if available
        if exam.rubric_json:
            rubric_hash = _hash_json(exam.rubric_json)
            if _should_process_document(
                db,
                use_http_rag=use_http_rag,
                force=force,
                exam_id=exam.id,
                content_hash=rubric_hash,
            ):
                chunks = chunk_rubric_json(exam.rubric_json)
                if use_http_rag:
                    chunks_count = _ingest_chunks_with_provider(
                        chunks,
                        exam_id=exam.id,
                        kind="rubric",
                        source_path="rubric_json",
                        content_hash=rubric_hash,
                        title=f"Barème - {exam.title}",
                        force=force,
                    )
                    total_chunks += chunks_count
                    _upsert_external_document_record(
                        db,
                        exam_id=exam.id,
                        kind="rubric",
                        source_path="rubric_json",
                        content_hash=rubric_hash,
                        title=f"Barème - {exam.title}",
                        chunks_count=chunks_count,
                        force=force,
                    )
                else:
                    total_chunks += _persist_chunks(
                        db,
                        chunks,
                        exam_id=exam.id,
                        kind="rubric",
                        source_path="rubric_json",
                        content_hash=rubric_hash,
                        title=f"Barème - {exam.title}",
                        force=force,
                    )

        # 2. Embed correction PDF if available
        if exam.correction_pdf_path:
            pdf_bytes = storage.read(exam.correction_pdf_path)
            pdf_hash = _hash_content(pdf_bytes)
            if _should_process_document(
                db,
                use_http_rag=use_http_rag,
                force=force,
                exam_id=exam.id,
                content_hash=pdf_hash,
            ):
                text_per_page = _extract_text_from_pdf(pdf_bytes)
                rubric_questions = (exam.rubric_json or {}).get("questions", [])
                chunks = chunk_correction_pdf(text_per_page, rubric_questions)
                if use_http_rag:
                    chunks_count = _ingest_chunks_with_provider(
                        chunks,
                        exam_id=exam.id,
                        kind="correction",
                        source_path=exam.correction_pdf_path,
                        content_hash=pdf_hash,
                        title=f"Corrigé - {exam.title}",
                        force=force,
                    )
                    total_chunks += chunks_count
                    _upsert_external_document_record(
                        db,
                        exam_id=exam.id,
                        kind="correction",
                        source_path=exam.correction_pdf_path,
                        content_hash=pdf_hash,
                        title=f"Corrigé - {exam.title}",
                        chunks_count=chunks_count,
                        force=force,
                    )
                else:
                    total_chunks += _persist_chunks(
                        db,
                        chunks,
                        exam_id=exam.id,
                        kind="correction",
                        source_path=exam.correction_pdf_path,
                        content_hash=pdf_hash,
                        title=f"Corrigé - {exam.title}",
                        force=force,
                    )

        # 3. Embed rubric PDF if available (as generic)
        if exam.rubric_pdf_path:
            pdf_bytes = storage.read(exam.rubric_pdf_path)
            pdf_hash = _hash_content(pdf_bytes)
            if _should_process_document(
                db,
                use_http_rag=use_http_rag,
                force=force,
                exam_id=exam.id,
                content_hash=pdf_hash,
            ):
                text_per_page = _extract_text_from_pdf(pdf_bytes)
                full_text = "\n\n".join(text_per_page)
                chunks = chunk_generic_pdf(full_text)
                if use_http_rag:
                    chunks_count = _ingest_chunks_with_provider(
                        chunks,
                        exam_id=exam.id,
                        kind="rubric",
                        source_path=exam.rubric_pdf_path,
                        content_hash=pdf_hash,
                        title=f"Barème PDF - {exam.title}",
                        force=force,
                    )
                    total_chunks += chunks_count
                    _upsert_external_document_record(
                        db,
                        exam_id=exam.id,
                        kind="rubric",
                        source_path=exam.rubric_pdf_path,
                        content_hash=pdf_hash,
                        title=f"Barème PDF - {exam.title}",
                        chunks_count=chunks_count,
                        force=force,
                    )
                else:
                    total_chunks += _persist_chunks(
                        db,
                        chunks,
                        exam_id=exam.id,
                        kind="rubric",
                        source_path=exam.rubric_pdf_path,
                        content_hash=pdf_hash,
                        title=f"Barème PDF - {exam.title}",
                        force=force,
                    )

        db.commit()

        # Count actual total chunks in DB (not just this run) to avoid
        # resetting to 0 on idempotent re-runs where documents are skipped.
        actual_total = _count_exam_chunks(db, exam.id) if not use_http_rag else total_chunks
        if actual_total == 0 and total_chunks > 0:
            actual_total = total_chunks
        _set_exam_embedding_metadata(db, exam, status="embedded", chunks_count=actual_total)

        logger.info("Embedded exam %s: %d chunks total", exam_id, actual_total)
        return {"status": "completed", "chunks_count": actual_total, "exam_id": exam_id}

    except Exception as exc:
        db.rollback()
        if "exam" in locals() and exam is not None:
            # Only mark as "failed" when all retries are exhausted;
            # otherwise the UI would show a failure while a retry is pending.
            if self.request.retries >= self.max_retries:
                try:
                    _set_exam_embedding_metadata(db, exam, status="failed")
                except Exception:
                    logger.warning("Could not set failed status for exam %s", exam_id)
        logger.exception("Error embedding exam %s: %s", exam_id, exc)
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


def _hash_content(content: bytes) -> str:
    """SHA-256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def _hash_json(value: Any) -> str:
    """SHA-256 hash of canonical JSON content."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hash_content(payload.encode("utf-8"))


def _set_exam_embedding_metadata(
    db: Session,
    exam: Exam,
    *,
    status: str,
    chunks_count: int | None = None,
) -> None:
    metadata = dict(exam.metadata_json or {})
    metadata["embedding_status"] = status
    if chunks_count is not None:
        metadata["embedded_chunks_count"] = chunks_count
    if status == "embedded":
        metadata["embedded_at"] = datetime.now(UTC).isoformat()
    exam.metadata_json = metadata
    db.add(exam)
    db.commit()


def _count_exam_chunks(db: Session, exam_id: uuid.UUID) -> int:
    """Count total knowledge chunks stored in DB for this exam."""
    from sqlalchemy import func

    result = (
        db.query(func.count(KnowledgeChunk.id))
        .join(KnowledgeDocument)
        .filter(KnowledgeDocument.exam_id == exam_id)
        .scalar()
    )
    return result or 0


def _doc_exists(db: Session, *, exam_id: uuid.UUID, content_hash: str) -> bool:
    """Check if this exam already has a document with this hash."""
    return (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.exam_id == exam_id,
            KnowledgeDocument.content_hash == content_hash,
        )
        .first()
        is not None
    )


def _should_process_document(
    db: Session,
    *,
    use_http_rag: bool,
    force: bool,
    exam_id: uuid.UUID,
    content_hash: str,
) -> bool:
    """Decide whether a document should be embedded for the active provider."""
    if use_http_rag:
        return True
    return force or not _doc_exists(db, exam_id=exam_id, content_hash=content_hash)


def _persist_chunks(
    db: Session,
    chunks: list[Chunk],
    *,
    exam_id: uuid.UUID,
    kind: str,
    source_path: str,
    content_hash: str,
    title: str,
    force: bool = False,
) -> int:
    """Persist a document and its chunks with embeddings. Returns chunk count."""
    if not chunks:
        return 0

    existing = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.exam_id == exam_id,
            KnowledgeDocument.content_hash == content_hash,
        )
        .first()
    )
    if existing and force:
        db.delete(existing)
        db.flush()
    elif existing:
        return 0

    # Create document
    doc = KnowledgeDocument(
        exam_id=exam_id,
        kind=kind,
        source_path=source_path,
        content_hash=content_hash,
        title=title,
    )
    db.add(doc)
    db.flush()

    # Embed all chunk texts in batch
    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    for chunk, embedding in zip(chunks, embeddings, strict=False):
        db.add(
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                latex=chunk.latex,
                question_id=chunk.question_id,
                tokens=chunk.tokens,
                metadata_={},
                embedding=embedding,
            )
        )

    db.flush()
    return len(chunks)


def _upsert_external_document_record(
    db: Session,
    *,
    exam_id: uuid.UUID,
    kind: str,
    source_path: str,
    content_hash: str,
    title: str,
    chunks_count: int,
    force: bool = False,
) -> None:
    existing = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.exam_id == exam_id,
            KnowledgeDocument.content_hash == content_hash,
        )
        .first()
    )
    metadata = {"provider": "http", "chunks_count": chunks_count}
    if existing:
        if force:
            existing.source_path = source_path
            existing.title = title
            existing.metadata_ = metadata
        return

    db.add(
        KnowledgeDocument(
            exam_id=exam_id,
            kind=kind,
            source_path=source_path,
            content_hash=content_hash,
            title=title,
            metadata_=metadata,
        )
    )


def _ingest_chunks_with_provider(
    chunks: list[Chunk],
    *,
    exam_id: uuid.UUID,
    kind: str,
    source_path: str,
    content_hash: str,
    title: str,
    force: bool = False,
) -> int:
    """Ingest chunks into the configured external RAG provider."""
    if not chunks:
        return 0

    provider = get_rag_provider()
    total = 0
    for chunk in chunks:
        chunk_hash = f"{content_hash}:{chunk.chunk_index}"
        chunk_source = f"{source_path}#content-{content_hash}-chunk-{chunk.chunk_index}"
        response = provider.ingest_document(
            exam_id=str(exam_id),
            kind=kind,
            source_path=chunk_source,
            content_hash=chunk_hash,
            title=f"{title} — chunk {chunk.chunk_index}",
            chunks_or_text=chunk.text,
            metadata={
                "original_source_path": source_path,
                "question_id": chunk.question_id,
                "chunk_index": chunk.chunk_index,
                "tokens": chunk.tokens,
                "latex": chunk.latex,
            },
            force=force,
        )
        total += _provider_chunks_count(response)
    return total


def _provider_chunks_count(response: dict[str, Any]) -> int:
    if response.get("status") == "skipped":
        return 0
    value = response.get("chunks_count", response.get("count"))
    if isinstance(value, int):
        return value
    if isinstance(response.get("chunks"), list):
        return len(response["chunks"])
    return 1


def _extract_text_from_pdf(pdf_bytes: bytes) -> list[str]:
    """Extract text per page from a PDF using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return pages
