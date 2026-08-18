---
name: seed-data
description: Generate demo TicketFlow data — N users each with M realistic, categorized tickets across statuses/priorities, with plausible activity histories. Use when the user asks to seed, reset, or refresh demo/test data, or runs /seed-data <users> <tickets>. Idempotent — safe to re-run.
---

# Seed demo data

Implements FR-SEED-01 through FR-SEED-04. Generates realistic demo data for
manual testing, the test-writer agent's fixtures, and live demos.

## Usage

`/seed-data <users> <tickets>` — e.g. `/seed-data 10 20` creates 10 demo
users with up to 20 tickets each.

## Behavior

Run `python scripts/seed_data.py <users> <tickets>` from the repo root.
The script (`scripts/seed_data.py`, backed by `features/seed_data/service.py`)
implements every step below — don't re-derive this logic by hand with raw
SQL; invoke the script via Bash instead:

1. Connects to SQL Server using the same env-based connection config the
   app uses (`DB_HOST`, `DB_NAME`, etc., loaded via `.env` if present) —
   never hardcode credentials, and never print the connection string.
2. Before inserting, deletes any rows under the reserved `demo_` username
   prefix (and their tickets/activity) so re-running is idempotent:
   existing seeded rows are cleared and regenerated rather than
   duplicated. Never touches non-seeded (real) user data.
3. For each of the `<users>` demo users: unique username/email (bcrypt
   password hash via `features.auth.service.hash_password`, never
   plaintext), role `REQUESTER` or `SUPPORT_AGENT` per the BRD role table
   (weighted toward `REQUESTER`).
4. For each user, generates 1..`<tickets>` tickets via
   `features.tickets.service.create_ticket`, with plausible title text per
   category (Bug, Feature Request, Access, Hardware, How-to / Other) and
   priority spread across LOW/MEDIUM/HIGH/URGENT.
5. Walks each ticket to a randomly chosen target status
   (OPEN/IN_PROGRESS/RESOLVED/CLOSED) using
   `features.tickets.service.transition_status`, which enforces BR-02/BR-03
   and writes one `ticket_activity` row per step in the same transaction as
   the status change — a ticket never lands in RESOLVED with only its
   creation activity row.
6. Prints a summary: users created, tickets created per status, and a
   reminder that re-running with `0 0` clears the seed without recreating
   it.

## Guardrails

- `seed_demo_data` refuses to run — raising before touching any row —
  unless `DB_HOST` is `localhost`/`127.0.0.1`, the strongest available
  signal that this isn't a shared/production database. It also rejects
  negative `<users>`/`<tickets>` values.
- Never seed real-looking PII: usernames use the `demo_` prefix and
  emails use the reserved `@example.invalid` domain, both obviously
  synthetic.
