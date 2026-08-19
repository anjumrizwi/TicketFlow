---
status: APPROVED — 2026-08-17
---

# Spec: Dashboard / Home

## Summary

The landing view after login: status counts, recent tickets, and quick
navigation, scoped entirely to the logged-in user.

## BRD requirements covered

- FR-DASH-01 — summary dashboard shown immediately after login.
- FR-DASH-02 — counts by status (Open, In Progress, Resolved, Closed),
  scoped to the user.
- FR-DASH-03 — most recent tickets (e.g. last 5) with title, status,
  priority, date.
- FR-DASH-04 — quick actions to Create Ticket, Ticket List, Reports, Chat
  Assistant.
- FR-DASH-05 — figures reflect live data, updating after any ticket
  creation or status change.
- BR-05 (user scoping).

## Out of scope

- Notifications, SLA timers, team/queue views (BRD §3.2).

## Data model touches

- Reads only from `tickets` (and implicitly `ticket_activity` for recency),
  filtered to the requester/assignee = current user.

## Acceptance criteria (draft — refine before approval)

1. Immediately after login, the dashboard renders without requiring
   navigation.
2. Status counts match the actual count of the user's tickets in each
   status — verified against a direct query, not just the UI.
3. The 5 most recent tickets shown belong only to the current user and are
   ordered newest-first.
4. Each quick action link navigates to the correct page (Create Ticket,
   Ticket List, Reports, Chat Assistant).
5. Creating a ticket or changing a status, then returning to the
   dashboard, shows updated counts/recent list without a stale cache
   (Streamlit's rerun-per-interaction model on `main`; on `TicketFlowCSharp`,
   `DashboardService.GetDashboardDataAsync` re-runs a fresh, live,
   user-scoped query every time the Home component initializes — there is
   no `[ResponseCache]`/`IMemoryCache` layer on this path, so navigating
   back to the dashboard after any change never shows a stale snapshot —
   see "Changes since last draft").
6. A second user's tickets never appear in the counts or recent list.

## Changes since last draft

- **`TicketFlowCSharp` branch:** reworded AC-5 to describe Blazor's
  per-navigation component re-initialization instead of Streamlit's
  rerun-per-interaction model — same underlying guarantee ("never a stale
  snapshot"), different mechanism. BRD-ID-preserving rewording, not a new
  requirement (see BRD §11a).
- **`TicketFlowCSharp` branch:** AC-4's Create Ticket, Ticket List,
  Reports, and Chat Assistant quick actions are all implemented as of the
  Chat Assistant stage — incremental migration is complete for this
  feature.
