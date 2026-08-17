"""Tests for features/tickets/service.py's status-transition, field-update,
and activity-history logic against specs/status-workflow.md acceptance
criteria (AC-1..AC-6).

All tests use the fake, in-memory PyMySQL-shaped connection/cursor from
tests/conftest.py (FakeCursor/FakeConnection via the `make_conn` fixture) --
no real MySQL server is required or assumed, mirroring the tickets/auth
suites' approach.

Placed in a separate file from test_tickets_service.py (which covers
specs/tickets.md) to keep this spec's acceptance-criteria coverage
traceable on its own, per the assignment.

Context: a prior verification of the seed-data feature found that
`transition_status` had no BR-05 ownership check and zero direct test
coverage -- it was only ever exercised indirectly, through mocks, in
test_seed_data_service.py. This suite gives `transition_status`,
`update_ticket_field`, and `get_ticket_activity` their first real,
direct coverage against a fake cursor/connection.
"""

import pytest

from features.tickets.service import (
    ALLOWED_TRANSITIONS,
    TicketError,
    TicketPermissionError,
    TransitionError,
    get_ticket_activity,
    transition_status,
    update_ticket_field,
)


def _ticket_row(**overrides):
    row = {"status": "OPEN", "requester_id": 7, "assignee_id": None}
    row.update(overrides)
    return row


def _field_row(field, value, **overrides):
    row = {field: value, "requester_id": 7, "assignee_id": None}
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# AC-1 (FR-STAT-01/BR-02): every legal transition succeeds and writes exactly
# one activity row with the correct old/new status values.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current_status,new_status",
    [
        ("OPEN", "IN_PROGRESS"),
        ("IN_PROGRESS", "RESOLVED"),
        ("RESOLVED", "CLOSED"),
        ("RESOLVED", "IN_PROGRESS"),
    ],
)
def test_fr_stat_01_legal_transition_succeeds_and_writes_one_activity_row(
    make_conn, current_status, new_status
):
    row = _ticket_row(status=current_status)
    conn = make_conn(fetchone_results=[row])

    transition_status(conn, ticket_id=42, actor_id=7, new_status=new_status)

    executed = conn.cursor_obj.executed
    update_calls = [
        (sql, params)
        for sql, params in executed
        if sql.strip().upper().startswith("UPDATE")
    ]
    activity_calls = [
        (sql, params)
        for sql, params in executed
        if "INSERT INTO ticket_activity" in sql
    ]

    assert len(update_calls) == 1
    update_sql, update_params = update_calls[0]
    assert "UPDATE tickets SET status" in update_sql
    assert update_params == (new_status, 42)

    assert len(activity_calls) == 1
    activity_sql, activity_params = activity_calls[0]
    assert "'STATUS_CHANGE'" in activity_sql
    assert activity_params == (42, 7, current_status, new_status)

    assert conn.commit_calls == 1
    assert conn.rollback_calls == 0


def test_fr_stat_01_allowed_transitions_map_matches_br_02_br_03():
    # BR-02/BR-03: exactly these transitions are legal; CLOSED is terminal.
    assert ALLOWED_TRANSITIONS == {
        "OPEN": {"IN_PROGRESS"},
        "IN_PROGRESS": {"RESOLVED"},
        "RESOLVED": {"CLOSED", "IN_PROGRESS"},
        "CLOSED": set(),
    }


# ---------------------------------------------------------------------------
# AC-2 (FR-STAT-02/BR-02/BR-03): illegal transitions are rejected, never
# persisted -- no UPDATE/INSERT is attempted and commit() is never called.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current_status,illegal_new_status",
    [
        ("CLOSED", "OPEN"),  # BR-03: CLOSED is terminal
        ("CLOSED", "IN_PROGRESS"),
        ("CLOSED", "RESOLVED"),
        ("OPEN", "RESOLVED"),  # skips IN_PROGRESS
        ("OPEN", "CLOSED"),
        ("IN_PROGRESS", "OPEN"),
        ("IN_PROGRESS", "CLOSED"),
    ],
)
def test_fr_stat_02_illegal_transition_rejected_no_write(
    make_conn, current_status, illegal_new_status
):
    row = _ticket_row(status=current_status)
    conn = make_conn(fetchone_results=[row])

    with pytest.raises(TransitionError) as exc_info:
        transition_status(conn, ticket_id=42, actor_id=7, new_status=illegal_new_status)

    assert current_status in str(exc_info.value)
    assert illegal_new_status in str(exc_info.value)

    executed = conn.cursor_obj.executed
    # Only the initial scoping SELECT should have been issued -- no write.
    assert len(executed) == 1
    assert executed[0][0].strip().upper().startswith("SELECT")
    assert not any(sql.strip().upper().startswith("UPDATE") for sql, _ in executed)
    assert not any("INSERT" in sql for sql, _ in executed)

    assert conn.commit_calls == 0
    assert conn.rollback_calls == 0  # rejected before entering the write's try/except


