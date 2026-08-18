"""Tests for features/tickets/service.py against specs/tickets.md acceptance
criteria (AC-1..AC-6).

All tests use the fake, in-memory pyodbc-shaped connection/cursor from
tests/conftest.py (FakeCursor/FakeConnection via the `make_conn` fixture) --
no real SQL Server instance is required or assumed, mirroring the auth
suite's approach (see test_auth_service.py).

Notes on two acceptance criteria that can't be fully proven at this unit
level:

- AC-5 ("immediately visible in the creating user's ticket list and
  dashboard counts"): there is no list/dashboard UI yet -- that is a
  separate, not-yet-implemented spec. This is exercised here only via
  `get_ticket(conn, ticket_id, user_id)` returning the just-created ticket
  when scoped to the creating user and nothing when scoped to a different
  user_id (the same requester/assignee scoping list/dashboard queries will
  need to reuse). Full list/dashboard visibility is flagged as not yet
  applicable, the same way test_session.py flags FR-AUTH-06 for pages that
  don't exist yet.
- AC-6 ("ticket numbers are never reused or duplicated across concurrent
  creations"): this is a DB-level guarantee -- IDENTITY `id` plus a
  filtered UNIQUE index on `ticket_number` (see common/db.py), with the
  number deterministically derived from the id. A single-threaded fake
  cursor cannot exercise real concurrent inserts or a real UNIQUE
  constraint, so this suite only proves the unit-level pieces of that
  guarantee (the format is deterministic and different ids produce
  different numbers by construction). Proving the concurrency guarantee
  itself is a gap here -- it needs an integration test against a real SQL
  Server instance and is not covered by this suite.
"""

import pytest

from features.tickets.service import (
    CATEGORIES,
    PRIORITIES,
    TicketError,
    create_ticket,
    get_ticket,
)


def _valid_ticket_row(**overrides):
    row = {
        "id": 42,
        "ticket_number": "TCK-000042",
        "requester_id": 7,
        "assignee_id": None,
        "title": "Printer is on fire",
        "description": "It's smoking and smells bad.",
        "category": "Hardware",
        "priority": "HIGH",
        "status": "OPEN",
        "created_at": "2026-08-17 00:00:00",
        "updated_at": "2026-08-17 00:00:00",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# AC-1 (FR-TKT-02): empty title/description rejected, no row written.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,description",
    [
        ("", "Valid description"),
        ("   ", "Valid description"),
        (None, "Valid description"),
        ("Valid title", ""),
        ("Valid title", "   "),
        ("Valid title", None),
    ],
)
def test_fr_tkt_02_empty_or_blank_title_or_description_rejected(
    make_conn, title, description
):
    conn = make_conn(fetchone_results=[])

    with pytest.raises(TicketError) as exc_info:
        create_ticket(conn, 1, title, description, "Bug", "LOW")

    # AC-1 requires a "clear message" -- assert it actually names the blank
    # field, not just that *some* TicketError was raised (a message-less or
    # mislabeled exception would satisfy `pytest.raises(TicketError)` alone
    # but would not be a "clear message").
    title_is_blank = not (title and title.strip())
    expected_field = "Title" if title_is_blank else "Description"
    assert expected_field in str(exc_info.value)

    # Validation happens before any DB access: a blank title/description
    # can never reach the INSERT.
    assert conn.cursor_obj.executed == []
    assert conn.commit_calls == 0


# ---------------------------------------------------------------------------
# AC-2 (FR-TKT-03): priority/category outside the fixed sets rejected, no
# row written.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category", ["Not-A-Category", "", "bug", None, "Feature request"]
)
def test_fr_tkt_03_invalid_category_rejected_no_insert(make_conn, category):
    conn = make_conn(fetchone_results=[])

    with pytest.raises(TicketError) as exc_info:
        create_ticket(conn, 1, "Valid title", "Valid description", category, "LOW")

    # AC-2 requires rejection to be clear about *what* was invalid.
    assert "Category" in str(exc_info.value)
    assert conn.cursor_obj.executed == []
    assert conn.commit_calls == 0


@pytest.mark.parametrize("priority", ["CRITICAL", "low", "", None])
def test_fr_tkt_03_invalid_priority_rejected_no_insert(make_conn, priority):
    conn = make_conn(fetchone_results=[])

    with pytest.raises(TicketError) as exc_info:
        create_ticket(conn, 1, "Valid title", "Valid description", "Bug", priority)

    # AC-2 requires rejection to be clear about *what* was invalid.
    assert "Priority" in str(exc_info.value)
    assert conn.cursor_obj.executed == []
    assert conn.commit_calls == 0


