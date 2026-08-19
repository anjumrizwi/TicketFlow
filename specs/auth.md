---
status: APPROVED — 2026-08-17
---

# Spec: Authentication

## Summary

Register, log in, log out, and session handling for TicketFlow. Gates every
other feature: no ticket, reporting, or chat operation is reachable without
an authenticated session.

## BRD requirements covered

- FR-AUTH-01 — register with unique username, email, password.
- FR-AUTH-02 — bcrypt password hashes only; plaintext never persisted/logged.
- FR-AUTH-03 — login; invalid credentials return a generic failure, no user
  enumeration.
- FR-AUTH-04 — session persists across pages until logout/expiry.
- FR-AUTH-05 — logout clears the session.
- FR-AUTH-06 — ticket/reporting/chat operations require an authenticated
  session.
- NFR-01 (secrets/bcrypt), NFR-03 (no PII in logs).

## Out of scope

- SSO/LDAP, granular RBAC beyond Requester/Support agent (BRD §3.2, §10).
- Role selection or self-service escalation at registration: every
  self-registered user is created with role `Requester`. `Support agent`
  accounts are created only via the `seed-data` skill or a direct DB
  update; there is no in-app role picker or promotion flow.
- Timed session expiry. The session is Blazor Server's circuit-scoped
  authentication state (`CurrentUserAccessor`/`AppAuthenticationStateProvider`
  on the `TicketFlowCSharp` branch), held server-side for the lifetime of
  one SignalR circuit — it ends on logout, tab close, or circuit
  disconnect/expiry per the framework's own reconnection-window defaults.
  There is no separate idle/absolute timeout implemented beyond that
  lifecycle.
- Password strength rules (minimum length, complexity). Only "required,
  non-empty" is enforced; the BRD does not specify complexity rules.

## Data model touches

- `users`: id, username (unique), email, password_hash, role (defaults to
  `Requester` on self-registration), created_at.

## Acceptance criteria (draft — refine before approval)

1. Registering with a username or email that already exists is rejected
   with a clear, non-enumerating message.
2. Registering with an empty username, email, or password is rejected with
   a clear message; no row is written.
3. Registering with a valid, unique username/email/password creates a user
   with role `Requester` and a bcrypt password hash; the raw password is
   never stored or logged.
4. Logging in with correct credentials starts a session; with incorrect
   credentials, the failure message is identical whether the username
   exists or not.
5. The session persists across page navigation without re-prompting for
   login, for as long as the underlying session is alive (Streamlit's
   in-memory session state on `main`; a Blazor Server circuit-scoped
   `AuthenticationStateProvider` on `TicketFlowCSharp` — see "Changes
   since last draft").
6. Logging out clears the session; subsequent ticket/report/chat access
   redirects to login.
7. Any attempt to reach ticket, reporting, or chat functionality without an
   active session is blocked before any data is touched.

## Changes since last draft

- Clarified that registration always assigns role `Requester`; `Support
  agent` is provisioned out-of-band (seed data / DB), not via self-service
  (resolves an ambiguity in the BRD's `users.role` column — confirmed with
  the user).
- Added an explicit empty-field validation criterion (AC-2), matching the
  pattern used in `specs/tickets.md` for required fields.
- Clarified FR-AUTH-04's "session persists ... until expiry" as tied to
  Streamlit's in-memory session lifetime, not a separate timed expiry —
  the BRD and stack (bcrypt + Streamlit session state) don't call for a
  token/cookie-based timeout, so none is invented.
- **`TicketFlowCSharp` branch:** reworded AC-5 and the session-expiry
  out-of-scope bullet to describe Blazor Server's circuit-scoped
  `AuthenticationStateProvider` instead of Streamlit's session state —
  same underlying guarantee ("no re-prompt while the session/circuit is
  alive, no separate timed expiry"), different mechanism name. This is a
  BRD-ID-preserving rewording, not a new requirement — see BRD §11a. Also
  worth recording as a genuine (minor) behavior difference, not silently
  absorbed: a slow network reconnect can tear down a Blazor circuit
  (forcing re-login) in a case where a Streamlit session might have
  tolerated the same gap.
