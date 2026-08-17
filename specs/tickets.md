---
status: APPROVED — 2026-08-17
---

# Spec: Create Ticket

## Summary

Authenticated users create tickets with a title, description, category,
and priority. Creation is the first activity-history event and the start
of the status workflow.

## BRD requirements covered

- FR-TKT-01 — create with title, description, category, priority.
- FR-TKT-02 — title/description required; empty submissions rejected with
  a clear message.
- FR-TKT-03 — priority in {LOW, MEDIUM, HIGH, URGENT}; category in {Bug,
  Feature Request, Access, Hardware, How-to/Other}.
- FR-TKT-04 — unique ticket number, status OPEN, creation activity entry.
- FR-TKT-05 — creating user recorded as requester; scoped to
  creator/assignee.
- BR-01 (new ticket starts OPEN), BR-04 (activity row for every change).

## Out of scope

- File attachments, rich text, threaded comments (BRD §3.2).

## Data model touches

- `tickets`: id, ticket_number (unique), requester_id (FK), assignee_id
  (FK, nullable), title, description, category, priority, status,
  created_at, updated_at.
- `ticket_activity`: one row for the creation event.

## Acceptance criteria (draft — refine before approval)

1. Submitting with an empty title or description is rejected with a clear
   message; no row is written.
2. Submitting a priority outside {LOW, MEDIUM, HIGH, URGENT} or a category
   outside the fixed list is rejected.
3. A valid submission creates a ticket with a unique ticket number, status
   `OPEN`, and the current user as requester.
4. Ticket creation and its activity-history row are written in the same
   transaction (FR-STAT-05 applies from the first write).
5. The new ticket is immediately visible in the creating user's ticket
   list and dashboard counts.
6. Ticket numbers are never reused or duplicated across concurrent
   creations.
