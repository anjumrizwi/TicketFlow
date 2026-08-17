"""Tests for features/tickets/service.py's `list_tickets` against
specs/list-search.md acceptance criteria (AC-1..AC-6).

All tests use the fake, in-memory PyMySQL-shaped connection/cursor from
tests/conftest.py (FakeCursor/FakeConnection via the `make_conn` fixture) --
no real MySQL server is required or assumed, mirroring the
test_status_workflow_service.py suite's approach.

Every test asserts on the actual SQL string and bound params sent to the
fake cursor, not just the returned rows, since the acceptance criteria are
about how the WHERE clause is composed (AND vs OR, which clauses are
present) rather than about any particular dataset.
"""

import pytest

from features.tickets.service import list_tickets


def _executed_select(conn):
    """The single SELECT list_tickets issues -- (sql, params)."""
    executed = conn.cursor_obj.executed
    assert len(executed) == 1
    return executed[0]


# ---------------------------------------------------------------------------
# AC-1 (FR-LIST-01/05): no filters -> full user-scoped list, newest first.
# ---------------------------------------------------------------------------


def test_fr_list_01_no_filters_returns_full_user_scoped_list_newest_first(make_conn):
    conn = make_conn(fetchall_results=[[]])

    list_tickets(conn, user_id=7)

    sql, params = _executed_select(conn)
    assert "WHERE (requester_id = %s OR assignee_id = %s)" in sql
    assert "ORDER BY created_at DESC, id DESC" in sql
    assert list(params) == [7, 7]
    # No other AND-ed clauses should be present -- the WHERE clause is
    # exactly the scoping clause, nothing more.
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert "AND" not in where_clause


def test_fr_list_01_returned_rows_passed_through_unfiltered(make_conn):
    rows = [{"id": 2, "title": "b"}, {"id": 1, "title": "a"}]
    conn = make_conn(fetchall_results=[rows])

    result = list_tickets(conn, user_id=7)

    assert result == rows


# ---------------------------------------------------------------------------
# AC-2 (FR-LIST-02): applying exactly one filter adds exactly one clause,
# ANDed with the scoping clause.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwarg,value,expected_clause,expected_extra_params",
    [
        ("status", "OPEN", "status = %s", ["OPEN"]),
        ("priority", "HIGH", "priority = %s", ["HIGH"]),
        ("category", "Bug", "category = %s", ["Bug"]),
        ("date_from", "2026-01-01", "DATE(created_at) >= %s", ["2026-01-01"]),
        ("date_to", "2026-12-31", "DATE(created_at) <= %s", ["2026-12-31"]),
    ],
)
def test_fr_list_02_single_filter_adds_exactly_one_anded_clause(
    make_conn, kwarg, value, expected_clause, expected_extra_params
):
    conn = make_conn(fetchall_results=[[]])

    list_tickets(conn, user_id=7, **{kwarg: value})

    sql, params = _executed_select(conn)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]

    assert "(requester_id = %s OR assignee_id = %s)" in where_clause
    assert expected_clause in where_clause
    # Exactly two clauses, joined by exactly one " AND ".
    assert where_clause.count(" AND ") == 1
    assert list(params) == [7, 7] + expected_extra_params


# ---------------------------------------------------------------------------
# AC-3 (FR-LIST-02/04): multiple filters together AND (intersect), never OR.
# ---------------------------------------------------------------------------


def test_fr_list_03_multiple_filters_and_together_not_or(make_conn):
    conn = make_conn(fetchall_results=[[]])

    list_tickets(
        conn,
        user_id=7,
        status="OPEN",
        priority="HIGH",
        category="Bug",
        date_from="2026-01-01",
        date_to="2026-12-31",
    )

    sql, params = _executed_select(conn)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]

    # Five filter clauses ANDed with the scoping clause = 5 " AND " joins.
    assert where_clause.count(" AND ") == 5

    # The only OR present must be the one inside the scoping clause -- no
    # filter clause introduces an OR (which would turn intersection into
    # union).
    assert where_clause.count(" OR ") == 1
    assert "(requester_id = %s OR assignee_id = %s)" in where_clause

    for clause in (
        "status = %s",
        "priority = %s",
        "category = %s",
        "DATE(created_at) >= %s",
        "DATE(created_at) <= %s",
    ):
        assert clause in where_clause

    assert list(params) == [
        7,
        7,
        "OPEN",
        "HIGH",
        "Bug",
        "2026-01-01",
        "2026-12-31",
    ]


def test_fr_list_03_two_filters_produce_intersection_not_union(make_conn):
    # A narrower, more targeted pairing -- status + priority -- confirms the
    # AND-composition even with just two active filters.
    conn = make_conn(fetchall_results=[[]])

    list_tickets(conn, user_id=7, status="OPEN", priority="URGENT")

    sql, params = _executed_select(conn)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]

    assert where_clause.count(" AND ") == 2  # scope AND status AND priority
    assert where_clause.count(" OR ") == 1  # only inside the scoping clause
    assert list(params) == [7, 7, "OPEN", "URGENT"]


