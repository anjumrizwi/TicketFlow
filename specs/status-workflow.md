---
status: APPROVED — 2026-08-17
---

# Spec: Status Workflow & Activity History

## Summary

Controlled status transitions (`OPEN -> IN_PROGRESS -> RESOLVED -> CLOSED`,
with `RESOLVED -> IN_PROGRESS` reopening) and the immutable activity log
that records every change. This is the integrity backbone of the app.

## BRD requirements covered

- FR-STAT-01 — status updates only along allowed transitions.
- FR-STAT-02 — illegal transitions (e.g. `CLOSED -> OPEN`) rejected, never
  persisted.
- FR-STAT-03 — priority/category/other permitted fields can be updated.
- FR-STAT-04 — every create/status-change/field-update writes one
  immutable activity row (who, what, old, new, when).
- FR-STAT-05 — status change + its activity row are a single transaction;
  partial updates impossible.
- FR-STAT-06 — ticket detail renders full history, newest first.
- BR-02, BR-03 (legal transitions; CLOSED is terminal), BR-04 (no silent
  edits), NFR-02 (atomicity).

## Out of scope

- SLA timers, escalation, auto-assignment (BRD §3.2).

## Data model touches

- `tickets`: status, priority, category, updated_at.
- `ticket_activity`: id, ticket_id (FK), actor_id (FK), action,
  field_changed, old_value, new_value, created_at.

## Acceptance criteria (draft — refine before approval)

1. `OPEN -> IN_PROGRESS`, `IN_PROGRESS -> RESOLVED`, `RESOLVED -> CLOSED`,
   and `RESOLVED -> IN_PROGRESS` all succeed and each writes one activity
   row.
2. `CLOSED -> OPEN` (or any transition not in BR-02) is rejected with a
   clear message and the ticket's status/activity table are unchanged.
3. A priority or category update writes exactly one activity row with the
   correct old/new values and actor.
4. If the activity-row write fails, the status/field change is rolled
   back — never a change with no corresponding history row, and never a
   history row with no underlying change.
5. The ticket detail view lists all activity rows newest-first, with no
   gaps versus what was actually changed.
6. A user cannot modify a ticket they are not the requester or assignee
   for.
