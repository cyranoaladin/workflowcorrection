# Math Correction Platform

Plateforme de **correction automatique de copies de mathematiques** avec pipeline complet : OCR multi-source, notation IA avec contexte RAG, audit LLM-as-judge, et validation humaine.

> **Production** : [maths.labomaths.tn/correction](https://maths.labomaths.tn/correction/)

## Fonctionnalites

- **Upload** : sujet PDF, corrige PDF, bareme PDF/JSON, copies eleves
- **OCR multi-source** : Azure Document Intelligence, Mathpix, OpenAI Vision, fusion intelligente
- **RAG** : indexation automatique du corrige et du bareme, injection de contexte dans la notation
- **Notation IA** : LLM grading par question avec baremes structures
- **Audit** : verification rule-based + LLM-as-judge avec recommandation tri-state (validate / review_partial / review_full)
- **UI complete** : Next.js avec suivi RAG, flags d'audit, validation manuelle, export bilan CSV

## Architecture

```
backend/    FastAPI + SQLAlchemy 2.0 + Alembic + Celery (5 containers)
frontend/   Next.js 16 + React 19 + Tailwind (1 container)
storage/    examens/copies/pages/reports (bind mount)
scripts/    deploy/backup/smoke-test

Stack RAG colocalise (3 containers) :
  compose-ingestor-1 (port 8001) + compose-chroma-1 + compose-ollama-1
  Communication via reseau Docker compose_rag_ui_net
```

Voir [docs/ARCHITECTURE_RAG.md](docs/ARCHITECTURE_RAG.md) pour le detail.

## Quickstart developpement

```bash
cp .env.example .env
# Remplir OPENAI_API_KEY, POSTGRES_PASSWORD, etc.
docker compose up -d --build
docker compose logs -f backend
```

Frontend local :

```bash
cd frontend
cp .env.local.example .env.local
npm install && npm run dev
```

## Quickstart production

Voir [docs/GO_LIVE_CHECKLIST.md](docs/GO_LIVE_CHECKLIST.md) pour le deploiement complet.

```bash
cd /opt/math-correction
cp .env.production.example .env
# Remplir toutes les variables (voir docs/OPERATIONS.md)
docker compose -f docker-compose.labomaths.yml up -d --build
curl http://localhost:8010/health/ready
```

## Documentation

| Document | Description |
|----------|-------------|
| [USER_GUIDE.md](docs/USER_GUIDE.md) | Guide enseignant : workflow complet de correction |
| [OPERATIONS.md](docs/OPERATIONS.md) | Runbook ops : architecture, commandes, diagnostic |
| [ARCHITECTURE_RAG.md](docs/ARCHITECTURE_RAG.md) | Topologie Docker et RAG |
| [SECURITY.md](docs/SECURITY.md) | Politique de securite |
| [ROLLBACK_PHASE1.md](docs/ROLLBACK_PHASE1.md) | Procedure de rollback |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Guide de contribution |
| [ROADMAP.md](docs/ROADMAP.md) | Phase 2 et au-dela |

## Tests

```bash
# Dans le container backend
docker compose exec backend pytest -q

# Depuis le repo local (necessite venv avec dependances)
cd backend && pytest -q
```

26 fichiers de tests : unit, integration, E2E.

## Endpoints principaux

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health/ready` | Healthcheck avec checks DB, Redis, Storage, RAG |
| POST | `/exams` | Creer un examen |
| POST | `/exams/{id}/files` | Uploader sujet/corrige/bareme |
| POST | `/exams/{id}/rubric-json` | Definir le bareme structure |
| POST | `/exams/{id}/embed` | Lancer l'indexation RAG |
| GET | `/exams/{id}/knowledge` | Lister les documents indexes |
| POST | `/copies` | Uploader une copie eleve |
| POST | `/copies/{id}/process` | Traiter le PDF (pages) |
| POST | `/pages/{id}/ocr/{source}` | OCR page (azure/mathpix/openai-vision/fuse) |
| POST | `/copies/{id}/grade` | Lancer la notation IA |
| GET | `/copies/{id}/report` | Rapport complet avec audit |
| PATCH | `/corrections/{id}/validate` | Valider/modifier une note |
| GET | `/exams/{id}/bilan` | Bilan classe (CSV) |

Tous les endpoints metier necessitent `Authorization: Bearer <ADMIN_API_TOKEN>`.

## Securite

- Ports PostgreSQL/Redis non exposes (reseau Docker uniquement)
- Caddy injecte le Bearer token — le navigateur ne voit jamais le secret
- `.env` en `chmod 600` sur le serveur
- `OCR_ENABLE_PAID_CALLS=false` par defaut

## Licence

Projet prive.
