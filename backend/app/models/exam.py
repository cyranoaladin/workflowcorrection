from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

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

    total_points: Mapped[Decimal] = mapped_column(Numeric, nullable=False, server_default="20")

    copies: Mapped[list["StudentCopy"]] = relationship(back_populates="exam", cascade="all, delete-orphan")


from app.models.copy import StudentCopy  # noqa: E402  (circular for typing)
