from __future__ import annotations

import uuid
import shutil
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.storage import get_storage
from app.models.copy import CopyStatus, StudentCopy
from app.models.correction import Correction
from app.models.exam import Exam
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.page import CopyPage
from app.models.transcription import Transcription
from app.services.audit_service import audit_correction
from app.services.chunking_service import Chunk, chunk_correction_pdf, chunk_generic_pdf, chunk_rubric_json
from app.services.embedding_service import embed_texts
from app.services.grading_service import grade_question
from app.services.image_preprocess_service import preprocess_image
from app.services.rag_service import _vector_literal
from app.workers.celery_app import celery

logger = get_task_logger(__name__)


def enforce_pdf_page_limit(*, page_count: int, max_pages: int) -> None:
    if page_count > max_pages:
        raise ValueError(f"too_many_pages: PDF has {page_count} pages, limit is {max_pages}")


def _load_pdf_module():
    try:
        import pymupdf as fitz  # type: ignore

        return fitz
    except Exception:  # pragma: no cover
        import fitz  # type: ignore

        return fitz


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_pdf_text_per_page(pdf_path: Path) -> list[str]:
    fitz = _load_pdf_module()
    doc = fitz.open(str(pdf_path))
    try:
        return [doc.load_page(i).get_text("text") for i in range(doc.page_count)]
    finally:
        doc.close()


def _persist_knowledge_document(
    *,
    db: Session,
    exam_id: UUID | None,
    kind: str,
    source_path: str,
    content_hash: str,
    title: str | None,
    chunks: list[Chunk],
    force: bool,
) -> tuple[str, int]:
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.content_hash == content_hash).first()
    if existing and not force:
        return "skipped", len(existing.chunks)
    if existing and force:
        db.delete(existing)
        db.flush()

    if not chunks:
        return "empty", 0

    embeddings = embed_texts([chunk.text for chunk in chunks])
    settings = get_settings()
    for embedding in embeddings:
        if len(embedding) != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"embedding_dimension_mismatch: got {len(embedding)}, expected {settings.EMBEDDING_DIMENSION}"
            )

    document = KnowledgeDocument(
        exam_id=exam_id,
        kind=kind,
        source_path=source_path,
        content_hash=content_hash,
        title=title,
        metadata_json={"embedding_model": settings.EMBEDDING_MODEL, "embedding_provider": settings.EMBEDDING_PROVIDER},
    )
    db.add(document)
    db.flush()

    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                text=chunk.text,
                latex=chunk.latex,
                question_id=chunk.question_id,
                embedding=_vector_literal(embedding),
                tokens=chunk.tokens,
                metadata_json=chunk.metadata,
            )
        )
    return "embedded", len(chunks)


@celery.task(bind=True, name="process_copy", track_started=True)
def process_copy(self, copy_id: str, force: bool = False) -> dict:
    db: Session = SessionLocal()
    storage = get_storage()
    settings = get_settings()

    try:
        copy_uuid = UUID(copy_id)
        copy = db.get(StudentCopy, copy_uuid)
        if not copy:
            return {"status": "error", "reason": "copy_not_found"}

        # Normal flow: API sets status=queued, then the worker transitions queued -> processing.
        if copy.status == CopyStatus.processing.value:
            return {"status": "skipped", "reason": "already_processing"}

        existing_pages = db.query(CopyPage).filter(CopyPage.copy_id == copy_uuid).all()
        if existing_pages and not force:
            if copy.status == CopyStatus.processed_pages.value:
                return {
                    "status": "already_processed",
                    "message": "Copy already processed. Use force=true to reprocess.",
                }
            return {
                "status": "pages_exist",
                "message": "Copy has existing pages on disk/DB. Use force=true to reprocess safely.",
                "existing_pages": len(existing_pages),
            }
        if existing_pages and force:
            # Delete derived images for this copy, then purge DB rows.
            for page in existing_pages:
                try:
                    page_dir = storage.resolve(f"pages/{page.id}")
                    shutil.rmtree(page_dir, ignore_errors=True)
                except Exception:
                    logger.warning("Failed to delete page dir for %s", page.id)
            db.query(CopyPage).filter(CopyPage.copy_id == copy_uuid).delete(synchronize_session=False)
            db.commit()

        copy.status = CopyStatus.processing.value
        copy.processing_task_id = self.request.id
        copy.error_message = None
        db.add(copy)
        db.commit()

        pdf_abs = storage.resolve(copy.original_pdf_path)
        if not pdf_abs.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_abs}")

        fitz = _load_pdf_module()
        doc = fitz.open(str(pdf_abs))
        page_count = doc.page_count
        enforce_pdf_page_limit(page_count=page_count, max_pages=int(settings.PDF_MAX_PAGES))
        try:
            for idx in range(page_count):
                page_number = idx + 1

                # Create DB page entry first (so we can use the UUID in paths)
                page_id = uuid.uuid4()
                original_rel = f"pages/{page_id}/original.png"
                processed_rel = f"pages/{page_id}/processed.png"

                page = CopyPage(
                    id=page_id,
                    copy_id=copy_uuid,
                    page_number=page_number,
                    original_image_path=original_rel,
                    processed_image_path=None,
                    width=None,
                    height=None,
                )
                db.add(page)
                db.commit()
                db.refresh(page)

                # Render at 300 DPI
                original_abs = storage.resolve(original_rel)
                original_abs.parent.mkdir(parents=True, exist_ok=True)
                pix = doc.load_page(idx).get_pixmap(dpi=300, alpha=False)
                pix.save(str(original_abs))

                processed_abs = storage.resolve(processed_rel)
                info = preprocess_image(original_abs, processed_abs)

                page.processed_image_path = processed_rel
                page.width = info.get("width")
                page.height = info.get("height")
                db.add(page)
                db.commit()
        finally:
            doc.close()

        copy.status = CopyStatus.processed_pages.value
        db.add(copy)
        db.commit()

        return {"status": "ok", "copy_id": copy_id, "pages": page_count}

    except Exception as e:
        logger.exception("process_copy failed")
        try:
            copy = db.get(StudentCopy, UUID(copy_id))
            if copy:
                copy.status = CopyStatus.failed.value
                copy.error_message = f"{type(e).__name__}: {e}"
                db.add(copy)
                db.commit()
        except Exception:
            pass
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
    finally:
        db.close()


