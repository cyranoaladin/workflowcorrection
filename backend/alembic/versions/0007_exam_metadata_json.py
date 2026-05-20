"""add exam metadata json

Revision ID: 0007_exam_metadata
Revises: 0006_uuid_defaults
Create Date: 2026-05-20

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_exam_metadata"
down_revision = "0006_uuid_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("exams", "metadata_json")