def test_fr_tkt_03_categories_and_priorities_match_spec_sets():
    assert set(PRIORITIES) == {"LOW", "MEDIUM", "HIGH", "URGENT"}
    # Spec spells this "How-to/Other"; the implementation constant is
    # "How-to / Other" (extra spacing). Same five categories -- treated as
    # a cosmetic spec/implementation wording difference, not a functional
    # mismatch, so the test asserts on the implementation's actual set.
    assert set(CATEGORIES) == {
        "Bug",
        "Feature Request",
        "Access",
        "Hardware",
        "How-to / Other",
    }


# ---------------------------------------------------------------------------
# AC-3 (FR-TKT-04/05): valid submission -> ticket number, status OPEN,
# requester_id recorded.
# ---------------------------------------------------------------------------


def test_fr_tkt_04_valid_submission_creates_open_ticket_with_unique_number(make_conn):
    ticket_row = _valid_ticket_row()
    conn = make_conn(fetchone_results=[ticket_row], lastrowid=42)

    result = create_ticket(
        conn,
        7,
        "Printer is on fire",
        "It's smoking and smells bad.",
        "Hardware",
        "HIGH",
    )

    insert_sql, insert_params = conn.cursor_obj.executed[0]
    assert "INSERT INTO tickets" in insert_sql
    assert "'OPEN'" in insert_sql  # status is hardcoded, never caller-supplied
    assert insert_params == (
        7,
        "Printer is on fire",
        "It's smoking and smells bad.",
        "Hardware",
        "HIGH",
    )

    update_sql, update_params = conn.cursor_obj.executed[1]
    assert "UPDATE tickets SET ticket_number" in update_sql
    assert update_params == ("TCK-000042", 42)

    assert conn.commit_calls == 1
    assert result == ticket_row
    assert result["status"] == "OPEN"


def test_fr_tkt_05_requester_id_recorded_as_creating_user(make_conn):
    ticket_row = _valid_ticket_row(id=9, ticket_number="TCK-000009", requester_id=123)
    conn = make_conn(fetchone_results=[ticket_row], lastrowid=9)

    result = create_ticket(
        conn, 123, "Need VPN access", "Please grant VPN access.", "Access", "MEDIUM"
    )

    _insert_sql, insert_params = conn.cursor_obj.executed[0]
    assert insert_params[0] == 123  # requester_id is the first bound INSERT param
    assert result["requester_id"] == 123


def test_fr_tkt_04_creation_writes_exactly_one_activity_row_with_created_action(
    make_conn,
):
    ticket_row = _valid_ticket_row()
    conn = make_conn(fetchone_results=[ticket_row], lastrowid=42)

    create_ticket(conn, 7, "Title", "Description", "Bug", "LOW")

    activity_inserts = [
        (sql, params)
        for sql, params in conn.cursor_obj.executed
        if "INSERT INTO ticket_activity" in sql
    ]
    assert len(activity_inserts) == 1
    activity_sql, activity_params = activity_inserts[0]
    assert "'CREATED'" in activity_sql
    assert activity_params == (42, 7, "OPEN")


# ---------------------------------------------------------------------------
# AC-4 (FR-STAT-05): ticket insert + activity insert are in the same
# transaction -- both writes happen before the single commit(), and a
# failure partway through leaves nothing committed.
# ---------------------------------------------------------------------------


def test_fr_tkt_04_ticket_and_activity_inserts_happen_before_commit(make_conn):
    ticket_row = _valid_ticket_row()
    conn = make_conn(fetchone_results=[ticket_row], lastrowid=42)

    order = []
    original_execute = conn.cursor_obj.execute
    original_commit = conn.commit

    def tracking_execute(sql, params=None):
        original_execute(sql, params)
        verb = sql.strip().split()[0].upper()
        order.append(("execute", verb, sql))

    def tracking_commit():
        original_commit()
        order.append(("commit", None, None))

    conn.cursor_obj.execute = tracking_execute
    conn.commit = tracking_commit

    create_ticket(conn, 7, "Title", "Description", "Bug", "LOW")

    commit_indexes = [i for i, event in enumerate(order) if event[0] == "commit"]
    assert commit_indexes == [len(order) - 1]  # exactly one commit, and it's last
    commit_index = commit_indexes[0]

    insert_indexes = [
        i
        for i, event in enumerate(order)
        if event[0] == "execute" and event[1] == "INSERT"
    ]
    assert len(insert_indexes) == 2  # ticket insert + activity insert
    assert all(i < commit_index for i in insert_indexes)


