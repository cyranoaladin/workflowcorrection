# Math Correction Platform

> Production deployment notes are in [`docs/GO_LIVE_CHECKLIST.md`](docs/GO_LIVE_CHECKLIST.md) and [`docs/SECURITY.md`](docs/SECURITY.md). Business API routes require `Authorization: Bearer <ADMIN_API_TOKEN>`; only health endpoints are public.

Plateforme MVP pour des **copies de maths scannées** (PDF) avec un workflow **traçable** et **asynchrone**:

- upload de fichiers (sujet / corrigé / barème / copies) ;
- stockage propre sur disque (prêt pour migration MinIO) ;
- conversion **PDF → images PNG à 300 DPI** (PyMuPDF) ;
- prétraitement image (OpenCV) ;
- création des pages en base (`copy_pages`) ;
- exposition des images via API ;
- interface Next.js locale pour visualiser pages et statuts.

Les briques IA (**Mathpix / Azure Document Intelligence / OpenAI**) sont **présentes en stubs** (fonctions + gestion “skipped” si clés absentes), mais **non activées** pour “corriger magiquement”.

## MVP vs Phase 2

**MVP fonctionnel (implémenté)**:
- CRUD minimal examens + copies
- upload PDF → stockage
- tâche Celery `process_copy`:
  - rendu 300 DPI
  - prétraitement
  - pages + images servies
- UI Next.js locale: dashboard, listes, détail copy + viewer

**Phase 2 (OCR contrôlé, implémenté mais désactivé par défaut)**:
- OCR page par page: Mathpix / Azure Document Intelligence / OpenAI Vision
- stockage traçable en base (table `transcriptions`, brut + fusion)
- endpoints de consultation:
  - `GET /pages/{page_id}/transcriptions`
  - `GET /copies/{copy_id}/transcriptions`
- fusion prudente:
  - `POST /pages/{page_id}/ocr/fuse` (ne fait aucun appel payant)
- OCR copie (optionnel) **limité**:
  - `POST /copies/{copy_id}/ocr` (max `OCR_MAX_PAGES_PER_JOB`)
- **Sécurité**: `OCR_ENABLE_PAID_CALLS=false` par défaut → aucun appel Mathpix/Azure/OpenAI ne part.

**Phase 3 (à compléter)**:
- structuration par question
- correction par barème + audit + rapport JSON complet

## Structure

```
backend/   FastAPI + SQLAlchemy + Alembic + Celery
frontend/  Next.js local
scripts/   init/deploy/backup/smoke-test
storage/   examens/copies/pages/... (bind mount)
```

## Installation serveur (cible: `/opt/math-correction`)

### 1) Initialisation serveur (optionnel)

Sur le serveur (root):

```bash
/opt/math-correction/scripts/init-server.sh
```

Ce script:
- met à jour `apt` ;
- installe Docker si absent ;
- vérifie Docker Compose ;
- crée `/opt/math-correction` + sous-dossiers `storage/` ;
- vérifie si le port `8000` est libre.

### 2) Déployer le code

Option A (recommandé): via Git

```bash
cd /opt
git clone <ton_repo_git> math-correction
cd /opt/math-correction
```

Option B: copier le dossier (scp/rsync) vers `/opt/math-correction`.

### 3) Configurer l’environnement

```bash
cd /opt/math-correction
cp .env.example .env
```

Puis **modifie impérativement**:
- `POSTGRES_PASSWORD`
- `DATABASE_URL` (doit matcher le password)
- `JWT_SECRET` (même si auth non utilisée en MVP)

OCR (Phase 2) — **par défaut les appels payants sont désactivés**:
- `OCR_ENABLE_PAID_CALLS=false`
- `OCR_MAX_PAGES_PER_JOB=3`
- `OCR_DEFAULT_IMAGE_TYPE=processed`
- renseigner ensuite les clés `MATHPIX_*`, `AZURE_*`, `OPENAI_*` si besoin.

### 4) Lancer la stack (backend + worker + DB + Redis)

```bash
cd /opt/math-correction
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
```

Health checks:

```bash
curl http://localhost:8000/health
curl http://46.224.150.0:8000/health
```

## Frontend local (ta machine)

Pré-requis: Node.js récent (idéalement Node 20+).

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

`frontend/.env.local` doit contenir:

`NEXT_PUBLIC_API_BASE_URL=http://46.224.150.0:8000`

## Tests API (upload + conversion)

### 1) Créer un examen

```bash
curl -X POST http://46.224.150.0:8000/exams \
  -H "Content-Type: application/json" \
  -d '{"title":"DS Maths","level":"Terminale","session":"2026"}'
```

### 2) Uploader sujet/corrigé/barème

```bash
curl -X POST http://46.224.150.0:8000/exams/<exam_id>/files \
  -F subject_pdf=@./sujet.pdf\;type=application/pdf \
  -F correction_pdf=@./corrige.pdf\;type=application/pdf \
  -F rubric_pdf=@./bareme.pdf\;type=application/pdf
```

### 3) Uploader une copie

```bash
curl -X POST http://46.224.150.0:8000/copies \
  -F exam_id=<exam_id> \
  -F student_name="Eleve 1" \
  -F file=@./copie.pdf\;type=application/pdf
```

### 4) Lancer traitement (Celery)

```bash
curl -X POST http://46.224.150.0:8000/copies/<copy_id>/process
curl http://46.224.150.0:8000/copies/<copy_id>/status
curl http://46.224.150.0:8000/copies/<copy_id>/pages
```

### 4bis) Idempotence / relances

Relance **sans** `force` (si déjà traité): pas d’erreur, réponse explicite:

```bash
curl -X POST "http://46.224.150.0:8000/copies/<copy_id>/process"
```

Relance **avec** `force=true` (purge pages + suppression des images dérivées + recalcul):

```bash
curl -X POST "http://46.224.150.0:8000/copies/<copy_id>/process?force=true"
```

### 5) Voir une page (image)

```bash
curl "http://46.224.150.0:8000/pages/<page_id>/image?type=original" -o page_original.png
curl "http://46.224.150.0:8000/pages/<page_id>/image?type=processed" -o page_processed.png
```

## Tests automatiques (pytest)

Dans `/opt/math-correction` (serveur):

```bash
docker compose exec backend pytest -q
```

## Scénario de test manuel complet

1) Health checks:

```bash
curl http://46.224.150.0:8000/health
curl http://46.224.150.0:8000/health/live
curl http://46.224.150.0:8000/health/ready
```

2) Créer un examen:

```bash
exam_json="$(curl -fsS -X POST http://46.224.150.0:8000/exams -H 'Content-Type: application/json' -d '{\"title\":\"DS Maths\",\"level\":\"Terminale\",\"session\":\"2026\"}')"
echo "$exam_json"
```

3) Uploader sujet/corrigé/barème:

```bash
exam_id="<exam_id>"
curl -X POST "http://46.224.150.0:8000/exams/$exam_id/files" \
  -F subject_pdf=@./sujet.pdf\;type=application/pdf \
  -F correction_pdf=@./corrige.pdf\;type=application/pdf \
  -F rubric_pdf=@./bareme.pdf\;type=application/pdf
```

4) Uploader une copie:

```bash
copy_json="$(curl -fsS -X POST http://46.224.150.0:8000/copies \
  -F exam_id=$exam_id \
  -F student_name='Eleve 1' \
  -F copy_code='A1' \
  -F file=@./copie.pdf\;type=application/pdf)"
echo "$copy_json"
```

5) Lancer traitement:

```bash
copy_id="<copy_id>"
curl -X POST "http://46.224.150.0:8000/copies/$copy_id/process"
curl "http://46.224.150.0:8000/copies/$copy_id/status"
curl "http://46.224.150.0:8000/copies/$copy_id/pages"
```

6) Afficher une page:

```bash
page_id="<page_id>"
curl "http://46.224.150.0:8000/pages/$page_id/image?type=original" -o original.png
curl "http://46.224.150.0:8000/pages/$page_id/image?type=processed" -o processed.png
```

7) Relancer traitement sans force:

```bash
curl -X POST "http://46.224.150.0:8000/copies/$copy_id/process"
```

8) Relancer traitement avec force:

```bash
curl -X POST "http://46.224.150.0:8000/copies/$copy_id/process?force=true"
curl "http://46.224.150.0:8000/copies/$copy_id/pages"
```

9) Tester le frontend local:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

## Intégrations (diagnostic, sans appel payant)

```bash
curl http://46.224.150.0:8000/integrations/status
```