@celery.task(bind=True, name="embed_exam", track_started=True)
def embed_exam(self, exam_id: str, force: bool = False) -> dict:
    """Embed exam correction/rubric knowledge into pgvector-backed chunks."""
    db: Session = SessionLocal()
    storage = get_storage()
    try:
        exam_uuid = UUID(exam_id)
        exam = db.get(Exam, exam_uuid)
        if not exam:
            return {"status": "error", "reason": "exam_not_found"}

        total_chunks = 0
        statuses: list[dict] = []
        rubric_questions = (exam.rubric_json or {}).get("questions", [])

        if exam.correction_pdf_path:
            correction_abs = storage.resolve(exam.correction_pdf_path)
            correction_bytes = correction_abs.read_bytes()
            correction_chunks = chunk_correction_pdf(
                _extract_pdf_text_per_page(correction_abs),
                rubric_questions,
            )
            status, chunks_count = _persist_knowledge_document(
                db=db,
                exam_id=exam_uuid,
                kind="correction",
                source_path=exam.correction_pdf_path,
                content_hash=_sha256_bytes(correction_bytes),
                title="Corrigé",
                chunks=correction_chunks,
                force=force,
            )
            total_chunks += chunks_count if status == "embedded" else 0
            statuses.append({"kind": "correction", "status": status, "chunks_count": chunks_count})

        if exam.rubric_json:
            rubric_bytes = json.dumps(exam.rubric_json, sort_keys=True, ensure_ascii=False).encode("utf-8")
            rubric_source = exam.rubric_pdf_path or f"exams/{exam_id}/rubric.json"
            status, chunks_count = _persist_knowledge_document(
                db=db,
                exam_id=exam_uuid,
                kind="rubric",
                source_path=rubric_source,
                content_hash=_sha256_bytes(rubric_bytes),
                title="Barème JSON",
                chunks=chunk_rubric_json(exam.rubric_json),
                force=force,
            )
            total_chunks += chunks_count if status == "embedded" else 0
            statuses.append({"kind": "rubric", "status": status, "chunks_count": chunks_count})
        elif exam.rubric_pdf_path:
            rubric_abs = storage.resolve(exam.rubric_pdf_path)
            rubric_bytes = rubric_abs.read_bytes()
            rubric_text = "\n\n".join(_extract_pdf_text_per_page(rubric_abs))
            status, chunks_count = _persist_knowledge_document(
                db=db,
                exam_id=exam_uuid,
                kind="rubric",
                source_path=exam.rubric_pdf_path,
                content_hash=_sha256_bytes(rubric_bytes),
                title="Barème PDF",
                chunks=chunk_generic_pdf(rubric_text),
                force=force,
            )
            total_chunks += chunks_count if status == "embedded" else 0
            statuses.append({"kind": "rubric", "status": status, "chunks_count": chunks_count})

        overall_status = "embedded" if any(item["status"] == "embedded" for item in statuses) else "skipped"
        exam.metadata_json = {
            **(exam.metadata_json or {}),
            "embedding_status": overall_status,
            "embedded_at": datetime.now(tz=timezone.utc).isoformat(),
            "chunks_count": sum(item["chunks_count"] for item in statuses),
            "embedding_documents": statuses,
        }
        db.add(exam)
        db.commit()

        return {
            "status": overall_status,
            "exam_id": exam_id,
            "chunks_count": total_chunks,
            "documents": statuses,
        }
    except Exception as e:
        logger.exception("embed_exam failed for exam %s", exam_id)
        db.rollback()
        try:
            exam = db.get(Exam, UUID(exam_id))
            if exam:
                exam.metadata_json = {
                    **(exam.metadata_json or {}),
                    "embedding_status": "failed",
                    "embedding_error": f"{type(e).__name__}: {e}",
                }
                db.add(exam)
                db.commit()
        except Exception:
            pass
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
    finally:
        db.close()


