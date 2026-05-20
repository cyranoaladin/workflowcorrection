from __future__ import annotations

from pathlib import Path


def _migration(name: str) -> str:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / name
    return path.read_text(encoding="utf-8")


def test_pgvector_migration_downgrade_keeps_shared_extension() -> None:
    content = _migration("0003_pgvector_knowledge.py")
    downgrade = content.split("def downgrade() -> None:", maxsplit=1)[1]

    assert "DROP EXTENSION" not in downgrade


def test_knowledge_unique_constraints_downgrade_does_not_restore_global_hash_unique() -> None:
    content = _migration("0005_knowledge_unique_constraints.py")
    downgrade = content.split("def downgrade() -> None:", maxsplit=1)[1]

    assert "knowledge_documents_content_hash_key" not in downgrade
    assert "content_hash" not in downgrade
