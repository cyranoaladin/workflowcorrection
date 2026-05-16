# Security Notes

This release is designed for a single trusted admin.

## Access Model

- Caddy basic auth protects the browser application.
- FastAPI business routes require `Authorization: Bearer <ADMIN_API_TOKEN>`.
- Health endpoints remain public for orchestration.

## Sensitive Data

Student copies, page images, and OCR transcriptions are sensitive data. Do not expose the backend directly. Only publish ports `80` and `443` from Caddy.

## OCR Cost Controls

Paid OCR calls require:

- `OCR_ENABLE_PAID_CALLS=true`
- Provider keys configured
- Confirmation query parameter on OCR routes

Keep provider-side billing alerts and quotas enabled.