# ---------------------------------------------------------------------------
# AC-3 (FR-STAT-03/04): priority/category update writes exactly one
# FIELD_UPDATE activity row with correct old/new values and actor.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,old_value,new_value",
    [
        ("priority", "LOW", "HIGH"),
        ("category", "Bug", "Access"),
    ],
)
def test_fr_stat_03_field_update_writes_one_field_update_activity_row(
    make_conn, field, old_value, new_value
):
    row = _field_row(field, old_value)
    conn = make_conn(fetchone_results=[row])

    update_ticket_field(
        conn, ticket_id=42, actor_id=7, field=field, new_value=new_value
    )

    executed = conn.cursor_obj.executed
    update_calls = [
        (sql, params)
        for sql, params in executed
        if sql.strip().upper().startswith("UPDATE")
    ]
    activity_calls = [
        (sql, params)
        for sql, params in executed
        if "INSERT INTO ticket_activity" in sql
    ]

    assert len(update_calls) == 1
    update_sql, update_params = update_calls[0]
    assert f"UPDATE tickets SET {field}" in update_sql
    assert update_params == (new_value, 42)

    assert len(activity_calls) == 1
    activity_sql, activity_params = activity_calls[0]
    assert "'FIELD_UPDATE'" in activity_sql
    assert activity_params == (42, 7, field, old_value, new_value)

    assert conn.commit_calls == 1
    assert conn.rollback_calls == 0


@pytest.mark.parametrize(
    "field,same_value",
    [
        ("priority", "LOW"),
        ("category", "Bug"),
    ],
)
def test_fr_stat_03_no_op_field_update_writes_nothing(make_conn, field, same_value):
    # BR-04 covers actual changes, not resubmission of the same value --
    # documented intentional no-write no-op path.
    row = _field_row(field, same_value)
    conn = make_conn(fetchone_results=[row])

    update_ticket_field(
        conn, ticket_id=42, actor_id=7, field=field, new_value=same_value
    )

    executed = conn.cursor_obj.executed
    assert len(executed) == 1  # only the initial scoping SELECT
    assert not any(sql.strip().upper().startswith("UPDATE") for sql, _ in executed)
    assert not any("INSERT" in sql for sql, _ in executed)
    assert conn.commit_calls == 0
    assert conn.rollback_calls == 0


def test_fr_stat_03_invalid_field_name_rejected_before_any_sql_uses_it(make_conn):
    # Directly targets the dynamic-SQL-construction concern: an
    # unallowlisted field name (e.g. a column that doesn't exist on the
    # fixed-set allowlist, including a sensitive one) must be rejected by
    # the FIELD_VALIDATORS check before *any* execute() call is made -- the
    # f-string SQL referencing that field name must never be built/executed.
    conn = make_conn(fetchone_results=[])

    with pytest.raises(TicketError) as exc_info:
        update_ticket_field(
            conn, ticket_id=42, actor_id=7, field="password_hash", new_value="whatever"
        )

    assert "password_hash" in str(exc_info.value)
    assert conn.cursor_obj.executed == []  # no SQL built or executed at all
    assert conn.commit_calls == 0
    assert conn.rollback_calls == 0


def test_fr_stat_03_invalid_field_name_status_also_rejected(make_conn):
    # `status` must go through transition_status, not update_ticket_field --
    # confirm it isn't accidentally allowlisted in FIELD_VALIDATORS.
    conn = make_conn(fetchone_results=[])

    with pytest.raises(TicketError):
        update_ticket_field(
            conn, ticket_id=42, actor_id=7, field="status", new_value="OPEN"
        )

    assert conn.cursor_obj.executed == []


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("priority", "CRITICAL"),
        ("category", "Not-A-Category"),
    ],
)
def test_fr_stat_03_invalid_value_for_valid_field_rejected_no_sql(
    make_conn, field, invalid_value
):
    conn = make_conn(fetchone_results=[])

    with pytest.raises(TicketError):
        update_ticket_field(
            conn, ticket_id=42, actor_id=7, field=field, new_value=invalid_value
        )

    # Value validation also happens before the field is ever fetched/used
    # in SQL.
    assert conn.cursor_obj.executed == []


