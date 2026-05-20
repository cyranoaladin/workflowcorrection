from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExamCreate(BaseModel):
    title: str
    level: str | None = None
    session: str | None = None


class ExamUpdate(BaseModel):
    title: str | None = None
    level: str | None = None
    session: str | None = None
    total_points: Decimal | None = None


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    level: str | None
    session: str | None

    subject_pdf_path: str | None
    correction_pdf_path: str | None
    rubric_pdf_path: str | None
    rubric_json: dict[str, Any] | None

    total_points: Decimal
    embedding_status: str | None = None
    embedded_chunks_count: int | None = None
    embedded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
