# Changelog

## Unreleased

### Added

- Phase 1 RAG foundations with HTTP provider for production and pgvector fallback for local development and CI.
- `RagProvider` protocol, `HttpRagProvider`, `PgvectorRagProvider`, and provider factory.
- RAG contract and architecture documentation.
- Rollback and contribution governance documentation.

### Fixed

- Registered `embed_exam` in the Celery worker process.
- Scoped knowledge deduplication by exam to avoid cross-exam data deletion.
- Replaced text vector serialization with `pgvector` SQLAlchemy type.
- Added scoped uniqueness constraints and chunk index uniqueness.
- Returned eager embed results with `chunks_count`.
- Removed the N+1 query in knowledge listing.
- Added embedding dimension validation.
