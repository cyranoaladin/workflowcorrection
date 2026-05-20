from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Exam(TimestampMixin, Base):
    __tablename__ = "exams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str | None] = mapped_column(Text, nullable=True)
    session: Mapped[str | None] = mapped_column(Text, nullable=True)

    subject_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    total_points: Mapped[Decimal] = mapped_column(Numeric, nullable=False, server_default="20")

    copies: Mapped[list[StudentCopy]] = relationship(back_populates="exam", cascade="all, delete-orphan")

    @property
    def embedding_status(self) -> str:
        return (self.metadata_json or {}).get("embedding_status") or "idle"

    @property
    def embedded_chunks_count(self) -> int | None:
        value = (self.metadata_json or {}).get("embedded_chunks_count")
        return int(value) if value is not None else None

    @property
    def embedded_at(self) -> datetime | None:
        value = (self.metadata_json or {}).get("embedded_at")
        return datetime.fromisoformat(value) if value else None


from app.models.copy import StudentCopy  # noqa: E402  (circular for typing)
