"""Celery tasks for embedding exam documents into the knowledge base."""

from __future__ import annotations

import hashlib
import uuid

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

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
        total_chunks = 0

        # 1. Embed rubric JSON if available
        if exam.rubric_json:
            rubric_hash = _hash_content(str(exam.rubric_json).encode())
            if force or not _doc_exists(db, exam_id=exam.id, content_hash=rubric_hash):
                chunks = chunk_rubric_json(exam.rubric_json)
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
            if force or not _doc_exists(db, exam_id=exam.id, content_hash=pdf_hash):
                text_per_page = _extract_text_from_pdf(pdf_bytes)
                rubric_questions = (exam.rubric_json or {}).get("questions", [])
                chunks = chunk_correction_pdf(text_per_page, rubric_questions)
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
            if force or not _doc_exists(db, exam_id=exam.id, content_hash=pdf_hash):
                text_per_page = _extract_text_from_pdf(pdf_bytes)
                full_text = "\n\n".join(text_per_page)
                chunks = chunk_generic_pdf(full_text)
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

        logger.info("Embedded exam %s: %d chunks total", exam_id, total_chunks)
        return {"status": "completed", "chunks_count": total_chunks}

    except Exception as exc:
        db.rollback()
        logger.exception("Error embedding exam %s: %s", exam_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


def _hash_content(content: bytes) -> str:
    """SHA-256 hash of content."""
    return hashlib.sha256(content).hexdigest()


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


def _extract_text_from_pdf(pdf_bytes: bytes) -> list[str]:
    """Extract text per page from a PDF using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return pages
