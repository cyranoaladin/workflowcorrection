# HTTP RAG Provider Contract

This project uses the colocated RAG ingestor as the production RAG provider.

Production on the Hetzner host:

```env
RAG_HTTP_BASE_URL=http://compose-ingestor-1:8001
```

Remote development fallback:

```env
RAG_HTTP_BASE_URL=https://rag-api.nexusreussite.academy
```

The API contract is identical for the internal Docker URL and the public fallback. The internal URL avoids Caddy/Nginx/TLS hops and keeps backend-to-RAG latency on the Docker bridge.

## Authentication

All protected calls use:

```http
Authorization: Bearer <RAG_HTTP_API_TOKEN>
```

Observed behavior on 2026-05-19:

- `GET /collections` without token: `401`
- `GET /collections` with invalid token: `401`
- `GET /collections` with valid token: `200`

The token is stored only in server environment files and must never be committed.

## Health

`GET /health`

Observed response:

```json
{"status":"healthy"}
```

`GET /admin/health`

Observed response:

```json
{"status":"ok"}
```

## Collections

`GET /collections`

Observed response:

```json
{"collections":[{"name":"rag_francais_premiere","count":0}],"total":1}
```

For the correction platform, use one collection:

```text
rag_math_correction
```

Metadata partitions documents by exam and kind.

## Retrieval

Preferred endpoint:

`POST /rag/query`

Request:

```json
{
  "query": "question or grading query",
  "collection": "rag_math_correction",
  "top_k": 5,
  "filters": {
    "metadata": {
      "exam_id": "<uuid>",
      "question_id": "Q1",
      "kind": "correction"
    }
  }
}
```

Observed empty response:

```json
{
  "query": "test correction maths",
  "collection": "rag_francais_premiere",
  "k": 3,
  "filters": {},
  "hits": []
}
```

Hit shape:

```json
{
  "id": "chunk-id",
  "document": "chunk text",
  "metadata": {
    "document_id": "doc-id",
    "chunk_index": 0,
    "exam_id": "<uuid>",
    "kind": "correction",
    "question_id": "Q1",
    "source_path": "/storage/exams/.../correction.pdf"
  },
  "score": 0.12
}
```

`score` is the Chroma distance returned by the service.

## Ingestion

Text ingestion:

`POST /ingest`

```json
{
  "source_type": "markdown",
  "source": "chunked correction or rubric text",
  "hints": {
    "collection": "rag_math_correction",
    "exam_id": "<uuid>",
    "kind": "rubric",
    "question_id": "Q1",
    "source_path": "rubric_json"
  }
}
```

File ingestion:

`POST /ingest/upload-files?metadata=<json>&mode=text`

The endpoint accepts multipart `files`.

Deduplication check:

`POST /ingest/check-duplicates`

```json
{"sources":["/storage/exams/.../correction.pdf"],"collection":"rag_math_correction"}
```

Observed response:

```json
{"sources_checked":1,"results":[{"source":"codex-inventory-nonexistent-source","already_ingested":false}]}
```

## Server Embeddings

The external RAG service embeds server-side. The correction backend sends raw text only.

Observed environment:

- `EMBED_MODEL=nomic-embed-text`
- `OLLAMA_URL=http://ollama:11434`
- Chroma space: cosine

`EMBEDDING_DIMENSION` in this repo only applies to `RAG_PROVIDER=pgvector`.

## Limits

Observed server config:

- `CHROMA_REQUEST_TIMEOUT=30`
- `OLLAMA_REQUEST_TIMEOUT=120`
- `MAX_REMOTE_BYTES=10 MiB` default for remote fetch
- `INGEST_CHUNK_SIZE=1000`
- `INGEST_CHUNK_OVERLAP=150`
- `GDRIVE_MAX_DOCS=200`

No explicit rate-limit headers were observed.

## Known Limitation

`GET /admin/documents` returned `HTTP 500 Internal Server Error` during inventory on 2026-05-19.
This is not blocking for Phase 1 because the correction backend does not require that endpoint.
