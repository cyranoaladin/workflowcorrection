# MCP Server Design Proposal (Phase 2)

This document describes the design for exposing the Workflow Correction platform as an MCP (Model Context Protocol) server, enabling integration with Claude.ai and Claude Desktop.

---

## Overview

The MCP server allows a teacher to interact with exams, student copies, and correction reports directly from their AI assistant (Claude Desktop or Claude.ai). The server exposes a set of read-only tools by default, with an optional write action for validation.

---

## Tools

### `list_exams`

List all exams accessible to the authenticated user.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | No | Filter by status: `draft`, `grading`, `completed`. Default: all. |
| `limit` | integer | No | Max results to return. Default: 20. |
| `offset` | integer | No | Pagination offset. Default: 0. |

**Returns:** Array of exam summaries (id, title, subject, status, copy count, creation date).

---

### `get_exam`

Retrieve full details of a specific exam, including its grading rubric.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `exam_id` | string | Yes | The UUID of the exam. |

**Returns:** Exam object with title, subject, description, rubric (criteria + point allocations), total copies, graded count, and status.

---

### `get_copy_report`

Retrieve the correction report for a specific student copy.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `copy_id` | string | Yes | The UUID of the student copy. |
| `include_raw_llm` | boolean | No | Include raw LLM responses (useful for debugging). Default: false. |

**Returns:** Report object with student identifier, scores per criterion, total score, textual feedback, grader model used, and optionally the raw LLM output.

---

### `validate_correction`

Mark a correction as validated (teacher-approved). This is the only write action and requires explicit opt-in.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `copy_id` | string | Yes | The UUID of the student copy. |
| `approved` | boolean | Yes | `true` to approve, `false` to reject and flag for re-grading. |
| `comment` | string | No | Optional teacher comment or reason for rejection. |

**Returns:** Updated copy status.

**Note:** This tool is disabled by default. The server must be started with `--enable-write` or the environment variable `MCP_WRITE_ENABLED=true` to activate it.

---

## Authentication

All requests are authenticated via a Bearer token in the MCP transport layer.

- Tokens are tied to existing user accounts in the platform.
- Token generation is done through the web UI (Settings > API Tokens) or via the REST API.
- Tokens inherit the RBAC permissions of the user (see Roadmap: Multi-Users + RBAC).
- Tokens have a configurable expiry (default: 90 days) and can be revoked at any time.

### Configuration in Claude Desktop

```json
{
  "mcpServers": {
    "workflow-correction": {
      "command": "npx",
      "args": ["-y", "@workflow-correction/mcp-server"],
      "env": {
        "WC_API_URL": "https://your-instance.example.com/api",
        "WC_TOKEN": "wc_tok_xxxxxxxxxxxx"
      }
    }
  }
}
```

Alternatively, the server can run as a standalone process:

```bash
wc-mcp-server --api-url https://your-instance.example.com/api --token wc_tok_xxxxxxxxxxxx
```

---

## Read-Only Mode (Default)

By default, the MCP server operates in read-only mode:

- `list_exams`, `get_exam`, and `get_copy_report` are available.
- `validate_correction` is hidden and returns an error if called.
- This prevents accidental modifications when the teacher is simply reviewing data via their assistant.

To enable write operations:

```bash
wc-mcp-server --enable-write
# or
WC_WRITE_ENABLED=true wc-mcp-server
```

---

## Use Cases

### Teacher Reviewing Corrections via Claude Desktop

A typical workflow:

1. **Teacher:** "Show me the exams I created this month."
   - Claude calls `list_exams` with no filters.
   - Claude presents a summary table.

2. **Teacher:** "Open the Math midterm and show me copies with low scores."
   - Claude calls `get_exam` to fetch rubric details.
   - Claude identifies copies below a threshold from the exam data.

3. **Teacher:** "Show me the report for student copy abc-123."
   - Claude calls `get_copy_report` with `copy_id = "abc-123"`.
   - Claude displays the score breakdown, feedback, and highlights areas where the student lost points.

4. **Teacher:** "The grading looks correct, approve it."
   - Claude calls `validate_correction` with `approved = true`.
   - The copy is marked as teacher-validated in the platform.

5. **Teacher:** "This one seems too harsh on question 3, reject it with a note."
   - Claude calls `validate_correction` with `approved = false` and a comment explaining the issue.
   - The copy is flagged for re-grading or manual adjustment.

### Batch Review

A teacher can ask Claude to summarize all corrections for an exam, flag outliers, and approve the rest in bulk. This dramatically reduces the time spent on manual review.

---

## Technical Notes

- The MCP server communicates with the platform via the existing REST API (no direct database access).
- Transport: stdio (for Claude Desktop) or SSE (for web-based clients).
- The server is stateless; all state lives in the platform backend.
- Rate limiting follows the same rules as the REST API.
- Logging: all MCP tool invocations are logged with user ID and timestamp for audit.
