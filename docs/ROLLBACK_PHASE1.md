# Phase 1 Rollback

Use this if the Phase 1 RAG deployment fails health checks or smoke tests.

## Before Deployment

Create backups:

```bash
cd /opt/math-correction
TS=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > /root/pre-rag-deploy-$TS.sql.gz
tar czf /root/pre-rag-deploy-storage-$TS.tar.gz storage/
cp .env /root/pre-rag-deploy-env-$TS
git rev-parse HEAD > /root/pre-rag-deploy-head-$TS
```

## Rollback

```bash
cd /opt/math-correction
TS_PREV=$(ls /root/pre-rag-deploy-head-* | tail -1 | sed 's|.*deploy-head-||')
PREV_HEAD=$(cat /root/pre-rag-deploy-head-$TS_PREV)
git fetch origin
git reset --hard "$PREV_HEAD"
cp /root/pre-rag-deploy-env-$TS_PREV .env
chmod 600 .env
zcat /root/pre-rag-deploy-$TS_PREV.sql.gz | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose down --remove-orphans
docker compose up -d --build
curl -fsS http://localhost:8000/health/ready
```
