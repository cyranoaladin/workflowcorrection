"""fix numeric precision for scores and points

Revision ID: 0004_numeric_precision
Revises: 0003_pgvector_knowledge
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_numeric_precision"
down_revision = "0003_pgvector_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # exams.total_points
    op.alter_column("exams", "total_points", type_=sa.Numeric(8, 3), existing_nullable=False)

    # corrections
    op.alter_column("corrections", "points_max", type_=sa.Numeric(8, 3), existing_nullable=False)
    op.alter_column("corrections", "points_awarded", type_=sa.Numeric(8, 3), existing_nullable=True)
    op.alter_column("corrections", "confidence", type_=sa.Numeric(8, 3), existing_nullable=True)

    # student_copies.total_score
    op.alter_column("student_copies", "total_score", type_=sa.Numeric(8, 3), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("student_copies", "total_score", type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("corrections", "confidence", type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("corrections", "points_awarded", type_=sa.Numeric(), existing_nullable=True)
    op.alter_column("corrections", "points_max", type_=sa.Numeric(), existing_nullable=False)
    op.alter_column("exams", "total_points", type_=sa.Numeric(), existing_nullable=False)