# ---------------------------------------------------------------------------
# AC-4 (FR-LIST-03/04): search adds a title/description LIKE clause, ANDed
# with (composing with, not replacing) any other active filters.
# ---------------------------------------------------------------------------


def test_fr_list_04_search_alone_adds_like_clause_with_wrapped_pattern(make_conn):
    conn = make_conn(fetchall_results=[[]])

    list_tickets(conn, user_id=7, search="printer")

    sql, params = _executed_select(conn)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]

    assert "(title LIKE %s OR description LIKE %s)" in where_clause
    assert where_clause.count(" AND ") == 1  # scope AND search
    # The search clause's internal OR plus the scoping clause's internal OR.
    assert where_clause.count(" OR ") == 2
    assert list(params) == [7, 7, "%printer%", "%printer%"]


def test_fr_list_04_search_composes_with_an_active_status_filter(make_conn):
    # Search must narrow the already-filtered set, not replace the filter.
    conn = make_conn(fetchall_results=[[]])

    list_tickets(conn, user_id=7, status="OPEN", search="printer")

    sql, params = _executed_select(conn)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]

    assert "(requester_id = %s OR assignee_id = %s)" in where_clause
    assert "status = %s" in where_clause
    assert "(title LIKE %s OR description LIKE %s)" in where_clause
    assert where_clause.count(" AND ") == 2  # scope AND status AND search
    assert list(params) == [7, 7, "OPEN", "%printer%", "%printer%"]


# ---------------------------------------------------------------------------
# AC-5 (FR-LIST-05): clearing filters/search is not a special code path --
# it produces exactly the same query as the no-filter case (AC-1).
# ---------------------------------------------------------------------------


def test_fr_list_05_all_filters_none_or_falsy_matches_no_filter_query(make_conn):
    conn_baseline = make_conn(fetchall_results=[[]])
    conn_cleared = make_conn(fetchall_results=[[]])

    list_tickets(conn_baseline, user_id=7)
    list_tickets(
        conn_cleared,
        user_id=7,
        status=None,
        priority=None,
        category=None,
        date_from=None,
        date_to=None,
        search=None,
    )

    baseline_sql, baseline_params = _executed_select(conn_baseline)
    cleared_sql, cleared_params = _executed_select(conn_cleared)

    assert cleared_sql == baseline_sql
    assert list(cleared_params) == list(baseline_params)


def test_fr_list_05_falsy_search_empty_string_matches_none_no_search_clause(make_conn):
    # Subtle branch: `if search:` (truthiness), not `is not None`, unlike
    # every other filter -- an empty string must behave exactly like None.
    conn_none = make_conn(fetchall_results=[[]])
    conn_empty = make_conn(fetchall_results=[[]])

    list_tickets(conn_none, user_id=7, search=None)
    list_tickets(conn_empty, user_id=7, search="")

    none_sql, none_params = _executed_select(conn_none)
    empty_sql, empty_params = _executed_select(conn_empty)

    assert empty_sql == none_sql
    assert list(empty_params) == list(none_params)
    assert "LIKE" not in empty_sql


# ---------------------------------------------------------------------------
# AC-6 (FR-LIST-05/BR-05): the requester/assignee scoping clause is always
# the first clause, unconditionally present, and always bound to user_id
# (never influenced by any filter argument), no matter what else is passed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"status": "CLOSED"},
        {"priority": "URGENT"},
        {"category": "Hardware"},
        {"date_from": "2020-01-01", "date_to": "2099-12-31"},
        {"search": "OR 1=1"},
        {
            "status": "OPEN",
            "priority": "LOW",
            "category": "Bug",
            "date_from": "2020-01-01",
            "date_to": "2099-12-31",
            "search": "anything",
        },
    ],
)
def test_fr_list_06_scoping_clause_always_first_and_bound_to_user_id(make_conn, kwargs):
    conn = make_conn(fetchall_results=[[]])

    list_tickets(conn, user_id=7, **kwargs)

    sql, params = _executed_select(conn)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0].strip()

    # The scoping clause is unconditionally the very first clause.
    assert where_clause.startswith("(requester_id = %s OR assignee_id = %s)")
    # Its two bound values are always user_id, first two positional params,
    # never overridden or shifted by any filter argument.
    assert list(params)[:2] == [7, 7]


def test_fr_list_06_scoping_clause_uses_user_id_not_any_filter_value(make_conn):
    # Even a crafted filter value can't smuggle itself into the scoping
    # clause's bound parameters -- they must remain exactly [user_id, user_id].
    conn = make_conn(fetchall_results=[[]])

    list_tickets(
        conn,
        user_id=7,
        status="999 OR 1=1",
        priority="999",
        category="999",
        search="999",
    )

    _, params = _executed_select(conn)
    assert list(params)[:2] == [7, 7]
    assert 999 not in list(params)[:2]
