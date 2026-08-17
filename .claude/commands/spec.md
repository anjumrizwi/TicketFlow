---
description: Draft or update a TicketFlow feature spec against its BRD section, with acceptance criteria traced to BRD requirement IDs.
argument-hint: <feature-name>
---

Draft or update the spec for feature `$ARGUMENTS` at `specs/$ARGUMENTS.md`.

1. Read `docs/BRD_TicketFlow.md` and identify every requirement ID (FR-*,
   NFR-*, BR-*) relevant to this feature. Don't guess scope — if the
   feature boundary is ambiguous, ask rather than assume.
2. If `specs/$ARGUMENTS.md` already exists, treat this as an update: keep
   existing acceptance criteria that still hold, and clearly mark what
   changed and why.
3. Write the spec with:
   - A short summary of what the feature does and does not do (respect
     BRD §3.2 out-of-scope items — do not spec anything listed there).
   - The BRD requirement IDs this spec satisfies, quoted or closely
     paraphrased so intent isn't lost.
   - Concrete, testable acceptance criteria — each one should be checkable
     by a single automated test. Vague criteria ("works correctly") are
     not acceptable.
   - Data model touches (which tables/columns) and any transitions or
     invariants that apply (e.g. status workflow, activity-history
     requirement).
4. Do not write implementation code in this command — spec only. Flag the
   spec as a draft; it becomes "approved" only when the user says so
   (implementation must never proceed against an unapproved spec).
