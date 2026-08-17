---
author:
- Business Requirements Document
date: Version 1.0
title: BRD --- TicketFlow
---

# 1. Executive Summary

TicketFlow is a web-based ticket management system built to teach
end-to-end spec-driven development with Claude Code on a realistic,
well-bounded domain.

After logging in, a user lands on a dashboard showing open ticket
counts, recent tickets, and quick actions. Users can raise a ticket,
update its status through a controlled workflow, search and filter the
ticket list, and download reports. Every change is captured in an
immutable activity history.

The system also includes a conversational AI assistant. Users can ask
plain-English questions about their tickets, such as "How many
high-priority tickets are still open?", and receive accurate,
data-grounded answers. The assistant uses guarded text-to-SQL with
conversation memory, wrapped in a LangGraph safety loop that validates
every generated query as a single, read-only, user-scoped `SELECT`
before it is executed.

The application is designed to look polished and deployment-ready using
the brand design system in Section 12. It remains a learning artifact
and therefore favours clarity and correct patterns---specs, hooks,
agents, and skills---over real-world helpdesk completeness.

# 2. Business Objectives

-   Demonstrate end-to-end spec-driven development using Claude Code on
    a realistic, well-bounded domain.
-   Teach correct application fundamentals, including validated state
    transitions, auditability, and least-surprise data integrity.
-   Teach a practical pattern for embedding a conversational LLM feature
    with chat memory and guarded text-to-SQL over the user's own data.
-   Showcase the Claude Code toolset: `CLAUDE.md`, specs, slash
    commands, hooks, subagents, skills, and plugins.
-   Produce a polished, presentable, deployment-ready teaching asset
    that learners can run locally and demonstrate.

# 3. Scope

## 3.1 In Scope

-   User authentication: register, login, logout, and session handling.
-   Dashboard/home with open, in-progress, and resolved counts; recent
    tickets; and quick actions.
-   Ticket creation with title, description, category, and priority.
-   Ticket detail with controlled status workflow:
    `Open -> In Progress -> Resolved -> Closed`.
-   Immutable ticket activity history.
-   Ticket list with search and filters for status, priority, category,
    and date range.
-   Reports/export of the ticket list as CSV and PDF, delivered as
    reusable Claude Code skills.
-   Conversational AI chat assistant with session memory over the
    logged-in user's tickets.
-   Demo data seeding for realistic analysis and testing.
-   Polished Streamlit frontend using the brand design system.
-   Deployment-ready local/demo configuration.

## 3.2 Out of Scope

-   Real email/SMS notifications, SLA timers, escalation engines, and
    CSAT surveys.
-   Multi-tenant organisations, teams, queues, and round-robin
    auto-assignment.
-   File attachments, rich-text editors, and threaded public/private
    comments.
-   SSO/LDAP, granular RBAC beyond the roles in Section 10, and
    production security hardening.
-   Mobile-native application.
-   Real customer PII handling; this is a demo build.

# 4. Stakeholders & Personas

  -----------------------------------------------------------------------
  Stakeholder / Persona               Interest / Responsibility
  ----------------------------------- -----------------------------------
  Course learners                     Follow the build and understand
                                      each Claude Code feature in
                                      context.

  End user --- "Aarav"                Raises tickets, tracks their
                                      status, and chats with the
                                      assistant about open items.

  Support agent --- "Neha"            Works assigned tickets, moves them
                                      through the workflow, and reports
                                      on the queue.

  Training Lead --- "Rahul"           Owns the asset and uses it for
                                      YouTube/corporate training and as a
                                      deployable demo.
  -----------------------------------------------------------------------

### Primary Persona --- Aarav

Aarav is a 31-year-old non-technical employee. He raises support tickets
when something breaks, wants a clean view of what is open and what
changed, and likes to casually ask questions such as "what's still
pending on me?" in a chat that remembers the conversation.

# 5. Assumptions & Constraints

  -----------------------------------------------------------------------
  ID                                  Assumption / Constraint
  ----------------------------------- -----------------------------------
  AC-01                               MySQL is installed locally and
                                      reachable; the application connects
                                      via PyMySQL using a connection
                                      string.

  AC-02                               A single MySQL user (`root`) is
                                      used for all database access in
                                      this demo. Production would use a
                                      least-privilege, read-only user for
                                      the AI layer.

  AC-03                               Ticket status values are
                                      constrained to a fixed set;
                                      transitions follow the workflow in
                                      Section 9.

  AC-04                               All timestamps are stored in UTC;
                                      the UI renders local time.

  AC-05                               The OpenAI API key is supplied
                                      through an environment variable and
                                      is never hardcoded or logged.

  AC-06                               This is a demo: no real customer
                                      PII and no production support
                                      obligations.
  -----------------------------------------------------------------------

