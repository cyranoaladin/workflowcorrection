# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added

- Add Phase 1 RAG foundations with pgvector migrations, knowledge document/chunk models, chunking, embedding and retrieval services.
- Add explicit exam embedding endpoint and knowledge listing endpoint.
- Add embedding configuration for OpenAI and TEI providers.

### Changed

- Use `pgvector/pgvector:pg16` for PostgreSQL services in Compose and CI.
- Set score-related numeric columns to `NUMERIC(8, 3)`.
