"""Guarded text-to-SQL chat assistant (specs/chat-assistant.md).

FR-AI-01..08, BR-06 (read-only, always user-scoped), NFR-01, NFR-03. This
is the highest-risk feature in the app: every LLM-generated query passes
through `validate_sql` before it can ever reach the database.

The security property this module is built around: the LLM never writes
the user-scoping condition itself, and never controls the actual numeric
user id. The LLM writes its own business-logic filters (status, priority,
date ranges) with no scoping clause of its own; `validate_sql` first
rejects anything that isn't a single, keyword-clean, subquery-free,
JOIN-free SELECT referencing exactly the `tickets` table (no other table,
no second copy of `tickets`); only then does `_inject_scope` — plain
code, not an LLM — parse the query's own WHERE clause (if any) and
structurally AND it with
`(requester_id = %(user_id)s OR assignee_id = %(user_id)s)`, wrapping
whatever the LLM wrote in parentheses first. Because the scoping condition
is always the outermost AND-ed conjunct by construction — never merely
present somewhere in the text — no LLM-authored `OR 1=1` or similar can
neutralize it: it can only ever narrow the LLM's own WHERE clause further,
never widen it. The real, session-authenticated user id is bound as a
genuine DB driver parameter at execution time (`execute_node`), never
string-substituted, and an LLM cannot cause a different value to be used
there — `state["user_id"]` is set once from `ask()`'s argument and no
graph node ever returns that key.

Scope is deliberately restricted to single-table `tickets` queries only
(no `ticket_activity`, no joins of any kind) — earlier revisions allowed
joining `ticket_activity` in, but repeated review rounds kept finding new
join-syntax shapes (non-"JOIN"-spelled join keywords, unconstrained
comma/cross joins between the two allowed tables) that let every user's
activity history leak through a scope clause that could only ever
constrain the `tickets` side. Token-level SQL analysis can rule out
specific shapes but can't prove a join's *semantics* are safe, so the join
surface is removed entirely rather than chased indefinitely — see
specs/chat-assistant.md's "Changes since last draft" note.
"""

import re
from typing import TypedDict

import sqlparse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from sqlparse.sql import Identifier, IdentifierList, Where
from sqlparse.tokens import DML, Keyword

MAX_ATTEMPTS = 2

# Only `tickets` may ever appear in a query's FROM — see the module
# docstring for why `ticket_activity`/joins were removed entirely rather
# than patched further.
REQUIRED_TABLES = {"tickets"}

SCOPE_CONDITION = "requester_id = %(user_id)s OR assignee_id = %(user_id)s"

_CLAUSE_BOUNDARY_KEYWORDS = ("GROUP BY", "ORDER BY", "LIMIT", "HAVING")

# Single-word keywords, matched on a word boundary so this can't false-positive
# on column names like `updated_at`/`created_at` (see _contains_forbidden_keyword).
# "join"/"straight_join" ban any multi-table access outright, regardless of
# which specific join keyword spelling is used (LEFT/RIGHT/INNER/NATURAL/...
# JOIN all contain the word "join"; MySQL's STRAIGHT_JOIN doesn't, hence the
# separate entry).
_FORBIDDEN_WORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "replace",
    "merge",
    "call",
    "exec",
    "execute",
    "set",
    "use",
    "attach",
    "pragma",
    "load_file",
    "information_schema",
    "union",
    "with",
    "join",
    "straight_join",
)
# Multi-word / punctuation-sensitive patterns that need their own regex.
# Comment markers are banned outright, not just scanned for hidden keywords
# inside them: `--`/`#` can truncate everything after them (MySQL executes
# only up to the comment, while `_inject_scope`'s appended clause — added
# by naive string concatenation, not re-parsing — would land inside the
# now-dead comment). `/*` additionally covers MySQL's "versioned comment"
# syntax (`/*!12345 ... */`), which MySQL executes as live SQL but which
# both this module's raw-text keyword scan and `sqlparse`'s tokenizer treat
# as an inert, invisible comment — a documented class of keyword-filter
# bypass. There is no legitimate reason for this assistant's generated SQL
# to contain a comment at all, so any occurrence is rejected rather than
# risking a mismatch between what gets validated and what MySQL executes.
_FORBIDDEN_PATTERNS = (
    re.compile(r"\bsleep\s*\(", re.IGNORECASE),
    re.compile(r"\bbenchmark\s*\(", re.IGNORECASE),
    re.compile(r"\binto\s+outfile\b", re.IGNORECASE),
    re.compile(r"\binto\s+dumpfile\b", re.IGNORECASE),
    re.compile(r"--"),
    re.compile(r"#"),
    re.compile(r"/\*"),
)

