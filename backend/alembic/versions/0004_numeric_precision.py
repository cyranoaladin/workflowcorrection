"""set numeric precision for scores

Revision ID: 0004_numeric_precision
Revises: 0003_pgvector
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_numeric_precision"
down_revision = "0003_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("student_copies", "total_score", type_=sa.Numeric(8, 3), existing_nullable=True)
    op.alter_column("student_copies", "confidence", type_=sa.Numeric(8, 3), existing_nullable=True)
    op.alter_column("corrections", "points_max", type_=sa.Numeric(8, 3), existing_nullable=False)
    op.alter_column("corrections", "points_awarded", type_=sa.Numeric(8, 3), existing_nullable=True)
    op.alter_column("corrections", "confidence", type_=sa.Numeric(8, 3), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("corrections", "confidence", type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("corrections", "points_awarded", type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("corrections", "points_max", type_=sa.Numeric(), existing_nullable=False)
    op.alter_column("student_copies", "confidence", type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("student_copies", "total_score", type_=sa.Numeric(), existing_nullable=True)
