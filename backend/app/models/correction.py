from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Correction(TimestampMixin, Base):
    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_copies.id", ondelete="CASCADE"))

    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    points_max: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    points_awarded: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    correction_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validated_by_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    copy: Mapped[StudentCopy] = relationship(back_populates="corrections")


from app.models.copy import StudentCopy  # noqa: E402
