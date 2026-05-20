from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CorrectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    copy_id: UUID
    question_id: str
    points_max: Decimal
    points_awarded: Decimal | None
    correction_json: dict[str, Any]
    confidence: Decimal | None
    needs_human_review: bool
    validated_by_human: bool
    created_at: datetime
    updated_at: datetime