SYSTEM_PROMPT = """You are a text-to-SQL assistant for TicketFlow, a ticket \
management system. You answer questions about the current user's own \
tickets by generating exactly one read-only SQL SELECT query.

Schema (MySQL):
  tickets(id, ticket_number, requester_id, assignee_id, title, description,
          category, priority, status, created_at, updated_at)

Rules, all mandatory:
- Output ONLY the SQL query. No explanation, no markdown code fences.
- Exactly one SELECT statement, with no subqueries and no CTEs (no WITH).
  Never write; never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
  TRUNCATE, GRANT, REVOKE, UNION, or any statement type other than one
  plain SELECT.
- The query's only table is `tickets` — no other table, no JOIN of any
  kind, no second reference to `tickets`. Activity-history questions
  can't be answered by this assistant; say so rather than guessing.
- Do NOT add any condition on `requester_id` or `assignee_id` yourself —
  the system adds the user-scoping filter automatically after you
  respond. Just write whatever business-logic filters the question needs
  (status, priority, category, dates) and nothing about the user.
"""


class ChatSQLError(Exception):
    """Raised when generated SQL fails the read-only/single-statement/
    subquery-free/table-allowlisted guard. The query is never executed."""


class ChatState(TypedDict):
    question: str
    user_id: int
    history: list
    sql: str | None
    validation_error: str | None
    attempts: int
    rows: list | None
    answer: str | None
    failed: bool


def _contains_forbidden_keyword(lowered_sql):
    for word in _FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered_sql):
            return word
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(lowered_sql):
            return pattern.pattern
    return None


def _extract_tables(token_list):
    """Recursively collect every table *reference* (schema, name) after a
    FROM/JOIN, including comma-separated lists (`FROM a, b`) and any
    nested token list — not just the single token immediately following
    the keyword. Returns a list, not a set: callers must check both the
    count and the names, so `FROM tickets, tickets` (same table twice)
    isn't silently collapsed into looking like a single reference."""
    tables = []
    tokens = list(getattr(token_list, "tokens", []))
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
            j = i + 1
            while j < len(tokens) and tokens[j].is_whitespace:
                j += 1
            if j < len(tokens):
                target = tokens[j]
                if isinstance(target, IdentifierList):
                    for identifier in target.get_identifiers():
                        name = identifier.get_real_name()
                        if name:
                            tables.append(
                                (identifier.get_parent_name(), name.strip("`").lower())
                            )
                elif isinstance(target, Identifier):
                    name = target.get_real_name()
                    if name:
                        tables.append(
                            (target.get_parent_name(), name.strip("`").lower())
                        )
                elif target.ttype in (sqlparse.tokens.Name, None):
                    tables.append((None, target.value.strip("`").lower()))
            i = j
        if hasattr(token, "tokens"):
            tables += _extract_tables(token)
        i += 1
    return tables


