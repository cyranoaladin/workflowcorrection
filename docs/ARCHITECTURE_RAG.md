# RAG Architecture

Phase 1 uses a provider interface so production and local development can use different retrieval backends.

## Providers

- `RAG_PROVIDER=http`: production default. On the Hetzner host the backend calls `http://compose-ingestor-1:8001` over Docker internal networking; the RAG service handles embeddings and Chroma retrieval.
- `RAG_PROVIDER=pgvector`: local fallback for development and CI. The backend embeds with OpenAI or TEI, stores vectors in PostgreSQL `pgvector`, and retrieves by cosine distance.

Both providers implement `RagProvider`:

- `health()`
- `retrieve(exam_id, question_id, query, top_k, kinds)`
- `ingest_document(...)`

## Metadata Contract

Every RAG chunk should carry:

```json
{
  "exam_id": "<uuid>",
  "kind": "correction | rubric | syllabus | user_doc",
  "question_id": "Q1",
  "niveau": "terminale",
  "owner_id": null,
  "source_path": "/storage/exams/.../correction.pdf"
}
```

Production uses one collection: `rag_math_correction`.

## Network Topology

The workflowcorrection stack and the RAG stack run on the same Hetzner host but are managed by separate Compose projects:

```text
88.99.254.59
├─ /opt/math-correction
│  ├─ math-correction-backend-1  ─┐
│  ├─ math-correction-worker-1   ─┼─ compose_rag_ui_net ── compose-ingestor-1:8001
│  ├─ math-correction-postgres-1  │                         ├─ compose-chroma-1:8000
│  └─ math-correction-redis-1     │                         └─ compose-ollama-1:11434
└─ /opt/compose                   ┘
```

`docker-compose.labomaths.yml` attaches `backend` and `worker` to the external Docker network `compose_rag_ui_net` as `rag_external`. This keeps production RAG traffic off public TLS/proxy paths while preserving the public `https://rag-api.nexusreussite.academy` endpoint as a remote development fallback.

Production value:

```env
RAG_HTTP_BASE_URL=http://compose-ingestor-1:8001
```

## Grading Flow

`grade_question()` retrieves expert context before calling the LLM when `exam_id` is provided. Retrieved chunks are injected into the grading prompt as correction/rubric context.

## Operational Choice

Keeping both providers avoids making CI dependent on the external service and keeps a local emergency fallback if the HTTP RAG stack is unavailable.
