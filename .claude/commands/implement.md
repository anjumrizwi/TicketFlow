---
description: Implement a TicketFlow feature strictly against its approved spec, then hand off to /verify.
argument-hint: <feature-name>
---

Implement feature `$ARGUMENTS` against `specs/$ARGUMENTS.md`.

1. Read `specs/$ARGUMENTS.md`. If it doesn't exist or is still a draft
   (not confirmed approved by the user), stop and say so — do not
   implement against an unapproved or missing spec. Suggest running
   `/spec $ARGUMENTS` first.
2. Read `CLAUDE.md` for conventions and non-negotiables before writing
   any code (user-scoping, atomic transaction writes, bcrypt, env-only
   secrets, status-transition rules).
3. Implement only what the spec's acceptance criteria require — no extra
   fields, pages, or abstractions beyond what's specified.
4. For anything touching ticket status/field changes: write the change
   and its `ticket_activity` row in a single transaction.
5. For anything touching the chat assistant or SQL generation: route
   through the existing LangGraph validation loop — do not add a new,
   separate DB access path.
6. Match the design system (BRD §12) for any UI surface you touch.
7. When implementation is done, run `/verify $ARGUMENTS` to generate
   tests and get spec/security review before considering the feature
   complete.
