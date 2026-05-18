"""add pgvector knowledge tables

Revision ID: 0003_pgvector
Revises: 0002_transcriptions_ocr_fields
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_pgvector"
down_revision = "0002_transcriptions_ocr_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "exams",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("kind IN ('correction','rubric','syllabus','user_doc')", name="ck_knowledge_documents_kind"),
    )
    op.create_index("ix_knowledge_documents_exam_id", "knowledge_documents", ["exam_id"])
    op.create_index("uq_knowledge_documents_content_hash", "knowledge_documents", ["content_hash"], unique=True)

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("latex", sa.Text(), nullable=True),
        sa.Column("question_id", sa.Text(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector")
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_question_id", "knowledge_chunks", ["question_id"])
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_index("ix_knowledge_chunks_question_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("uq_knowledge_documents_content_hash", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_exam_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_column("exams", "metadata")
    op.execute("DROP EXTENSION IF EXISTS vector")