# ---------------------------------------------------------------------------
# AC-4 (FR-STAT-05/NFR-02): a failure partway through either write path rolls
# back and never commits -- proving the rollback actually fires, not just
# that the code has a try/except.
# ---------------------------------------------------------------------------


def test_fr_stat_05_transition_status_activity_insert_failure_rolls_back(make_conn):
    row = _ticket_row(status="OPEN")
    # Call order: 1) SELECT status/requester/assignee, 2) UPDATE status,
    # 3) INSERT ticket_activity. Fail on the activity insert.
    conn = make_conn(
        fetchone_results=[row], raise_on_execute={3: RuntimeError("db exploded")}
    )

    with pytest.raises(RuntimeError):
        transition_status(conn, ticket_id=42, actor_id=7, new_status="IN_PROGRESS")

    executed = conn.cursor_obj.executed
    assert len(executed) == 3  # SELECT, UPDATE, failed INSERT -- nothing after
    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0


def test_fr_stat_05_transition_status_update_failure_rolls_back(make_conn):
    row = _ticket_row(status="OPEN")
    # Fail on the very first write (the status UPDATE, call 2).
    conn = make_conn(
        fetchone_results=[row], raise_on_execute={2: RuntimeError("db exploded")}
    )

    with pytest.raises(RuntimeError):
        transition_status(conn, ticket_id=42, actor_id=7, new_status="IN_PROGRESS")

    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0
    # The activity insert must never have been reached.
    assert not any(
        "INSERT INTO ticket_activity" in sql for sql, _ in conn.cursor_obj.executed
    )


def test_fr_stat_05_update_ticket_field_activity_insert_failure_rolls_back(make_conn):
    row = _field_row("priority", "LOW")
    # Call order: 1) SELECT field/requester/assignee, 2) UPDATE field,
    # 3) INSERT ticket_activity. Fail on the activity insert.
    conn = make_conn(
        fetchone_results=[row], raise_on_execute={3: RuntimeError("db exploded")}
    )

    with pytest.raises(RuntimeError):
        update_ticket_field(
            conn, ticket_id=42, actor_id=7, field="priority", new_value="HIGH"
        )

    executed = conn.cursor_obj.executed
    assert len(executed) == 3
    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0


def test_fr_stat_05_update_ticket_field_update_failure_rolls_back(make_conn):
    row = _field_row("category", "Bug")
    conn = make_conn(
        fetchone_results=[row], raise_on_execute={2: RuntimeError("db exploded")}
    )

    with pytest.raises(RuntimeError):
        update_ticket_field(
            conn, ticket_id=42, actor_id=7, field="category", new_value="Access"
        )

    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0
    assert not any(
        "INSERT INTO ticket_activity" in sql for sql, _ in conn.cursor_obj.executed
    )


# ---------------------------------------------------------------------------
# AC-5 (FR-STAT-06): activity history is returned newest-first, via the
# actual ORDER BY clause, and empty for a ticket that doesn't exist / isn't
# the user's.
# ---------------------------------------------------------------------------


def test_fr_stat_06_activity_query_orders_newest_first(make_conn):
    conn = make_conn(fetchone_results=[{"id": 42}], fetchall_results=[[]])

    get_ticket_activity(conn, ticket_id=42, user_id=7)

    activity_select_sql = conn.cursor_obj.executed[-1][0]
    assert "ORDER BY ta.created_at DESC, ta.id DESC" in activity_select_sql


def test_fr_stat_06_activity_rows_returned_newest_first_by_canned_order(make_conn):
    # A canned multi-row result, already in "created_at DESC, id DESC"
    # order as the real DB would return it -- confirms get_ticket_activity
    # passes rows through unreordered/unfiltered.
    rows = [
        {"id": 3, "action": "STATUS_CHANGE", "created_at": "2026-08-17 03:00:00"},
        {"id": 2, "action": "FIELD_UPDATE", "created_at": "2026-08-17 02:00:00"},
        {"id": 1, "action": "CREATED", "created_at": "2026-08-17 01:00:00"},
    ]
    conn = make_conn(fetchone_results=[{"id": 42}], fetchall_results=[rows])

    result = get_ticket_activity(conn, ticket_id=42, user_id=7)

    assert [r["id"] for r in result] == [3, 2, 1]


