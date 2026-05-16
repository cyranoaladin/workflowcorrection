# Production Readiness Design

## Goal

Make the project ready for a first production deployment as a single-tenant admin application.

## Scope

This release is not a multi-user SaaS. It is a secured admin-operated deployment where one trusted operator can create exams, upload student copies, run processing, inspect page images, and trigger OCR.

## Architecture

The backend remains the source of truth and protects every business endpoint with an admin bearer token. Health probes stay public for orchestration. Production settings fail fast when unsafe defaults are used.

OCR remains opt-in. Paid OCR calls require server-side enablement and per-request confirmation. PDF processing is bounded by a maximum page count to avoid resource exhaustion.

Deployment runs behind a TLS reverse proxy. PostgreSQL, Redis, backend, worker, and frontend run as separate services, with only the proxy exposed publicly.

## Release Gates

- All business API routes require authentication.
- Production startup rejects placeholder secrets and insecure CORS/API settings.
- Paid OCR endpoints require explicit confirmation.
- Frontend sends the admin token when configured.
- Frontend build, backend tests, lint, and dependency audit are part of the release checklist.
- Operations documentation covers environment, deployment, smoke tests, backup, restore, and rollback.