@celery.task(bind=True, name="grade_copy_task", track_started=True)
def grade_copy_task(self, copy_id: str, force: bool = False) -> dict:
    """
    Async Celery task: grade all questions of a copy using LLM + rubric_json.
    Called after OCR is complete.
    """
    db: Session = SessionLocal()
    try:
        copy_uuid = UUID(copy_id)
        copy = db.get(StudentCopy, copy_uuid)
        if not copy:
            return {"status": "error", "reason": "copy_not_found"}

        if copy.status == CopyStatus.corrected.value and not force:
            return {"status": "skipped", "reason": "already_corrected"}

        exam = db.get(Exam, copy.exam_id)
        if not exam or not exam.rubric_json:
            return {"status": "error", "reason": "no_rubric_json"}

        rubric_questions: list[dict] = exam.rubric_json.get("questions", [])
        if not rubric_questions:
            return {"status": "error", "reason": "rubric_has_no_questions"}

        transcriptions = (
            db.query(Transcription)
            .filter(Transcription.copy_id == copy_uuid)
            .order_by(Transcription.created_at.desc())
            .all()
        )
        full_transcription = "\n\n".join(
            t.final_text or t.raw_text or ""
            for t in transcriptions
            if (t.final_text or t.raw_text)
        )
        if not full_transcription.strip():
            return {"status": "error", "reason": "no_transcription"}

        if force:
            db.query(Correction).filter(Correction.copy_id == copy_uuid).delete(synchronize_session=False)
            db.commit()

        grading_results: list[dict] = []
        for q in rubric_questions:
            qid = str(q.get("id", "unknown"))
            self.update_state(state="PROGRESS", meta={"grading_question": qid})
            result = grade_question(qid, q, full_transcription)
            grading_results.append(result)

            if result.get("status") == "ok" and result.get("points_awarded") is not None:
                corr = Correction(
                    copy_id=copy_uuid,
                    question_id=qid,
                    points_max=Decimal(str(result["points_max"])),
                    points_awarded=Decimal(str(result["points_awarded"])),
                    correction_json={
                        "justification": result.get("justification", ""),
                        "criteria_details": result.get("criteria_details", []),
                    },
                    confidence=Decimal(str(result.get("confidence", 0))),
                    needs_human_review=result.get("needs_human_review", True),
                )
                db.add(corr)

        db.commit()

        audit = audit_correction(
            corrections=grading_results,
            total_points=float(exam.total_points),
            rubric_questions=rubric_questions,
        )

        total_awarded = sum(
            float(r["points_awarded"])
            for r in grading_results
            if r.get("status") == "ok" and r.get("points_awarded") is not None
        )

        copy.total_score = Decimal(str(total_awarded))
        copy.confidence = Decimal(str(audit.get("overall_confidence", 0)))
        copy.status = CopyStatus.corrected.value
        db.add(copy)
        db.commit()

        return {
            "status": "ok",
            "copy_id": copy_id,
            "total_awarded": total_awarded,
            "questions_graded": len(grading_results),
            "audit_passed": audit.get("audit_passed"),
        }

    except Exception as e:
        logger.exception("grade_copy_task failed for copy %s", copy_id)
        try:
            copy = db.get(StudentCopy, UUID(copy_id))
            if copy:
                copy.status = CopyStatus.failed.value
                copy.error_message = f"grading: {type(e).__name__}: {e}"
                db.add(copy)
                db.commit()
        except Exception:
            pass
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
    finally:
        db.close()