def test_fr_stat_06_activity_empty_for_nonexistent_or_non_owned_ticket(make_conn):
    # The scoping SELECT returns None -- ticket doesn't exist or isn't the
    # user's -- so get_ticket_activity must short-circuit to [] without
    # ever issuing the activity query itself.
    conn = make_conn(fetchone_results=[None])

    result = get_ticket_activity(conn, ticket_id=42, user_id=999)

    assert result == []
    assert len(conn.cursor_obj.executed) == 1  # only the scoping SELECT ran


# ---------------------------------------------------------------------------
# AC-6 (BR-05): a user who is neither requester nor assignee cannot modify a
# ticket via transition_status or update_ticket_field -- rejected before any
# write; the assignee (not the requester) is correctly allowed through.
# ---------------------------------------------------------------------------


def test_fr_stat_06_transition_status_rejects_non_owner_before_any_write(make_conn):
    row = _ticket_row(status="OPEN", requester_id=7, assignee_id=8)
    conn = make_conn(fetchone_results=[row])

    with pytest.raises(TicketPermissionError):
        transition_status(conn, ticket_id=42, actor_id=999, new_status="IN_PROGRESS")

    executed = conn.cursor_obj.executed
    assert len(executed) == 1  # only the initial scoping SELECT
    assert not any(sql.strip().upper().startswith("UPDATE") for sql, _ in executed)
    assert not any("INSERT" in sql for sql, _ in executed)
    assert conn.commit_calls == 0
    assert conn.rollback_calls == 0


def test_fr_stat_06_update_ticket_field_rejects_non_owner_before_any_write(make_conn):
    row = _field_row("priority", "LOW", requester_id=7, assignee_id=8)
    conn = make_conn(fetchone_results=[row])

    with pytest.raises(TicketPermissionError):
        update_ticket_field(
            conn, ticket_id=42, actor_id=999, field="priority", new_value="HIGH"
        )

    executed = conn.cursor_obj.executed
    assert len(executed) == 1
    assert not any(sql.strip().upper().startswith("UPDATE") for sql, _ in executed)
    assert not any("INSERT" in sql for sql, _ in executed)
    assert conn.commit_calls == 0
    assert conn.rollback_calls == 0


def test_fr_stat_06_transition_status_allows_assignee_who_is_not_requester(make_conn):
    row = _ticket_row(status="OPEN", requester_id=7, assignee_id=8)
    conn = make_conn(fetchone_results=[row])

    # actor_id=8 is the assignee, not the requester -- must be allowed.
    transition_status(conn, ticket_id=42, actor_id=8, new_status="IN_PROGRESS")

    assert conn.commit_calls == 1
    assert conn.rollback_calls == 0
    activity_params = next(
        params
        for sql, params in conn.cursor_obj.executed
        if "INSERT INTO ticket_activity" in sql
    )
    assert activity_params == (42, 8, "OPEN", "IN_PROGRESS")


def test_fr_stat_06_update_ticket_field_allows_assignee_who_is_not_requester(make_conn):
    row = _field_row("category", "Bug", requester_id=7, assignee_id=8)
    conn = make_conn(fetchone_results=[row])

    update_ticket_field(
        conn, ticket_id=42, actor_id=8, field="category", new_value="Access"
    )

    assert conn.commit_calls == 1
    assert conn.rollback_calls == 0
    activity_params = next(
        params
        for sql, params in conn.cursor_obj.executed
        if "INSERT INTO ticket_activity" in sql
    )
    assert activity_params == (42, 8, "category", "Bug", "Access")


def test_fr_stat_06_transition_status_nonexistent_ticket_raises_ticket_error(make_conn):
    conn = make_conn(fetchone_results=[None])

    with pytest.raises(TicketError):
        transition_status(conn, ticket_id=999, actor_id=7, new_status="IN_PROGRESS")

    assert conn.commit_calls == 0
    assert conn.rollback_calls == 0
