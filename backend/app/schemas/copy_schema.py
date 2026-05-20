from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CopyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    student_name: str | None
    copy_code: str | None
    original_pdf_path: str
    status: str
    processing_task_id: str | None
    total_score: Decimal | None
    confidence: Decimal | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
