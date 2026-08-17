---
name: ticket-export
description: Generate CSV or PDF exports of the current filtered ticket list, styled to the TicketFlow brand design system. Use when the user asks to export, download, or produce a report of tickets, or implements the Reports page (FR-EXP-01 through FR-EXP-05).
---

# Ticket export (CSV + PDF)

Implements FR-EXP-01 through FR-EXP-05 as one module (`features/reports/service.py`)
so CSV and PDF never visually or structurally drift apart, and so brand
styling is defined once. Wired into the app as the "Reports" page
(`features/reports/ui.py`), which mirrors the Ticket List's own filter
widgets and calls `features.tickets.service.list_tickets` for the query —
there is no independent query logic here.

## Inputs

`generate_csv(tickets, user_id)` / `generate_pdf(tickets, user_id)` take
the **already-filtered** ticket rows exactly as shown under the active
status/priority/category/date-range filters and search term (FR-EXP-03)
— neither function re-queries or re-filters; they only format what
they're given. Both independently re-verify every row's
`requester_id`/`assignee_id` against `user_id` before writing anything
(FR-EXP-04, BR-05, `ReportError` if violated) — never trust the caller's
filter state blindly.

## CSV export

- Columns: ticket number, title, status, priority, category, created
  date, updated date (match the ticket list columns from FR-LIST-01).
- UTF-8, comma-delimited, header row, one ticket per row.
- No row limit beyond what was passed in — the export reflects exactly
  the filtered set, never a truncated sample.
- An empty filtered set still produces a valid header-only CSV, not an
  error (AC-4).

## PDF export

- Built with `fpdf2`. Matches the brand design system (BRD §12): white
  background, black body text, a solid purple title bar (no gradients).
  Tabular layout mirrors the CSV columns exactly.
- An empty filtered set still produces a valid PDF with the title bar and
  an explanatory line ("No tickets match the current filters."), not an
  error (AC-4).
- Not yet implemented, since no approved spec's acceptance criteria
  require it: colored status/priority badges (no in-app status→color
  mapping exists yet to reuse — the Ticket List page currently renders
  status as plain text), and a title-block summary of applied filters.
  Add these only alongside whatever feature first introduces status-color
  styling in the UI, so the two are built from one definition, not two.

## Guardrails

- Never include another user's tickets, even if the caller's filter
  logic has a bug — both `generate_csv` and `generate_pdf` defensively
  re-check every row's requester/assignee against the requesting user id
  before writing output.
- Don't fabricate or infer missing fields. None of the current export
  columns (ticket number, title, status, priority, category, created,
  updated) are nullable on a valid ticket; if a future spec adds a
  nullable exported field, render it as blank, not guessed.