def validate_sql(sql):
    """Validate `sql` is a single, read-only, subquery-free, JOIN-free
    SELECT that references exactly the `tickets` table (see the module
    docstring for why joins/`ticket_activity` are banned outright rather
    than validated). Raises ChatSQLError on any violation — this checks
    structure only; user-scoping itself is applied afterwards by
    `_inject_scope`, not requested of the LLM. Returns `sql` unchanged."""
    if not sql or not sql.strip():
        raise ChatSQLError("Empty query.")

    statements = [
        s for s in sqlparse.parse(sql) if s.token_first(skip_cm=True) is not None
    ]
    if len(statements) != 1:
        raise ChatSQLError("Only a single SQL statement is allowed.")

    statement = statements[0]
    if statement.get_type() != "SELECT":
        raise ChatSQLError("Only read-only SELECT queries are allowed.")

    select_count = sum(
        1 for t in statement.flatten() if t.ttype is DML and t.value.upper() == "SELECT"
    )
    if select_count > 1:
        raise ChatSQLError("Subqueries and nested SELECTs are not allowed.")

    forbidden = _contains_forbidden_keyword(sql.lower())
    if forbidden:
        raise ChatSQLError(
            f"Query contains a disallowed keyword or pattern: {forbidden}."
        )

    tables = _extract_tables(statement)
    if len(tables) != 1:
        raise ChatSQLError(
            "Query must reference exactly one table (tickets), referenced exactly once."
        )
    schema, name = tables[0]
    if schema is not None or name not in REQUIRED_TABLES:
        raise ChatSQLError(
            "Query must reference exactly the tickets table, nothing else."
        )

    return sql


def _inject_scope(sql, statement):
    """Structurally AND `SCOPE_CONDITION` into `sql`'s WHERE clause (code-
    controlled, never LLM text) — the sole enforcement of BR-05/BR-06 for
    this feature. If a WHERE clause already exists, whatever the LLM wrote
    is wrapped in parentheses first, so it can only ever narrow the
    scoping condition, never widen or bypass it."""
    tokens = list(statement.tokens)
    where_index = next((i for i, t in enumerate(tokens) if isinstance(t, Where)), None)

    if where_index is not None:
        where_token = tokens[where_index]
        condition = re.sub(r"(?i)^\s*where\s*", "", where_token.value).strip()
        new_clause = f"WHERE ({condition}) AND ({SCOPE_CONDITION}) "
        before = "".join(t.value for t in tokens[:where_index])
        after = "".join(t.value for t in tokens[where_index + 1 :])
        return f"{before}{new_clause}{after}"

    boundary_index = next(
        (
            i
            for i, t in enumerate(tokens)
            if t.ttype is Keyword
            and re.sub(r"\s+", " ", t.value.upper()) in _CLAUSE_BOUNDARY_KEYWORDS
        ),
        None,
    )
    new_clause = f"WHERE ({SCOPE_CONDITION}) "
    if boundary_index is not None:
        before = "".join(t.value for t in tokens[:boundary_index])
        after = "".join(t.value for t in tokens[boundary_index:])
        return f"{before}{new_clause}{after}"

    return f"{sql.rstrip().rstrip(';')} {new_clause}"


def _extract_sql(content):
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^sql\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _build_generation_messages(state):
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for role, content in state["history"]:
        messages.append(
            HumanMessage(content=content)
            if role == "user"
            else AIMessage(content=content)
        )
    messages.append(HumanMessage(content=state["question"]))
    if state.get("validation_error"):
        messages.append(
            HumanMessage(
                content=(
                    f"Your previous query was rejected: {state['validation_error']} "
                    "Generate a corrected query following all the rules above."
                )
            )
        )
    return messages


def _build_summary_messages(state):
    return [
        SystemMessage(
            content=(
                "You answer the user's question conversationally using ONLY the "
                "query result rows given below. Never invent a number or fact "
                "that isn't in the rows. If the rows are empty, say so plainly."
            )
        ),
        HumanMessage(
            content=f"Question: {state['question']}\nQuery result rows: {state['rows']}"
        ),
    ]


