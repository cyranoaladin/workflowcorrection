"""scope knowledge uniqueness constraints

Revision ID: 0005_knowledge_uq
Revises: 0004_numeric_precision
Create Date: 2026-05-19

"""

from __future__ import annotations

from alembic import op

revision = "0005_knowledge_uq"
down_revision = "0004_numeric_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_content_hash_key")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_documents_exam_hash
        ON knowledge_documents (exam_id, content_hash)
        WHERE exam_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_documents_owner_hash_path
        ON knowledge_documents (owner_id, content_hash, source_path)
        WHERE exam_id IS NULL
    """)
    op.create_unique_constraint(
        "uq_knowledge_chunks_doc_chunk",
        "knowledge_chunks",
        ["document_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_knowledge_chunks_doc_chunk", "knowledge_chunks", type_="unique")
    op.execute("DROP INDEX IF EXISTS uq_knowledge_documents_owner_hash_path")
    op.execute("DROP INDEX IF EXISTS uq_knowledge_documents_exam_hash")
