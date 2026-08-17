---
status: APPROVED — 2026-08-17
---

# Spec: Demo Data Seeding

## Summary

Idempotent generation of N demo users with M realistic, categorized
tickets and plausible activity histories, delivered as the `seed-data`
skill (`/seed-data <users> <tickets>`).

## BRD requirements covered

- FR-SEED-01 — generate N users, each with M realistic categorized
  tickets across statuses/priorities.
- FR-SEED-02 — seeded tickets carry plausible activity histories
  consistent with the workflow.
- FR-SEED-03 — idempotent or clearly resettable; re-running doesn't
  corrupt data.
- FR-SEED-04 — delivered as a Claude Code skill, invokable manually or
  during automated testing.

## Out of scope

- Seeding production-realistic PII (BRD §5 AC-06 — demo only, no real
  customer data).

## Data model touches

- `users`, `tickets`, `ticket_activity` — writes only to clearly marked
  demo rows (see guardrail below).

## Acceptance criteria (draft — refine before approval)

1. `/seed-data <users> <tickets>` creates exactly the requested number of
   demo users, each with 1..<tickets> tickets.
2. Every seeded ticket's status was reached only via legal transitions
   (BR-02), with a corresponding activity row for each step — no ticket
   appears in `RESOLVED` with only a single "created" activity row.
3. Re-running `/seed-data` with the same or different counts does not
   duplicate or corrupt previously seeded rows, and never touches
   non-seeded (real) user data.
4. Seeded users/emails are obviously synthetic, never resembling real
   PII.
5. The skill refuses to run, with a clear warning, if the target database
   doesn't look like the local/demo database.
