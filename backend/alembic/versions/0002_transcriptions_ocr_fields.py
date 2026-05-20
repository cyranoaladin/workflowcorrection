"""add ocr fields to transcriptions

Revision ID: 0002_transcriptions_ocr_fields
Revises: 0001_init
Create Date: 2026-05-07

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_transcriptions_ocr_fields"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transcriptions") as batch_op:
        batch_op.add_column(sa.Column("input_image_type", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("raw_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("raw_latex", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transcriptions") as batch_op:
        batch_op.drop_column("error_message")
        batch_op.drop_column("raw_latex")
        batch_op.drop_column("raw_text")
        batch_op.drop_column("input_image_type")
