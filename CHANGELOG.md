# Changelog

## v1.0.0 — 2026-05-20

Phase 1 RAG go-live ready.

### Added

- **Pipeline complet OCR -> Grading -> Audit -> Rapport**
  - OCR multi-source : Azure Document Intelligence, Mathpix, OpenAI Vision, fusion
  - Notation IA par question avec bareme structure JSON
  - Audit LLM-as-judge (rule-based + GPT) avec recommandation tri-state
  - Rapport JSON avec flags, confidence, needs_human_review
  - Validation humaine et export bilan CSV

- **RAG (Retrieval-Augmented Generation)**
  - HttpRagProvider (production) vers ingestor local port 8001
  - PgvectorRagProvider (fallback CI/dev)
  - Auto-embed quand corrige PDF + bareme JSON uploades
  - Chunking intelligent : par question, LaTeX-aware, overlap tokenise
  - Endpoints : embed, embed/status, knowledge listing

- **UI complete Next.js 16**
  - Dashboard examens avec progress pills
  - Page detail examen : upload, bareme JSON, RAG status panel
  - Page copie : OCR page par page, grading, rapport avec audit flags
  - Bilan classe avec export CSV
  - Import CSV etudiants
  - Polling intelligent du status RAG

- **Infrastructure**
  - Healthchecks cross-services : database, redis, storage, rag
  - Stack RAG colocalise via reseau Docker compose_rag_ui_net (port 8001)
  - 26 fichiers de tests (unit + integration + E2E)
  - CI/CD GitHub Actions (lint Ruff + tests pytest)
  - Scripts deploy, backup, smoke-test

- **Documentation**
  - Guide enseignant (USER_GUIDE.md)
  - Runbook ops (OPERATIONS.md)
  - Architecture RAG, securite, rollback, contribution, roadmap

### Fixed

- Embedding ne se re-queue plus sur upload de fichiers non-RAG (sujet_pdf)
- Broker failure ne laisse plus le status "queued" orphelin
- embedded_chunks_count reflette le total reel en DB, pas le run courant
- Status "failed" uniquement quand tous les retries Celery sont epuises
- Bouton reindex desactive pendant status "queued"
- Ruff B904 : exception chaining dans knowledge.py

### Security

- ADMIN_API_TOKEN requis sur tous les endpoints metier
- Bearer token injecte par Caddy, jamais expose au navigateur
- .env chmod 600, secrets redactes dans les logs
- OCR_ENABLE_PAID_CALLS=false par defaut

## Pre-release

### Added

- Phase 1 RAG foundations with HTTP provider and pgvector fallback
- RagProvider protocol, HttpRagProvider, PgvectorRagProvider, factory
- RAG contract and architecture documentation
- Rollback and contribution governance documentation

### Fixed

- Registered embed_exam in Celery worker process
- Scoped knowledge deduplication by exam
- Replaced text vector serialization with pgvector SQLAlchemy type
- Added scoped uniqueness constraints and chunk index uniqueness
- Embedding dimension validation
