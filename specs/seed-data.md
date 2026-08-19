---
status: APPROVED — 2026-08-17
---

# Spec: Demo Data Seeding

## Summary

Idempotent generation of N demo users with M realistic, categorized
tickets and plausible activity histories, delivered as the `seed-data`
skill (`/seed-data <users> <tickets>`) on `main`; as the `TicketFlow.SeedCli`
console command (`dotnet run --project src/TicketFlow.SeedCli -- <users>
<tickets>`) on `TicketFlowCSharp`.

## BRD requirements covered

- FR-SEED-01 — generate N users, each with M realistic categorized
  tickets across statuses/priorities.
- FR-SEED-02 — seeded tickets carry plausible activity histories
  consistent with the workflow.
- FR-SEED-03 — idempotent or clearly resettable; re-running doesn't
  corrupt data.
- FR-SEED-04 — invokable manually by a developer/tester or from automated
  test setup; not exposed to Requester/Support-agent end users inside the
  running app. On `main`, delivered as a Claude Code skill; on
  `TicketFlowCSharp`, a standalone `TicketFlow.SeedCli` console command
  (see "Changes since last draft").

## Out of scope

- Seeding production-realistic PII (BRD §5 AC-06 — demo only, no real
  customer data).

## Data model touches

- `users`, `tickets`, `ticket_activity` — writes only to clearly marked
  demo rows (see guardrail below).

## Acceptance criteria (draft — refine before approval)

1. `/seed-data <users> <tickets>` (`main`) or
   `dotnet run --project src/TicketFlow.SeedCli -- <users> <tickets>`
   (`TicketFlowCSharp`) creates exactly the requested number of demo
   users, each with 1..<tickets> tickets.
2. Every seeded ticket's status was reached only via legal transitions
   (BR-02), with a corresponding activity row for each step — no ticket
   appears in `RESOLVED` with only a single "created" activity row.
3. Re-running with the same or different counts does not duplicate or
   corrupt previously seeded rows, and never touches non-seeded (real)
   user data.
4. Seeded users/emails are obviously synthetic, never resembling real
   PII.
5. The tool refuses to run, with a clear error, if the target database
   doesn't look like the local/demo database.

## Changes since last draft

- **`TicketFlowCSharp` branch:** reworded the skill-invocation phrasing to
  the console-command form; the underlying guarantees (exact counts,
  legal-transition-only status paths, idempotent re-run, synthetic-only
  data, local-DB guardrail) are unchanged — see BRD §11a.
- **`TicketFlowCSharp` branch, guardrail correction:** the demo-database
  guard now strips a SQL Server named-instance suffix (e.g.
  `localhost\SQLEXPRESS`) before comparing against `localhost`/`127.0.0.1`.
  Ported as-is, the Python reference app's exact-string check would
  incorrectly refuse to seed against the connection string actually used
  since the SQL Server migration (`DB_HOST=localhost\SQLEXPRESS`) — worth
  fixing on `main` too as a follow-up, tracked separately from this port.
