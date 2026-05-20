from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.exam import Exam
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.chunking_service import Chunk
from app.workers.embed_tasks import (
    _doc_exists,
    _hash_json,
    _ingest_chunks_with_provider,
    _persist_chunks,
    _should_process_document,
)


@pytest.fixture
def db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_doc_exists_is_scoped_by_exam_id(db_session: Session) -> None:
    content_hash = f"same-hash-{uuid.uuid4()}"
    exam_a = Exam(title=f"exam-a-{uuid.uuid4()}", total_points=10, rubric_json={"questions": []})
    exam_b = Exam(title=f"exam-b-{uuid.uuid4()}", total_points=10, rubric_json={"questions": []})
    db_session.add_all([exam_a, exam_b])
    db_session.flush()

    doc = KnowledgeDocument(
        exam_id=exam_a.id,
        kind="rubric",
        source_path="rubric_json",
        content_hash=content_hash,
        title="A",
    )
    db_session.add(doc)
    db_session.commit()

    assert _doc_exists(db_session, exam_id=exam_a.id, content_hash=content_hash) is True
    assert _doc_exists(db_session, exam_id=exam_b.id, content_hash=content_hash) is False


def test_force_reembed_deletes_only_matching_exam_document(db_session: Session) -> None:
    content_hash = f"same-hash-{uuid.uuid4()}"
    exam_a = Exam(title=f"exam-a-{uuid.uuid4()}", total_points=10, rubric_json={"questions": []})
    exam_b = Exam(title=f"exam-b-{uuid.uuid4()}", total_points=10, rubric_json={"questions": []})
    db_session.add_all([exam_a, exam_b])
    db_session.flush()

    doc_a = KnowledgeDocument(
        exam_id=exam_a.id,
        kind="rubric",
        source_path="rubric_json",
        content_hash=content_hash,
        title="A",
    )
    db_session.add(doc_a)
    db_session.flush()
    db_session.add(
        KnowledgeChunk(
            document_id=doc_a.id,
            chunk_index=0,
            text="existing A",
            embedding=[0.0] * 1536,
        )
    )
    db_session.commit()

    with patch("app.workers.embed_tasks.embed_texts", return_value=[[0.1] * 1536]):
        _persist_chunks(
            db_session,
            [Chunk(chunk_index=0, text="new B", tokens=2)],
            exam_id=exam_b.id,
            kind="rubric",
            source_path="rubric_json",
            content_hash=content_hash,
            title="B",
            force=True,
        )
    db_session.commit()

    docs = db_session.query(KnowledgeDocument).filter(KnowledgeDocument.content_hash == content_hash).all()
    assert {doc.exam_id for doc in docs} == {exam_a.id, exam_b.id}
    assert (
        db_session.query(KnowledgeChunk).join(KnowledgeDocument).filter(KnowledgeDocument.exam_id == exam_a.id).count()
        == 1
    )


def test_hash_json_uses_canonical_serialization() -> None:
    assert _hash_json({"b": 2, "a": 1}) == _hash_json({"a": 1, "b": 2})


def test_http_provider_processing_ignores_local_pgvector_documents(db_session: Session) -> None:
    content_hash = f"same-hash-{uuid.uuid4()}"
    exam = Exam(title=f"exam-{uuid.uuid4()}", total_points=10, rubric_json={"questions": []})
    db_session.add(exam)
    db_session.flush()
    db_session.add(
        KnowledgeDocument(
            exam_id=exam.id,
            kind="rubric",
            source_path="rubric_json",
            content_hash=content_hash,
            title="Local pgvector doc",
        )
    )
    db_session.commit()

    assert (
        _should_process_document(
            db_session,
            use_http_rag=True,
            force=False,
            exam_id=exam.id,
            content_hash=content_hash,
        )
        is True
    )
    assert (
        _should_process_document(
            db_session,
            use_http_rag=False,
            force=False,
            exam_id=exam.id,
            content_hash=content_hash,
        )
        is False
    )


def test_http_ingestion_sends_one_document_per_chunk() -> None:
    provider = MagicMock()
    provider.ingest_document.return_value = {"status": "completed", "chunks_count": 1}

    chunks = [
        Chunk(text="Q1 text", question_id="Q1", chunk_index=0, tokens=3, latex="$x$"),
        Chunk(text="Q2 text", question_id="Q2", chunk_index=1, tokens=4),
    ]

    with patch("app.workers.embed_tasks.get_rag_provider", return_value=provider):
        count = _ingest_chunks_with_provider(
            chunks,
            exam_id=uuid.uuid4(),
            kind="rubric",
            source_path="rubric_json",
            content_hash="hash",
            title="Barème",
        )

    assert count == 2
    assert provider.ingest_document.call_count == 2
    first_call = provider.ingest_document.call_args_list[0].kwargs
    assert first_call["source_path"] == "rubric_json#content-hash-chunk-0"
    assert first_call["content_hash"] == "hash:0"
    assert first_call["metadata"]["original_source_path"] == "rubric_json"
    assert first_call["metadata"]["question_id"] == "Q1"
    assert first_call["metadata"]["chunk_index"] == 0