## OCR contrôlé (Phase 2) — activation prudente

### Variables `.env` (sécurité)

Par défaut:
- `OCR_ENABLE_PAID_CALLS=false` → les endpoints OCR payants répondent `403 paid_calls_disabled`.
- `OCR_MAX_PAGES_PER_JOB=3` → limite dure sur `POST /copies/{copy_id}/ocr`.
- `OCR_DEFAULT_IMAGE_TYPE=processed` → image par défaut (prétraitée) pour l’OCR.

Pour activer (à faire **en connaissance de cause**):
1) mettre `OCR_ENABLE_PAID_CALLS=true`
2) renseigner **au moins une** intégration:
   - Mathpix: `MATHPIX_APP_ID`, `MATHPIX_APP_KEY`
   - Azure: `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY`
   - OpenAI: `OPENAI_API_KEY`

### Tester une seule page (recommandé)

Prérequis: copie déjà `processed_pages` et `page_id` connu.

Mathpix (1 page):

```bash
curl -X POST "http://46.224.150.0:8000/pages/$page_id/ocr/mathpix?image_type=processed"
```

Azure Document Intelligence (1 page):

```bash
curl -X POST "http://46.224.150.0:8000/pages/$page_id/ocr/azure?image_type=processed"
```

OpenAI Vision (1 page, transcription uniquement):

```bash
curl -X POST "http://46.224.150.0:8000/pages/$page_id/ocr/openai-vision?image_type=processed"
```

Consulter les transcriptions stockées:

```bash
curl "http://46.224.150.0:8000/pages/$page_id/transcriptions"
curl "http://46.224.150.0:8000/copies/$copy_id/transcriptions"
```

Fusion prudente (sans appel payant, utilise les transcriptions existantes):

```bash
curl -X POST "http://46.224.150.0:8000/pages/$page_id/ocr/fuse"
```

### OCR d’une copie (limité)

⚠️ Ce endpoint peut déclencher plusieurs appels (boucle sur pages), mais **ne dépassera jamais** `OCR_MAX_PAGES_PER_JOB`.
⚠️ Garde-fou supplémentaire: il exige `confirm_paid_calls=true` quand `OCR_ENABLE_PAID_CALLS=true`.

```bash
curl -X POST "http://46.224.150.0:8000/copies/$copy_id/ocr?max_pages=3&sources=azure&confirm_paid_calls=true"
```

Sources possibles: `sources=azure&sources=mathpix&sources=openai_vision`

### Coût & prudence

- Ne pas activer `OCR_ENABLE_PAID_CALLS=true` tant que tu n’es pas prêt à assumer des coûts.
- Toujours commencer par 1 page, comparer les sorties, puis fusionner et valider humainement.
- Ne pas lancer d’OCR sur “toutes les copies” sans limite stricte.

## Endpoints (backend)

- `GET /health`
- `POST /exams`
- `GET /exams`
- `GET /exams/{exam_id}`
- `POST /exams/{exam_id}/files`
- `POST /copies`
- `GET /copies` (option: `?exam_id=...`)
- `GET /copies/{copy_id}`
- `POST /copies/{copy_id}/process` (option: `?force=true`)
- `GET /copies/{copy_id}/pages`
- `GET /pages/{page_id}/image?type=original|processed`
- `GET /copies/{copy_id}/status`
- `GET /copies/{copy_id}/correction` (MVP: vide)

## Stockage

- Sur le serveur: `/opt/math-correction/storage`
- Dans les containers: `/app/storage` (via bind mount)
- Les chemins stockés en DB sont **relatifs** (ex: `copies/<id>/original.pdf`, `pages/<page_id>/processed.png`)

## Sécurité minimale

- Les ports hôte PostgreSQL/Redis ne sont **pas exposés** (réseau Docker uniquement).
- Le backend est exposé sur `8000` (prévu pour passer derrière Nginx/HTTPS ensuite).
- Ne jamais committer `.env` (uniquement `.env.example`).

## Dépannage

- Logs: `docker compose logs -f backend` / `docker compose logs -f worker`
- Rebuild: `docker compose up -d --build`
- Migration DB: exécutée au démarrage backend (`alembic upgrade head`)
- Permissions storage: s’assurer que `/opt/math-correction/storage` est accessible au process Docker (bind mount)