# 6. Functional Requirements

## 6.1 Authentication --- FR-AUTH

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-AUTH-01                          A visitor can register with a
                                      unique username, email, and
                                      password.

  FR-AUTH-02                          Passwords are stored only as bcrypt
                                      hashes; plaintext is never
                                      persisted or logged.

  FR-AUTH-03                          A registered user can log in;
                                      invalid credentials return a
                                      generic failure without user
                                      enumeration.

  FR-AUTH-04                          A logged-in session persists across
                                      pages until logout or expiry.

  FR-AUTH-05                          A user can log out, clearing the
                                      session.

  FR-AUTH-06                          All ticket, reporting, and chat
                                      operations require an authenticated
                                      session.
  -----------------------------------------------------------------------

## 6.2 Dashboard / Home --- FR-DASH

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-DASH-01                          Immediately after login, the user
                                      sees a summary dashboard.

  FR-DASH-02                          The dashboard displays counts of
                                      tickets by status (Open, In
                                      Progress, Resolved, Closed), scoped
                                      to the user.

  FR-DASH-03                          The dashboard shows the user's most
                                      recent tickets (for example, the
                                      last 5) with title, status,
                                      priority, and date.

  FR-DASH-04                          The dashboard offers quick
                                      actions/navigation to Create
                                      Ticket, Ticket List, Reports, and
                                      Chat Assistant.

  FR-DASH-05                          All figures reflect live data and
                                      update after any ticket creation or
                                      status change.
  -----------------------------------------------------------------------

## 6.3 Create Ticket --- FR-TKT

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-TKT-01                           An authenticated user can create a
                                      ticket with a title, description,
                                      category, and priority.

  FR-TKT-02                           Title and description are required;
                                      empty submissions are rejected with
                                      a clear message.

  FR-TKT-03                           Priority is one of `LOW`, `MEDIUM`,
                                      `HIGH`, or `URGENT`; category is
                                      from a fixed list: Bug, Feature
                                      Request, Access, Hardware, How-to /
                                      Other.

  FR-TKT-04                           On creation, the ticket gets a
                                      unique ticket number, status
                                      `OPEN`, and a creation entry in the
                                      activity history.

  FR-TKT-05                           The creating user is recorded as
                                      the requester; tickets are scoped
                                      to their creator and assignee.
  -----------------------------------------------------------------------

## 6.4 Status Workflow & Activity History --- FR-STAT

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-STAT-01                          A user can update a ticket's status
                                      only along an allowed transition
                                      defined in Section 9.

  FR-STAT-02                          An illegal transition, such as
                                      `CLOSED -> OPEN` directly, is
                                      rejected with a clear message and
                                      is never persisted.

  FR-STAT-03                          A user can update ticket priority,
                                      category, and other permitted
                                      fields.

  FR-STAT-04                          Every create, status change, and
                                      field update writes an immutable
                                      row to the activity history
                                      containing who, what, old value,
                                      new value, and when.

  FR-STAT-05                          The status change and its history
                                      row are written in a single
                                      database transaction; partial
                                      updates are impossible.

  FR-STAT-06                          The ticket detail view renders the
                                      full activity history, newest
                                      first.
  -----------------------------------------------------------------------

## 6.5 Ticket List, Search & Filters --- FR-LIST

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-LIST-01                          A user can view a list of their
                                      tickets, newest first, with ticket
                                      number, title, status, priority,
                                      category, and date.

  FR-LIST-02                          The list can be filtered by status,
                                      priority, category, and date range,
                                      in any combination.

  FR-LIST-03                          The user can search tickets by free
                                      text across title and description.

  FR-LIST-04                          Filters and search compose; an
                                      active search further filters the
                                      current filter set.

  FR-LIST-05                          The list shows only the logged-in
                                      user's tickets; cross-user access
                                      is impossible.
  -----------------------------------------------------------------------

## 6.6 Reports & Export --- FR-EXP

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-EXP-01                           A user can download the current
                                      filtered ticket list as a CSV file.

  FR-EXP-02                           A user can download the current
                                      filtered ticket list as a PDF
                                      report.

  FR-EXP-03                           Exports reflect exactly the rows
                                      visible under the active
                                      filters/search.

  FR-EXP-04                           Exports contain only the logged-in
                                      user's data.

  FR-EXP-05                           CSV and PDF generation are
                                      delivered as reusable Claude Code
                                      skills; brand styling is delivered
                                      as a skill so reports remain
                                      consistent.
  -----------------------------------------------------------------------

