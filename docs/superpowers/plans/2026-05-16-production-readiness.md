# Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app production-ready for a single-tenant admin deployment.

**Architecture:** Add bearer-token auth and prod config validation in the backend, wire the frontend to pass the token, harden OCR and PDF processing, complete the production compose stack, and document go-live operations.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Redis, PostgreSQL, Next.js, Docker Compose, Caddy.

---

## Chunk 1: Backend Security

- [ ] Add failing tests for protected business routes and public health routes.
- [ ] Implement admin bearer token dependency.
- [ ] Apply dependency to exams, copies, pages, corrections, and integrations routers.
- [ ] Add production settings validation and tests.

## Chunk 2: Abuse And Cost Guards

- [ ] Add failing tests for page OCR confirmation and PDF page limit.
- [ ] Require confirmation on all paid OCR endpoints.
- [ ] Enforce maximum PDF page count in worker processing.
- [ ] Stop returning tracebacks to API clients/task results.

## Chunk 3: Frontend Auth

> **SUPERSEDED by fix/production-final-hardening** — `NEXT_PUBLIC_ADMIN_API_TOKEN` has been
> removed entirely. The `Authorization: Bearer` header is now injected **server-side by Caddy**
> via `header_up`. The frontend never holds the token.

- [x] Remove `NEXT_PUBLIC_ADMIN_API_TOKEN` from `frontend/lib/api.ts`, `frontend/Dockerfile`,
      `frontend/.env.local.example`, `docker-compose.prod.yml`, and all documentation.
- [x] Caddy injects `Authorization: Bearer {$ADMIN_API_TOKEN}` for all business API routes.
- [x] Frontend build remains clean (no bearer token in bundle).

## Chunk 4: Deployment And Ops

- [ ] Add frontend service and Caddy reverse proxy to production compose.
- [ ] Add Caddyfile.
- [ ] Add production environment template.
- [ ] Add go-live checklist and smoke-test documentation.

## Chunk 5: Verification

- [ ] Install/verify dependencies if needed.
- [ ] Run backend tests.
- [ ] Run frontend build.
- [ ] Run lint/audit and report any residual blocker.
