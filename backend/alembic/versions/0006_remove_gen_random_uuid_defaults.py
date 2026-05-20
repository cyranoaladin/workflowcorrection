"""remove knowledge server-side uuid defaults

Revision ID: 0006_uuid_defaults
Revises: 0005_knowledge_uq
Create Date: 2026-05-19

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_uuid_defaults"
down_revision = "0005_knowledge_uq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("knowledge_documents", "id", server_default=None)
    op.alter_column("knowledge_chunks", "id", server_default=None)


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.alter_column("knowledge_documents", "id", server_default=sa.text("gen_random_uuid()"))
    op.alter_column("knowledge_chunks", "id", server_default=sa.text("gen_random_uuid()"))