## 6.7 GenAI Chat Assistant --- FR-AI

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-AI-01                            The assistant is presented as a
                                      chat: user messages are
                                      right-aligned and assistant
                                      messages are left-aligned in a
                                      scrolling conversation.

  FR-AI-02                            The conversation has memory; the
                                      assistant retains prior turns in
                                      the session and answers follow-up
                                      questions in context.

  FR-AI-03                            The user can ask free-text
                                      questions about their own tickets,
                                      including counts by
                                      status/priority/category, recent
                                      activity, and trends, and receive
                                      accurate, data-grounded answers.

  FR-AI-04                            The assistant answers using only
                                      the logged-in user's data; it never
                                      fabricates figures and never
                                      exposes another user's data.

  FR-AI-05                            For data questions, the LLM (OpenAI
                                      API via LangChain) produces a
                                      parameterized SQL query scoped to
                                      the current user.

  FR-AI-06                            A LangGraph safety loop validates
                                      each generated query: generate SQL
                                      -\> validate as a single read-only,
                                      user-scoped `SELECT` -\> regenerate
                                      if unsafe -\> run -\> summarize
                                      conversationally.

  FR-AI-07                            Any query that is not a single
                                      user-scoped `SELECT` is rejected
                                      and never executed. This is a
                                      code-level runtime guard because a
                                      single root DB user is used in the
                                      demo.

  FR-AI-08                            Conversation memory persists for
                                      the duration of the session;
                                      clearing the chat resets the
                                      memory.
  -----------------------------------------------------------------------

## 6.8 Demo Data Seeding --- FR-SEED

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FR-SEED-01                          A seeding capability generates N
                                      demo users, each with M realistic,
                                      categorized tickets across statuses
                                      and priorities.

  FR-SEED-02                          Seeded tickets carry plausible
                                      activity histories (created,
                                      progressed, resolved) consistent
                                      with the workflow.

  FR-SEED-03                          Seeding is idempotent or clearly
                                      resettable; re-running does not
                                      corrupt data.

  FR-SEED-04                          Seeding is delivered as a Claude
                                      Code skill such as
                                      `/seed-data <users> <tickets>`,
                                      invokable manually or autonomously
                                      during testing.
  -----------------------------------------------------------------------

# 7. Non-Functional Requirements

  -----------------------------------------------------------------------
  ID                      Category                Requirement
  ----------------------- ----------------------- -----------------------
  NFR-01                  Security                Secrets only via
                                                  environment variables;
                                                  never committed or
                                                  logged. Bcrypt is used
                                                  for passwords.
                                                  AI-generated SQL is
                                                  validated as read-only
                                                  and user-scoped before
                                                  execution.

  NFR-02                  Data Integrity          Every status/field
                                                  change is atomic in a
                                                  single database
                                                  transaction and
                                                  produces exactly one
                                                  history row.

  NFR-03                  Privacy                 Email addresses and
                                                  other PII are never
                                                  written to logs; the
                                                  chat never leaks
                                                  cross-user data.

  NFR-04                  Usability               Clean dashboard-first
                                                  flow, clear validation
                                                  messages, and chat
                                                  behaviour similar to a
                                                  familiar messaging app.

  NFR-05                  Performance             Common operations
                                                  respond within
                                                  approximately 2 seconds
                                                  on local MySQL; chat
                                                  responses return
                                                  promptly.

  NFR-06                  Maintainability         Code is organized by
                                                  feature; each feature
                                                  maps to a spec;
                                                  conventions are defined
                                                  in `CLAUDE.md`.

  NFR-07                  Testability             Every acceptance
                                                  criterion has at least
                                                  one automated test
                                                  through a test-writer
                                                  subagent; the
                                                  end-to-end flow is
                                                  scripted.

  NFR-08                  Presentation & UI       The application is
                                                  visually polished,
                                                  consistent with the
                                                  design system, and
                                                  ready to deploy with
                                                  documented,
                                                  environment-based
                                                  setup.
  -----------------------------------------------------------------------

# 8. Data Model --- High Level

### `users`

-   `id`
-   `username` (unique)
-   `email`
-   `password_hash`
-   `role`
-   `created_at`

### `tickets`

-   `id`
-   `ticket_number` (unique)
-   `requester_id` (FK)
-   `assignee_id` (FK, nullable)
-   `title`
-   `description`
-   `category`
-   `priority`
-   `status`
-   `created_at`
-   `updated_at`

