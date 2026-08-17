---
status: APPROVED — 2026-08-17
---

# Spec: Ticket List, Search & Filters

## Summary

The user's ticket list with composable filters (status, priority,
category, date range) and free-text search across title/description.

## BRD requirements covered

- FR-LIST-01 — list newest-first with ticket number, title, status,
  priority, category, date.
- FR-LIST-02 — filter by status/priority/category/date range, any
  combination.
- FR-LIST-03 — free-text search across title and description.
- FR-LIST-04 — filters and search compose (search further narrows the
  active filter set).
- FR-LIST-05 — only the logged-in user's tickets; cross-user access
  impossible.
- BR-05 (user scoping).

## Out of scope

- Saved filter presets, team/queue-wide views (BRD §3.2).

## Data model touches

- Reads only from `tickets`, filtered to requester/assignee = current
  user.

## Acceptance criteria (draft — refine before approval)

1. The list shows only the current user's tickets, newest first, with all
   six required columns.
2. Applying any single filter (status, priority, category, or date range)
   narrows the list correctly.
3. Applying multiple filters together narrows to the intersection, not
   the union.
4. A search term filters by substring match against title or description,
   composing with any active filters rather than replacing them.
5. Clearing filters/search returns to the full (user-scoped) list.
6. No combination of filter/search parameters can surface another user's
   ticket, even via crafted input.
