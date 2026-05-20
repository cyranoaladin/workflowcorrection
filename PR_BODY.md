## What

Finalisation complète de la Phase 1 RAG :

- Construit sur le travail Windsurf (PR #2 `cc549be`) comme base
- Corrige 12 défauts D.1 à D.20 identifiés par Copilot, cubic-dev-ai et audit Claude (dont 2 P0 bloquants en prod)
- Introduit le sous-package `app.services.rag/` avec `RagProvider` Protocol, `HttpRagProvider` (production via `rag-api.nexusreussite.academy`) et `PgvectorRagProvider` (fallback dev/CI/offline)
- `grade_question` injecte désormais le contexte RAG dans le prompt LLM

## Why

La PR #2 d'origine contenait 2 défauts P0 bloquants en production (D.10 task Celery non enregistrée → `KeyError` worker ; D.11 force re-embed cross-exam détruit des données d'un autre examen). De plus, l'intention utilisateur initiale était d'utiliser le service RAG externe `rag-api.nexusreussite.academy` qui tournait déjà sur la machine, pas un RAG pgvector autonome. Cette PR aligne le code sur l'intention et corrige les défauts.

## How

19 commits atomiques :

- `13008c2` fix(rag): register embed_exam task in celery worker include — D.10
- `1523932` fix(rag): scope knowledge persistence by exam and vector schema — D.1, D.7, D.11, D.12, D.13, D.15
- `3b4d4bb` fix(rag): validate rag and embedding dimensions — D.14
- `0c96091` fix(rag): return embed task result and aggregate chunk counts — D.16, D.17
- `9b85564` feat(rag): implement token-sized overlap in generic chunking — D.20
- `f2912b7` feat(rag): introduce http and pgvector providers — Phase D
- `099fe2a` test(rag): cover pgvector cosine retrieval ordering — D.5
- `ba90d1c` test(rag): fix non-tautological question filter assertion — D.18, D.19
- `483c509` docs(rag): document http provider and enable ruff ci — Phase F
- `51b8c2f` chore(infra): align labomaths compose comments with prod state — Phase G
- `4ee1b9c` fix(rag): keep embedding validation compatible with provider mocks
- `3f8efe1` chore(deps): include ruff for local backend verification
- `bfc8e43` style(backend): apply ruff formatting
- `8caeb09` fix(deploy): apply alembic migrations on every deploy
- `ae08da5` chore(ci): align backend with ruff import checks
- `2a74695` fix(ci): satisfy ruff exception chaining rules
- `4e4d1ca` fix(rag): address review safety issues
- `3d76779` fix(rag): decouple http ingestion from local dedup
- `13437f3` fix(deploy): add pg_dump backup and healthcheck wait before migrations

> **Note pour le reviewer** : le commit `bfc8e43` est uniquement du formatage Ruff sur 70 fichiers existants, aucune modification fonctionnelle. Il peut être ignoré en navigation.

## Test plan

- ✅ 146 tests backend (était 91, +55 nouveaux)
- ✅ Test intégration pgvector réel (insert + cosine top-3 order)
- ✅ Test E2E `grade_question` avec RAG injection vérifiée
- ✅ Test `HttpRagProvider` mocké : 5 scénarios (200 OK, 200 empty, 401, retry 5xx, timeout)
- ✅ Test `embed_exam` task Celery registration
- ✅ Test cross-exam destructive force-reembed prevention
- ✅ Test runtime validation (HTTP token, HTTPS base URL en prod)
- ✅ Migrations 0003 → 0006 testées down/up
- ✅ Ruff check + format check OK (ruff 0.6.9)
- ✅ 3 docker-compose configs valides

## Checklist Phase 1 originale

- [x] Migrations 0003 + 0004 + 0005 + 0006 up + down
- [x] `POST /exams/{id}/embed` retourne `{status, chunks_count}` idempotent
- [x] `GET /exams/{id}/embed/status?task_id=...` pour polling
- [x] `GET /exams/{id}/knowledge` liste docs et statut
- [x] Retrieval testé avec ≥ 10 cas (16 tests RAG totaux)
- [x] Aucun embedding à l'upload
- [x] README RAG mis à jour
- [x] CI verte attendue (backend + frontend + Ruff + GitGuardian)

## Vérifications pré-déploiement

### V.1 — Alembic migrations au déploiement
✅ `deploy_server.sh` step 7/10 exécute explicitement `alembic upgrade head` via `docker compose run --rm backend alembic upgrade head` avant le démarrage complet des services. Le Dockerfile CMD conserve `alembic upgrade head` comme filet de sécurité idempotent.

### V.2 — Migration image Postgres
✅ `postgres:16-alpine` → `pgvector/pgvector:pg16` : les deux images utilisent PostgreSQL 16, binaires compatibles. Le volume `postgres_data` est externe au container, préservé lors du changement d'image. Step 3/10 du deploy script effectue un `pg_dump` backup automatique avant le teardown comme filet de sécurité.

### V.3 — Activation pgvector au démarrage
✅ Migration `0003_pgvector_knowledge.py` ligne 24 : `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` en première instruction de `upgrade()`. L'image `pgvector/pgvector:pg16` inclut `vector.control` dans `/usr/share/postgresql/16/extension/`.

## Dépendances déploiement

- Variables env prod à ajouter sur le serveur :
  - `RAG_PROVIDER=http`
  - `RAG_HTTP_BASE_URL=https://rag-api.nexusreussite.academy`
  - `RAG_HTTP_COLLECTION=rag_math_correction`
  - `RAG_HTTP_API_TOKEN=<lu depuis compose-ingestor-1>`
- 4 migrations Alembic à appliquer (0003, 0004, 0005, 0006)
- Image Postgres à passer de `postgres:16-alpine` à `pgvector/pgvector:pg16` (volume préservé)

## Rollback

Procédure complète dans `docs/ROLLBACK_PHASE1.md`. Le script de déploiement effectue automatiquement un backup DB avant chaque deploy (step 3/10).

## Known follow-ups (post-merge)

- Refactor : `rag_service.py::retrieve()` duplique le SQL pgvector du `PgvectorRagProvider.retrieve()`. À collapser dans un ticket dédié.
- Endpoint `/admin/documents` du RAG externe retourne 500 — non utilisé par nous mais à signaler à l'équipe RAG.

## Closes

- Remplace la PR #2 (qui sera fermée avec commentaire de redirection après merge de celle-ci)