### `ticket_activity`

-   `id`
-   `ticket_id` (FK)
-   `actor_id` (FK)
-   `action`
-   `field_changed`
-   `old_value`
-   `new_value`
-   `created_at`

This is an immutable audit log.

### `chat_messages` --- Optional

-   `id`
-   `user_id` (FK)
-   `role` (`user` / `assistant`)
-   `content`
-   `created_at`

This is used only if chat history is persisted beyond the session.

> Detailed schema---including column types, indexes, and
> constraints---is owned by the relevant feature specification, not by
> this BRD.

# 9. Business Rules

  -----------------------------------------------------------------------
  ID                                  Business Rule
  ----------------------------------- -----------------------------------
  BR-01                               A new ticket always starts in
                                      status `OPEN`.

  BR-02                               Allowed status transitions are
                                      `OPEN -> IN_PROGRESS`,
                                      `IN_PROGRESS -> RESOLVED`,
                                      `RESOLVED -> CLOSED`, and
                                      `RESOLVED -> IN_PROGRESS` for
                                      reopening.

  BR-03                               `CLOSED` is terminal. Reopening
                                      requires creating activity from
                                      `RESOLVED`; a direct
                                      `CLOSED -> OPEN` jump is not
                                      allowed.

  BR-04                               Every state or field change has a
                                      corresponding activity-history row;
                                      there are no silent edits.

  BR-05                               A user can only ever read/write
                                      their own tickets (as requester or
                                      assignee) and their own chat.

  BR-06                               The chat assistant is read-only: it
                                      never writes to any table and is
                                      always user-scoped.
  -----------------------------------------------------------------------

# 10. Roles & Permissions

  -----------------------------------------------------------------------
  Role                                Permissions
  ----------------------------------- -----------------------------------
  Visitor                             Register and log in.

  End user / Requester                Create tickets, view/search/filter
                                      own tickets, update own tickets
                                      along allowed transitions, export,
                                      and use chat---all scoped to self.

  Support agent                       All requester abilities, plus work
                                      on tickets assigned to them and
                                      progress them through the workflow.

  AI chat                             Read-only `SELECT` scoped to the
                                      requesting user, enforced in
                                      application code over the shared
                                      root connection.
  -----------------------------------------------------------------------

# 11. Technology Stack

  -----------------------------------------------------------------------
  Layer / Area                        Technology
  ----------------------------------- -----------------------------------
  Language                            Python 3.10+

  Frontend                            Streamlit, custom-styled to the
                                      brand design system

  Database                            MySQL (local) via PyMySQL; single
                                      root user for this demo

  Authentication                      bcrypt + Streamlit session state

  GenAI                               OpenAI model via LangChain (chat
                                      with memory + guarded text-to-SQL);
                                      LangGraph for the validation loop

  Reporting                           CSV + PDF export delivered as
                                      Claude Code skills

  Testing                             pytest (unit + integration),
                                      scripted end-to-end

  Developer tooling                   Claude Code: `CLAUDE.md`, `specs/`,
                                      slash commands, hooks, subagents,
                                      skills, plugins

  Deployment                          Local run + deployable to a
                                      Streamlit-compatible host;
                                      environment-based configuration
  -----------------------------------------------------------------------

# 12. UI / UX & Design System

The application must look polished and presentable for demos and
deployment. The visual language uses the brand palette in solid colours,
with no gradients, a white background, and black text throughout.

## 12.1 Colour Palette

The source document specifies the following functional use of the brand
palette:

-   Green: positive/success states, primary call-to-action buttons, and
    user chat bubbles.
-   Purple: brand/section headers, sidebar navigation, and assistant
    chat styling.
-   Pink: accents, empty/active badges, secondary accents, and
    urgent-priority styling.

## 12.2 Layout & Typography

-   Background: white.
-   Text: black for all content, labels, values, and chat text.
-   Clean sans-serif typography.
-   Consistent spacing.
-   Card-based dashboard with rounded corners and subtle shadows.
-   Left sidebar navigation in purple: Dashboard, Create Ticket, Ticket
    List, Reports, Chat Assistant.
-   Status shown as coloured badges with clear contrast.
-   Buttons use solid brand colours, with black or white labels as
    contrast requires.
-   Ticket counts are shown in large, prominent summary cards.

## 12.3 Chat Assistant --- Messaging-App Style

-   Scrolling conversation view.
-   Assistant messages are left-aligned in white bubbles with a purple
    border.