def _build_graph(llm, conn):
    graph = StateGraph(ChatState)

    def generate_sql_node(state):
        response = llm.invoke(_build_generation_messages(state))
        return {
            "sql": _extract_sql(response.content),
            "attempts": state["attempts"] + 1,
        }

    def validate_node(state):
        try:
            validate_sql(state["sql"])
            statement = sqlparse.parse(state["sql"])[0]
            scoped_sql = _inject_scope(state["sql"], statement)
        except ChatSQLError as exc:
            return {"validation_error": str(exc)}
        return {"validation_error": None, "sql": scoped_sql}

    def route_after_validate(state):
        if state["validation_error"] is None:
            return "execute"
        if state["attempts"] < MAX_ATTEMPTS:
            return "generate_sql"
        return "fail"

    def execute_node(state):
        with conn.cursor() as cur:
            cur.execute(state["sql"], {"user_id": state["user_id"]})
            rows = cur.fetchall()
        return {"rows": rows}

    def summarize_node(state):
        response = llm.invoke(_build_summary_messages(state))
        return {"answer": response.content}

    def fail_node(_state):
        return {"failed": True, "answer": "I couldn't safely answer that question."}

    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("validate", validate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("fail", fail_node)

    graph.set_entry_point("generate_sql")
    graph.add_edge("generate_sql", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {"execute": "execute", "generate_sql": "generate_sql", "fail": "fail"},
    )
    graph.add_edge("execute", "summarize")
    graph.add_edge("summarize", END)
    graph.add_edge("fail", END)

    return graph.compile()


def ask(question, user_id, history, conn, llm=None):
    """Run one turn of the guarded text-to-SQL loop (FR-AI-01..08).

    `history` is the prior conversation as a list of `(role, content)`
    tuples (role is `"user"` or `"assistant"`); the caller owns trimming
    and persistence — this function reads it but doesn't store anything.
    `llm` is injectable for testing; defaults to a real `ChatOpenAI`
    reading `OPENAI_API_KEY` from the environment (NFR-01: never
    hardcoded). Returns `{"answer": str, "sql": str | None, "failed": bool}`.
    """
    if llm is None:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    graph = _build_graph(llm, conn)
    initial_state = {
        "question": question,
        "user_id": user_id,
        "history": history,
        "sql": None,
        "validation_error": None,
        "attempts": 0,
        "rows": None,
        "answer": None,
        "failed": False,
    }
    final_state = graph.invoke(initial_state)
    return {
        "answer": final_state["answer"],
        "sql": final_state.get("sql"),
        "failed": final_state.get("failed", False),
        "validation_error": final_state.get("validation_error"),
    }


# Fixed, non-sensitive classification for any exception `ask()` lets escape
# (LLM/API/network failures). Never `str(exc)`: third-party SDK exceptions
# aren't guaranteed not to embed request headers, endpoints, or key
# fragments, so only the exception's class name is recorded (specs/
# chat-assistant.md AC-10, NFR-01).
EXTERNAL_FAILURE_MESSAGE = "The AI service call failed or was unreachable."


def classify_chat_exception(exc):
    """Map an exception from `ask()` to a `(error_type, error_message)` pair
    safe to persist in `chat_error_log` — see `EXTERNAL_FAILURE_MESSAGE`."""
    return type(exc).__name__, EXTERNAL_FAILURE_MESSAGE


def log_chat_error(conn, user_id, error_type, error_message):
    """Persist one scrubbed failure record for this chat turn, scoped to
    `user_id` (specs/chat-assistant.md AC-7/AC-9). Never raises — a logging
    failure degrades to "no row written", never a broken chat turn."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_error_log (user_id, error_type, error_message) "
                "VALUES (%s, %s, %s)",
                (user_id, error_type, error_message),
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            # The connection may already be broken (the likely reason the
            # insert/commit above failed in the first place) — a failing
            # rollback must not escape either, or it defeats the "never
            # raises" guarantee for the exact case it exists to handle.
            pass
