from __future__ import annotations

import httpx
import pytest

from app.services.rag.http_provider import HttpRagProvider, RagAuthError


def test_http_rag_provider_retrieve_maps_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rag/query"
        assert request.headers["Authorization"] == "Bearer test-token"
        payload = httpx.Request("POST", request.url, content=request.content).read()
        assert b'"query":"derivee"' in payload
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "id": "chunk-1",
                        "document": "corrige Q1",
                        "metadata": {
                            "document_id": "doc-1",
                            "chunk_index": 2,
                            "kind": "correction",
                            "question_id": "Q1",
                            "tokens": 10,
                        },
                        "score": 0.12,
                    }
                ]
            },
        )

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )

    chunks = provider.retrieve(
        exam_id="exam-1",
        question_id="Q1",
        query="derivee",
        top_k=3,
        kinds=["correction"],
    )

    assert len(chunks) == 1
    assert chunks[0].id == "chunk-1"
    assert chunks[0].text == "corrige Q1"
    assert chunks[0].kind == "correction"
    assert chunks[0].question_id == "Q1"


def test_http_rag_provider_retrieve_empty() -> None:
    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"hits": []})),
    )

    assert provider.retrieve(exam_id="exam-1", question_id=None, query="x") == []


def test_http_rag_provider_raises_on_unauthorized() -> None:
    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="bad-token",
        transport=httpx.MockTransport(lambda _: httpx.Response(401, json={"detail": "Unauthorized"})),
    )

    with pytest.raises(RagAuthError):
        provider.retrieve(exam_id="exam-1", question_id=None, query="x")


def test_http_rag_provider_retries_5xx() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(500, text="temporary")
        return httpx.Response(200, json={"hits": []})

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    assert provider.retrieve(exam_id="exam-1", question_id=None, query="x") == []
    assert calls == 3


def test_http_rag_provider_timeout_surfaces_as_runtime_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="rag_http_request_failed"):
        provider.retrieve(exam_id="exam-1", question_id=None, query="x")


def test_ingest_document_uses_upload_files_endpoint() -> None:
    """ingest_document must POST multipart to /ingest/upload-files, not JSON to /ingest."""
    import json
    from urllib.parse import parse_qs, urlparse

    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if "/check-duplicates" in str(request.url):
            return httpx.Response(200, json={"results": [{"already_ingested": False}]})
        if "/upload-files" in str(request.url):
            return httpx.Response(
                200,
                json={"status": "ok", "total_added": 3, "total_skipped": 0, "results": []},
            )
        return httpx.Response(404)

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )

    result = provider.ingest_document(
        exam_id="exam-42",
        kind="correction",
        source_path="exams/42/correction.md",
        content_hash="abc123",
        title="Correction Exam 42",
        chunks_or_text="# Q1\nLa derivee de x^2 est 2x.",
    )

    assert result["status"] == "ok"
    assert result["total_added"] == 3
    # Response normalized: chunks_count mapped from total_added
    assert result["chunks_count"] == 3
    assert result["collection"] == "rag_math_correction"

    # Verify the upload request
    upload_req = [r for r in captured_requests if "/upload-files" in str(r.url)][0]
    assert upload_req.method == "POST"
    assert "multipart/form-data" in upload_req.headers.get("content-type", "")

    # Parse and validate metadata query param
    parsed = urlparse(str(upload_req.url))
    qs = parse_qs(parsed.query)
    assert qs["mode"] == ["text"]
    hints = json.loads(qs["metadata"][0])
    assert hints["collection"] == "rag_math_correction"
    assert hints["title"] == "Correction Exam 42"
    assert hints["exam_id"] == "exam-42"
    assert hints["kind"] == "correction"
    assert hints["content_hash"] == "abc123"


def test_ingest_document_no_double_md_extension() -> None:
    """source_path ending in .md should not produce filename.md.md."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if "/check-duplicates" in str(request.url):
            return httpx.Response(200, json={"results": [{"already_ingested": False}]})
        if "/upload-files" in str(request.url):
            return httpx.Response(200, json={"status": "ok", "total_added": 1, "total_skipped": 0, "results": []})
        return httpx.Response(404)

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )

    provider.ingest_document(
        exam_id="e1",
        kind="rubric",
        source_path="exams/1/rubric.md",
        content_hash="h1",
        title=None,
        chunks_or_text="content",
    )

    upload_req = [r for r in captured_requests if "/upload-files" in str(r.url)][0]
    # Extract filename from multipart body — it should end with .md, not .md.md
    body = upload_req.content.decode("utf-8", errors="replace")
    assert "exams_1_rubric.md" in body
    assert "exams_1_rubric.md.md" not in body