-   User messages are right-aligned in solid green (`#00E676`) bubbles.
-   All bubble text is black for readability.
-   Fixed input box at the bottom with a send button.
-   Pressing Send appends the message and the assistant replies in
    context.
-   Typing/loading indicator while the assistant responds.
-   Conversation scrolls to the latest message.
-   Visible "Clear chat" control resets the conversation and its memory.

# 13. Success Criteria --- Business-Level Acceptance

  -----------------------------------------------------------------------
  ID                                  Success Criterion
  ----------------------------------- -----------------------------------
  SC-01                               A new user can register, log in,
                                      create a ticket, move it through
                                      the workflow, and view it in their
                                      list without errors.

  SC-02                               After login, the dashboard
                                      correctly shows status counts and
                                      the user's recent tickets.

  SC-03                               An illegal status transition is
                                      always blocked, and every legal
                                      change appears in the activity
                                      history.

  SC-04                               A user can maintain a continuous
                                      multi-turn chat where the assistant
                                      remembers context and correctly
                                      answers at least five distinct
                                      ticket questions from their own
                                      data.

  SC-05                               Crafted prompt-injection input
                                      cannot read another user's data or
                                      mutate any data.

  SC-06                               The UI matches the design
                                      system---palette, white background,
                                      black text---and is
                                      presentable/deployable.

  SC-07                               Every functional requirement traces
                                      to a spec, and every spec
                                      acceptance criterion traces to a
                                      passing test.
  -----------------------------------------------------------------------

# 14. Risks & Mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  AI-generated SQL is unsafe when the LangGraph runtime guard validates
  demo uses a full-privilege root DB  generated SQL as a single
  user                                user-scoped `SELECT` before
                                      execution. This is demo-only;
                                      production would use a read-only
                                      database user.

  LLM fabricates figures or leaks     Ground all data answers in
  other users' data                   user-scoped query results and
                                      enforce user data scope in code. No
                                      cross-user access path is
                                      permitted.

  Illegal or silent status changes    Transition rules are enforced in
  corrupt the audit trail             code; every change is atomic and
                                      requires a history row (BR-02 and
                                      BR-04).

  Destructive commands during the     Pre-hooks block dangerous
  build                               operations such as `DROP TABLE`;
                                      safe operations can be
                                      auto-approved. Post-hooks format
                                      and test after edits.

  Scope creep beyond the teaching     The out-of-scope list in Section
  goal                                3.2 is binding; new ideas become
                                      future enhancements.
  -----------------------------------------------------------------------

# 15. Traceability & Delivery Flow

1.  **BRD** --- Defines what the business needs through FR, NFR, and BR
    identifiers.
2.  **Specs** --- One specification per feature translates requirements
    into precise behaviour and acceptance criteria, each referencing BRD
    IDs.
3.  **Development** --- Implementation is performed against the approved
    spec using the spec → implement → verify loop through custom slash
    commands.
4.  **Testing** --- Test cases are written from each spec's acceptance
    criteria by the test-writer subagent.
5.  **Review** --- The spec-reviewer subagent checks implementation
    against the approved specification.
6.  **Security** --- The security-auditor subagent enforces NFR-01,
    NFR-02, and NFR-03.
7.  **Hooks** --- Hooks continuously enforce conventions,
    formatting/testing, and protection against destructive commands.
8.  **End-to-End Validation** --- The complete user journey is validated
    against the business-level success criteria.
9.  **Reusable Tooling** --- Commands, hooks, agents, and skills are
    packaged as a Claude Code plugin for reuse.

The resulting traceability chain is:

**BRD requirement → spec acceptance criterion → implementation → test
case → verification**

# 16. Glossary

  -----------------------------------------------------------------------
  Term                                Definition
  ----------------------------------- -----------------------------------
  Status workflow                     The fixed set of allowed ticket
                                      states and the legal transitions
                                      between them.

  Activity history                    An immutable audit log with one row
                                      per create, status change, or field
                                      update.

  Text-to-SQL                         Converting a natural-language
                                      question into a SQL query.

  Guarded                             Generated SQL is validated as a
                                      single, read-only, user-scoped
                                      `SELECT` before execution.

  Conversation memory                 Prior turns are retained so the
                                      assistant can answer follow-up
                                      questions in context.

  Spec-driven development             Code is written only against an
                                      approved specification with
                                      explicit acceptance criteria.

  Runtime guard                       Validation that ships inside the
                                      application, such as the LangGraph
                                      SQL validation loop.

  Build-time agent                    A security-auditor or other
                                      subagent that operates during the
                                      software build process.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

**Document status:** BRD v1.0 --- pending review and sign-off before
specifications are derived.
