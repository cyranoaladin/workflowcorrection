"""add pgvector extension and knowledge tables

Revision ID: 0003_pgvector_knowledge
Revises: 0002_transcriptions_ocr_fields
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0003_pgvector_knowledge"
down_revision = "0002_transcriptions_ocr_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # knowledge_documents
    op.create_table(
        "knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exam_id",
            UUID(as_uuid=True),
            sa.ForeignKey("exams.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('correction', 'rubric', 'syllabus', 'user_doc')",
            name="ck_knowledge_documents_kind",
        ),
    )

    # knowledge_chunks — use raw SQL for the vector column since SA doesn't have native vector type
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("latex", sa.Text(), nullable=True),
        sa.Column("question_id", sa.Text(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Add the vector column via raw SQL (dimension configured at runtime, default 1536)
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding vector(1536) NOT NULL")

    # Indexes
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_question_id", "knowledge_chunks", ["question_id"])
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_index("ix_knowledge_chunks_question_id")
    op.drop_index("ix_knowledge_chunks_document_id")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
