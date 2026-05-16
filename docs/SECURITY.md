# Security Notes

This release is designed for a single trusted admin.

## Access Model

- Caddy Basic Auth protects the browser application and all API routes except health.
- FastAPI business routes require `Authorization: Bearer <ADMIN_API_TOKEN>`.
  **Caddy injects this header server-side** via `header_up Authorization "Bearer {$ADMIN_API_TOKEN}"`.
  The frontend never reads, stores, or transmits `ADMIN_API_TOKEN` in production.
  `NEXT_PUBLIC_ADMIN_API_TOKEN` is removed. `NEXT_PUBLIC_DEV_ADMIN_TOKEN` is the sole
  permitted dev escape-hatch (local direct-backend access only); it is ignored at
  runtime when `NODE_ENV=production` and the production build fails fast if it is set.
- Health endpoints (`/api/health`, `/api/health/live`, `/api/health/ready`) remain public
  for orchestration and are forwarded by Caddy without authentication.

## Sensitive Data

Student copies, page images, and OCR transcriptions are sensitive data. Do not expose the backend directly. Only publish ports `80` and `443` from Caddy.

## OCR Cost Controls

Paid OCR calls require:

- `OCR_ENABLE_PAID_CALLS=true`
- Provider keys configured
- Confirmation query parameter on OCR routes

Keep provider-side billing alerts and quotas enabled.
