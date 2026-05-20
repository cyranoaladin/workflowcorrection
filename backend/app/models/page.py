from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class CopyPage(Base):
    __tablename__ = "copy_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_copies.id", ondelete="CASCADE"))

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_image_path: Mapped[str] = mapped_column(Text, nullable=False)
    processed_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    copy: Mapped[StudentCopy] = relationship(back_populates="pages")


from app.models.copy import StudentCopy  # noqa: E402
