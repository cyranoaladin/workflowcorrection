from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CopyStatus(str, Enum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    processed_pages = "processed_pages"
    ocr_pending = "ocr_pending"
    corrected = "corrected"
    failed = "failed"


class StudentCopy(TimestampMixin, Base):
    __tablename__ = "student_copies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"))

    student_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    copy_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    original_pdf_path: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, default=CopyStatus.uploaded.value)
    processing_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    exam: Mapped[Exam] = relationship(back_populates="copies")
    pages: Mapped[list[CopyPage]] = relationship(back_populates="copy", cascade="all, delete-orphan")
    transcriptions: Mapped[list[Transcription]] = relationship(back_populates="copy", cascade="all, delete-orphan")
    corrections: Mapped[list[Correction]] = relationship(back_populates="copy", cascade="all, delete-orphan")


from app.models.correction import Correction  # noqa: E402
from app.models.exam import Exam  # noqa: E402
from app.models.page import CopyPage  # noqa: E402
from app.models.transcription import Transcription  # noqa: E402
