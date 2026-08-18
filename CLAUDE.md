# TicketFlow

A Streamlit + SQL Server ticket management system built to teach spec-driven
development with Claude Code. Full requirements: [docs/BRD_TicketFlow.md](docs/BRD_TicketFlow.md).
This is a teaching artifact, not a production helpdesk — favor clarity and
correct patterns over feature completeness. The out-of-scope list in the
BRD (§3.2) is binding; new ideas become future enhancements, not scope creep.

## Stack

- Python 3.10+, Streamlit frontend (custom-styled, see Design System below)
- SQL Server via pyodbc, Windows/AD integrated auth (Trusted_Connection)
  to a local/demo instance (see Security)
- Auth: bcrypt + Streamlit session state
- GenAI: OpenAI via LangChain (chat + text-to-SQL), LangGraph for the SQL
  safety loop
- Testing: pytest (unit + integration)

## Spec-driven workflow

Every feature lives as one spec under `specs/`, each referencing BRD
requirement IDs (FR-*, NFR-*, BR-*). The delivery loop is:

1. `/spec <feature>` — draft or update the spec against its BRD section.
2. `/implement <feature>` — build strictly against the **approved** spec.
   Do not implement ahead of an approved spec or invent requirements.
3. `/verify <feature>` — runs the `test-writer`, `spec-reviewer`, and
   `security-auditor` subagents together against the spec's acceptance
   criteria.

Traceability chain: BRD requirement → spec acceptance criterion →
implementation → test case → verification. If a spec and the BRD
disagree, the BRD wins — flag the discrepancy rather than silently
picking one.

## Code organization

Organize by feature, not by layer: each feature (auth, dashboard, tickets,
status-workflow, list-search, reports-export, chat-assistant, seed-data)
maps to one spec and one code area. Shared code (db connection, auth
helpers, design-system components) lives in a common module used by all
features, not duplicated per feature.

## Non-negotiables (NFR-01, NFR-02, NFR-03, BR-05, BR-06)

- Passwords: bcrypt hashes only. Never log, print, or persist plaintext.
- Secrets (`OPENAI_API_KEY`, DB connection string) come only from
  environment variables. Never hardcode or log them.
- Every ticket/status/field query and mutation is scoped to the
  authenticated user (as requester or assignee). There is no code path
  that reads or writes another user's tickets.
- The chat assistant is read-only: it may only ever execute a single,
  validated, user-scoped `SELECT`. It never writes to any table. Every
  AI-generated query passes through the LangGraph validation loop before
  execution — no exceptions, even for "obviously safe" queries.
- Every ticket create, status change, or field update writes exactly one
  row to `ticket_activity`, in the same DB transaction as the change
  itself (FR-STAT-05). Partial updates must be impossible.
- Status transitions are only ever those in BR-02/BR-03. Validate in code,
  not just in the UI.
- No PII (emails, etc.) in logs.

## Design system (BRD §12)

White background, black text, no gradients. Green = success/primary
actions/user chat bubbles. Purple = brand/headers/sidebar/assistant chat.
Pink = accents/badges/urgent-priority. Card-based layout, rounded corners,
subtle shadows. Keep shared styling in one place so reports (`ticket-export`
skill) and the UI never visually drift apart.

## Conventions

- Format with `black`/`ruff` before considering an edit done (enforced by
  a post-edit hook — see `.claude/hooks/`).
- Every acceptance criterion in a spec needs at least one automated test.
  Don't mark a feature done without one.
- Prefer fixing the underlying cause over bypassing a hook or check.
