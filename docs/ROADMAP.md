# Phase 2 Roadmap

This document outlines the planned features and improvements for Phase 2 of the Workflow Correction platform.

---

## 1. Dual-Grader (Parallel LLM Reliability)

Run two independent LLM models in parallel on each student copy to improve grading reliability.

- Each copy is sent to Model A and Model B simultaneously.
- Scores are compared; if the delta exceeds a configurable threshold, the copy is flagged for human review.
- Final score can use an aggregation strategy: average, median, or teacher-selected.
- Traceability: both raw responses are stored for audit.

**Goal:** Reduce grading variance and catch hallucinated or inconsistent scores.

---

## 2. MCP Server for Claude.ai / Claude Desktop Integration

Expose the platform as an MCP (Model Context Protocol) server so teachers can interact with exams and corrections directly from Claude Desktop or Claude.ai.

- See `MCP_SERVER_PHASE2.md` for the full design proposal.
- Read-only mode by default; write actions require explicit opt-in.
- Bearer token authentication tied to user accounts.

**Goal:** Let teachers review and validate corrections without leaving their AI assistant.

---

## 3. Multi-Users + RBAC

Introduce proper multi-tenancy and role-based access control.

- **Roles:** Admin, Teacher, Reviewer (read-only).
- Admin can manage users, assign roles, and configure platform settings.
- Teachers see only their own exams and copies.
- Reviewers can view corrections and leave comments but cannot modify grades.
- Permissions enforced at the API layer with middleware guards.

**Goal:** Support multiple teachers on a single instance with proper isolation.

---

## 4. Playwright Browser E2E Tests

Add end-to-end test coverage using Playwright.

- Cover critical flows: login, exam creation, copy upload, grading launch, report viewing.
- Run in CI on every PR against a dockerized backend + frontend.
- Visual regression snapshots for key pages.
- Accessibility checks (axe-core) integrated into the test suite.

**Goal:** Catch UI regressions before they reach production.

---

## 5. Sentry + Prometheus Observability

Implement structured observability across the full stack.

- **Sentry:** Error tracking and performance monitoring for both backend (FastAPI) and frontend (React/Next.js).
- **Prometheus:** Expose `/metrics` endpoint with key indicators:
  - Request latency (p50, p95, p99).
  - LLM call duration and token usage.
  - Grading queue depth and processing time.
  - Error rates by endpoint.
- **Grafana dashboards:** Pre-built dashboards for ops monitoring.
- **Alerting:** Slack/email alerts on error spikes or latency degradation.

**Goal:** Proactive issue detection and data-driven capacity planning.

---

## 6. UI Premium (Split-View, Dark Mode, i18n)

Enhance the user interface with quality-of-life improvements.

- **Split-view:** Side-by-side display of the student copy (PDF/image) and the AI-generated correction report.
- **Dark mode:** System-preference-aware theme toggle with persistent user setting.
- **i18n:** Internationalization support starting with French and English. Use a standard i18n library (e.g., react-i18next). All UI strings extracted to locale files.

**Goal:** Improve teacher comfort and expand to non-francophone users.

---

## 7. Backups to Hetzner Storage Box

Automated, encrypted backups of all critical data to Hetzner Storage Box.

- Daily incremental backups of the PostgreSQL database.
- Weekly full backups of uploaded files (copies, exams).
- Backups encrypted at rest with AES-256 before transfer.
- Transfer via SFTP/rsync over SSH.
- Retention policy: 30 daily, 12 weekly, 6 monthly.
- Restore procedure documented and tested quarterly.

**Goal:** Disaster recovery with affordable, EU-hosted off-site storage.

---

## 8. LLM Quotas per User

Prevent runaway costs by enforcing per-user LLM usage limits.

- Configurable monthly token/request quotas per role (Admin can override per user).
- Real-time usage tracking displayed in the user dashboard.
- Soft limit: warning notification at 80% usage.
- Hard limit: requests rejected with a clear error message at 100%.
- Admin dashboard showing aggregated usage across all users.
- Quota reset on a configurable billing cycle (default: monthly).

**Goal:** Cost control and fair resource sharing in multi-user deployments.

---

## Priority Order

| Priority | Feature | Effort Estimate |
|----------|---------|-----------------|
| 1 | Multi-Users + RBAC | 2 weeks |
| 2 | LLM Quotas per User | 1 week |
| 3 | Dual-Grader | 1.5 weeks |
| 4 | MCP Server | 1 week |
| 5 | Sentry + Prometheus | 1 week |
| 6 | Playwright E2E Tests | 1 week |
| 7 | Backups to Hetzner | 3 days |
| 8 | UI Premium | 2 weeks |

Total estimated effort: ~10 weeks.
