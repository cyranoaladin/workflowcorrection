# Go-Live Checklist

## Required Before Production

- Point `APP_DOMAIN` to the server public IP.
- Copy `.env.production.example` to `.env`.
- Replace every `replace_with_*` value.
- Generate `ADMIN_API_TOKEN` with at least 32 random characters.
  **This token is a backend + Caddy secret only. Never expose it to the browser.**
- Generate the Caddy password hash:
  `docker run --rm caddy:2.8-alpine caddy hash-password --plaintext 'your-password'`
- Keep `OCR_ENABLE_PAID_CALLS=false` until keys, quotas, and billing alerts are verified.
- Set `CORS_ALLOWED_ORIGINS=https://<APP_DOMAIN>`.
- Set `NEXT_PUBLIC_API_BASE_URL` to `https://<APP_DOMAIN>/api` (public, no secret).
- Set `RAG_PROVIDER=http`.
- Set `RAG_HTTP_BASE_URL=http://compose-ingestor-1:8001` when deployed on the colocated Hetzner host.
- Set `RAG_HTTP_COLLECTION=rag_math_correction`.
- Set `RAG_HTTP_API_TOKEN` server-side only. Never expose it in frontend env.
- **Do NOT set `NEXT_PUBLIC_ADMIN_API_TOKEN`** (removed) or **`NEXT_PUBLIC_DEV_ADMIN_TOKEN`**
  in any production file — the production build will fail-fast if `NEXT_PUBLIC_DEV_ADMIN_TOKEN`
  is present. The bearer token is injected by Caddy via
  `header_up Authorization "Bearer {$ADMIN_API_TOKEN}"`. The frontend never sees it.

## Deploy

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml --env-file .env ps
```

## Smoke Test

```bash
curl -fsS https://$APP_DOMAIN/api/health
curl -fsS https://$APP_DOMAIN/api/health/ready
curl -fsS -H "Authorization: Bearer $ADMIN_API_TOKEN" https://$APP_DOMAIN/api/integrations/status
curl -fsS -H "Authorization: Bearer $ADMIN_API_TOKEN" https://$APP_DOMAIN/api/exams
```

Then sign in through Caddy basic auth and verify that the dashboard loads.

## Backup

Run a logical PostgreSQL backup before every release:

```bash
docker compose -f docker-compose.prod.yml --env-file .env exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "backup-$(date +%Y%m%d-%H%M%S).sql"
```

Restore drill:

```bash
cat backup.sql | docker compose -f docker-compose.prod.yml --env-file .env exec -T postgres \
  psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

## Rollback

```bash
git checkout <last-known-good-commit>
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
curl -fsS https://$APP_DOMAIN/api/health/ready
```

## Operational Limits

- `MAX_UPLOAD_SIZE_MB` limits uploaded PDF size.
- `PDF_MAX_PAGES` limits PDF rendering workload.
- `OCR_MAX_PAGES_PER_JOB` limits batch paid OCR calls.
- Page-level OCR still requires `confirm_paid_call=true`.
