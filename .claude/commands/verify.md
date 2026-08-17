---
description: Verify a TicketFlow feature by running test-writer, spec-reviewer, and security-auditor against it, then summarize what's blocking release.
argument-hint: <feature-name>
---

Verify feature `$ARGUMENTS` is ready, using `specs/$ARGUMENTS.md` as the
source of truth.

1. Launch the `test-writer`, `spec-reviewer`, and `security-auditor`
   subagents against feature `$ARGUMENTS`. They can run independently —
   none of them depends on another's output, so launch them together
   rather than one after another.
2. Wait for all three, then synthesize a single report:
   - Acceptance criteria: met / not met (from spec-reviewer), with any
     that lack a passing test (from test-writer) called out explicitly —
     "met" without a test is not verified, per NFR-07.
   - Security/integrity findings (from security-auditor), ranked by
     severity.
   - A clear verdict: ready to consider done, or blocked — and if
     blocked, the specific list of what needs to change.
3. Do not soften or paper over disagreement between subagents (e.g. one
   says "met", another's test fails) — surface the conflict and let the
   evidence (the failing test, or the missing code) decide.
4. Do not fix anything yourself in this command — verification only.
   Report back so the user or a follow-up `/implement` pass can address
   findings.
