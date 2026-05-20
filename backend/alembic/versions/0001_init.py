"""init tables

Revision ID: 0001_init
Revises:
Create Date: 2026-05-06

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("session", sa.Text(), nullable=True),
        sa.Column("subject_pdf_path", sa.Text(), nullable=True),
        sa.Column("correction_pdf_path", sa.Text(), nullable=True),
        sa.Column("rubric_pdf_path", sa.Text(), nullable=True),
        sa.Column("rubric_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_points", sa.Numeric(), nullable=False, server_default=sa.text("20")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "student_copies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "exam_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_name", sa.Text(), nullable=True),
        sa.Column("copy_code", sa.Text(), nullable=True),
        sa.Column("original_pdf_path", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'uploaded'")),
        sa.Column("processing_task_id", sa.Text(), nullable=True),
        sa.Column("total_score", sa.Numeric(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_student_copies_exam_id", "student_copies", ["exam_id"])

    op.create_table(
        "copy_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "copy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_copies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("original_image_path", sa.Text(), nullable=False),
        sa.Column("processed_image_path", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_copy_pages_copy_id", "copy_pages", ["copy_id"])
    op.create_index(
        "uq_copy_pages_copy_id_page_number",
        "copy_pages",
        ["copy_id", "page_number"],
        unique=True,
    )

    op.create_table(
        "transcriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "copy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_copies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copy_pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("question_id", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column("final_latex", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column(
            "needs_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_transcriptions_copy_id", "transcriptions", ["copy_id"])
    op.create_index("ix_transcriptions_page_id", "transcriptions", ["page_id"])

    op.create_table(
        "corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "copy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_copies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.Text(), nullable=False),
        sa.Column("points_max", sa.Numeric(), nullable=False),
        sa.Column("points_awarded", sa.Numeric(), nullable=True),
        sa.Column(
            "correction_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column(
            "needs_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "validated_by_human",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_corrections_copy_id", "corrections", ["copy_id"])
    op.create_index(
        "uq_corrections_copy_id_question_id",
        "corrections",
        ["copy_id", "question_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_corrections_copy_id_question_id", table_name="corrections")
    op.drop_index("ix_corrections_copy_id", table_name="corrections")
    op.drop_table("corrections")

    op.drop_index("ix_transcriptions_page_id", table_name="transcriptions")
    op.drop_index("ix_transcriptions_copy_id", table_name="transcriptions")
    op.drop_table("transcriptions")

    op.drop_index("uq_copy_pages_copy_id_page_number", table_name="copy_pages")
    op.drop_index("ix_copy_pages_copy_id", table_name="copy_pages")
    op.drop_table("copy_pages")

    op.drop_index("ix_student_copies_exam_id", table_name="student_copies")
    op.drop_table("student_copies")

    op.drop_table("exams")
