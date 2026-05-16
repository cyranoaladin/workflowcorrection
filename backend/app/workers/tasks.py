from __future__ import annotations

import uuid
import shutil
from pathlib import Path
from uuid import UUID

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.storage import get_storage
from app.models.copy import CopyStatus, StudentCopy
from app.models.page import CopyPage
from app.services.image_preprocess_service import preprocess_image
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
