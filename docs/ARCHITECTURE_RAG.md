# RAG Architecture

Phase 1 uses a provider interface so production and local development can use different retrieval backends.

## Providers

- `RAG_PROVIDER=http`: production default. The backend calls `rag-api.nexusreussite.academy`; the RAG service handles embeddings and Chroma retrieval.
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

## Grading Flow

`grade_question()` retrieves expert context before calling the LLM when `exam_id` is provided. Retrieved chunks are injected into the grading prompt as correction/rubric context.

## Operational Choice

Keeping both providers avoids making CI dependent on the external service and keeps a local emergency fallback if the HTTP RAG stack is unavailable.