def test_fr_stat_05_activity_insert_failure_prevents_commit_no_partial_write(make_conn):
    # Call order inside create_ticket: 1) INSERT tickets, 2) UPDATE
    # ticket_number, 3) INSERT ticket_activity, 4) SELECT. Fail on the
    # activity insert (call 3) to simulate a mid-transaction failure.
    conn = make_conn(raise_on_execute={3: RuntimeError("db exploded")}, lastrowid=5)

    with pytest.raises(RuntimeError):
        create_ticket(conn, 7, "Title", "Description", "Bug", "LOW")

    executed_sql = [sql for sql, _params in conn.cursor_obj.executed]
    assert len(executed_sql) == 3  # failed before the trailing SELECT was ever issued
    assert any("INSERT INTO tickets" in sql for sql in executed_sql)
    assert any("INSERT INTO ticket_activity" in sql for sql in executed_sql)

    # The ticket insert was sent to the cursor but never committed -- with
    # autocommit off and no commit() reached, it cannot be left as a
    # partial write.
    assert conn.commit_calls == 0


# ---------------------------------------------------------------------------
# AC-5 (FR-TKT-05 / BR-05): new ticket is scoped to the creating user; a
# different user_id cannot retrieve it via get_ticket. Full ticket-list /
# dashboard visibility is not yet applicable (see module docstring).
# ---------------------------------------------------------------------------


def test_fr_tkt_05_creator_can_retrieve_created_ticket_via_get_ticket(make_conn):
    ticket_row = _valid_ticket_row(id=42, requester_id=7)
    # First fetchone() is create_ticket's trailing SELECT; second is
    # get_ticket's SELECT for the owning user.
    conn = make_conn(fetchone_results=[ticket_row, ticket_row], lastrowid=42)

    created = create_ticket(conn, 7, "Title", "Description", "Bug", "LOW")
    fetched = get_ticket(conn, created["id"], 7)

    assert fetched == ticket_row
    _select_sql, select_params = conn.cursor_obj.executed[-1]
    assert select_params == (42, 7, 7)


def test_fr_tkt_05_other_user_cannot_retrieve_ticket_via_get_ticket(make_conn):
    ticket_row = _valid_ticket_row(id=42, requester_id=7)
    # get_ticket's SELECT for a non-owning user_id would be filtered out by
    # the real WHERE clause, so the canned result for that call is None.
    conn = make_conn(fetchone_results=[ticket_row, None], lastrowid=42)

    created = create_ticket(conn, 7, "Title", "Description", "Bug", "LOW")
    fetched = get_ticket(conn, created["id"], 999)

    assert fetched is None


def test_fr_tkt_05_get_ticket_query_scopes_to_requester_or_assignee(make_conn):
    conn = make_conn(fetchone_results=[None])

    get_ticket(conn, 55, 3)

    sql, params = conn.cursor_obj.executed[0]
    assert "requester_id = ? OR assignee_id = ?" in sql
    assert params == (55, 3, 3)


# ---------------------------------------------------------------------------
# AC-6: ticket numbers are deterministic-from-id and collision-free by
# construction at the unit level. The actual "never reused/duplicated under
# concurrency" guarantee lives in the UNIQUE constraint in common/db.py and
# is not (and cannot be) proven by these single-threaded fake-cursor tests
# -- see module docstring for this gap.
# ---------------------------------------------------------------------------


def test_fr_tkt_06_ticket_number_format_is_deterministic_from_id(make_conn):
    ticket_row = _valid_ticket_row(id=7, ticket_number="TCK-000007")
    conn = make_conn(fetchone_results=[ticket_row], lastrowid=7)

    create_ticket(conn, 1, "Title", "Description", "Bug", "LOW")

    _update_sql, update_params = conn.cursor_obj.executed[1]
    assert update_params[0] == "TCK-000007"


def test_fr_tkt_06_different_lastrowids_produce_different_ticket_numbers(make_conn):
    row1 = _valid_ticket_row(id=1, ticket_number="TCK-000001")
    conn1 = make_conn(fetchone_results=[row1], lastrowid=1)
    create_ticket(conn1, 1, "Title", "Description", "Bug", "LOW")
    number1 = conn1.cursor_obj.executed[1][1][0]

    row2 = _valid_ticket_row(id=2, ticket_number="TCK-000002")
    conn2 = make_conn(fetchone_results=[row2], lastrowid=2)
    create_ticket(conn2, 1, "Title", "Description", "Bug", "LOW")
    number2 = conn2.cursor_obj.executed[1][1][0]

    assert number1 == "TCK-000001"
    assert number2 == "TCK-000002"
    assert number1 != number2
