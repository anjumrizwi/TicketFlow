---
status: APPROVED — 2026-08-17
---

# Spec: Reports & Export

## Summary

CSV and PDF export of the current filtered ticket list, delivered via the
`ticket-export` skill so both formats share one brand-styled
implementation.

## BRD requirements covered

- FR-EXP-01 — download filtered list as CSV.
- FR-EXP-02 — download filtered list as PDF.
- FR-EXP-03 — exports reflect exactly the rows visible under active
  filters/search.
- FR-EXP-04 — exports contain only the logged-in user's data.
- FR-EXP-05 — CSV/PDF generation and brand styling delivered as a reusable
  Claude Code skill (`ticket-export`).
- BR-05 (user scoping).

## Out of scope

- Scheduled/emailed reports (BRD §3.2 — no real email/SMS).

## Data model touches

- Reads only from `tickets`, using exactly the same filtered result set as
  the Ticket List feature — no independent query logic.

## Acceptance criteria (draft — refine before approval)

1. The CSV export contains exactly the rows visible under the currently
   active filters/search — same count, same tickets.
2. The PDF export contains the same rows as the CSV, styled per the brand
   design system (BRD §12): white background, black text, purple
   header, no gradients.
3. Neither export ever includes a ticket belonging to another user, even
   if the in-app filter state were somehow manipulated.
4. Exporting with zero matching tickets produces a valid, empty
   CSV/PDF (header row / empty table), not an error.
5. The `ticket-export` skill is the single implementation used by both
   formats — no duplicated column/status-color logic between them.
