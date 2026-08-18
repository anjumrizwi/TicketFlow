"""Tests for features/seed_data/service.py against specs/seed-data.md
acceptance criteria (AC-1..AC-5).

All tests use the fake, in-memory pyodbc-shaped connection/cursor from
tests/conftest.py (FakeCursor/FakeConnection via the `make_conn` fixture) --
no real SQL Server instance is required or assumed, mirroring the
auth/tickets suites' approach.

Two levels of fake-out are used, deliberately:

- Orchestration-level tests (AC-1, AC-2) monkeypatch the already-tested
  collaborators `create_ticket`/`transition_status` (and, for AC-2's
  isolated per-target-status check, `_create_demo_ticket`'s `random.choice`
  calls) rather than re-deriving ticket-creation/status-transition
  correctness here -- that's `test_tickets_service.py`'s job. These tests
  instead prove seed_demo_data's own contract: it creates the right number
  of users/tickets and walks each ticket through the *correct* legal
  status-path sequence.
- Data-shape and guardrail tests (AC-3, AC-4, AC-5, negative counts, the
  num_tickets == 0 edge case) exercise the real `_clear_seeded_data`,
  `_create_demo_user`, and `_assert_demo_database` against a fake cursor,
  since those are exactly the DB-facing behaviors under test.
"""

from collections import defaultdict

import pytest

import features.seed_data.service as seed_service
from features.seed_data.service import (
    STATUS_PATHS,
    SeedError,
    SeedGuardError,
    _assert_demo_database,
    _clear_seeded_data,
    _create_demo_ticket,
    _create_demo_user,
    seed_demo_data,
)
from features.tickets.service import ALLOWED_TRANSITIONS

# ---------------------------------------------------------------------------
# AC-1 (FR-SEED-01): seed_demo_data(conn, N, M) creates exactly N demo users,
# each with 1..M tickets.
# ---------------------------------------------------------------------------


def test_fr_seed_01_creates_exactly_n_users_with_ticket_counts_in_range(
    monkeypatch, make_conn
):
    ticket_calls_by_user = defaultdict(int)

    def fake_create_demo_ticket(conn, user_id):
        ticket_calls_by_user[user_id] += 1
        return "OPEN"

    monkeypatch.setattr(seed_service, "_create_demo_ticket", fake_create_demo_ticket)

    # No pre-existing demo users to clear (first fetchall(): empty list).
    conn = make_conn(fetchall_results=[[]], auto_increment_lastrowid=True)

    num_users, num_tickets = 5, 4
    summary = seed_demo_data(conn, num_users, num_tickets)

    insert_user_calls = [
        (sql, params)
        for sql, params in conn.cursor_obj.executed
        if "INSERT INTO users" in sql
    ]
    assert len(insert_user_calls) == num_users
    assert summary["users"] == num_users

    # Every user is distinct (thanks to auto-incrementing lastrowid) and
    # each got between 1 and num_tickets tickets.
    assert len(ticket_calls_by_user) == num_users
    for count in ticket_calls_by_user.values():
        assert 1 <= count <= num_tickets


def test_fr_seed_01_zero_users_creates_nothing(monkeypatch, make_conn):
    monkeypatch.setattr(
        seed_service, "_create_demo_ticket", lambda conn, user_id: pytest.fail(
            "no tickets should be created when num_users == 0"
        )
    )
    conn = make_conn(fetchall_results=[[]])

    summary = seed_demo_data(conn, 0, 5)

    assert summary["users"] == 0
    assert sum(summary["tickets_by_status"].values()) == 0
    insert_user_calls = [
        sql for sql, _params in conn.cursor_obj.executed if "INSERT INTO users" in sql
    ]
    assert insert_user_calls == []


# ---------------------------------------------------------------------------
# num_tickets == 0 edge case: each user ends up with 0 tickets, not 1
# (guards against an off-by-one in random.randint(1, num_tickets)).
# ---------------------------------------------------------------------------


def test_fr_seed_01_num_tickets_zero_gives_every_user_zero_tickets(
    monkeypatch, make_conn
):
    monkeypatch.setattr(
        seed_service,
        "_create_demo_ticket",
        lambda conn, user_id: pytest.fail(
            "_create_demo_ticket must never be called when num_tickets == 0"
        ),
    )
    conn = make_conn(fetchall_results=[[]], auto_increment_lastrowid=True)

    summary = seed_demo_data(conn, 3, 0)

    assert summary["users"] == 3
    assert sum(summary["tickets_by_status"].values()) == 0


# ---------------------------------------------------------------------------
# Negative-count guard: SeedError for negative num_users/num_tickets, raised
# before any DB access.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("num_users,num_tickets", [(-1, 5), (5, -1), (-1, -1)])
def test_fr_seed_negative_counts_rejected_before_any_db_access(
    make_conn, num_users, num_tickets
):
    conn = make_conn()

    with pytest.raises(SeedError):
        seed_demo_data(conn, num_users, num_tickets)

    assert conn.cursor_obj.executed == []
    assert conn.commit_calls == 0


# ---------------------------------------------------------------------------
# AC-2 (FR-SEED-02 / BR-02): every seeded ticket's status was reached only
# via the legal STATUS_PATHS chain, with one transition_status call per
# step -- never a single "created" row for a non-OPEN ticket.
# ---------------------------------------------------------------------------


def _patch_random_choice_for_target_status(monkeypatch, target_status):
    """Make every `random.choice` call inside seed_data.service deterministic:
    the STATUS_PATHS selection call returns `target_status`; any other
    `random.choice` call (category/priority/title) returns the first option,
    which is irrelevant to this test."""

    status_options = list(STATUS_PATHS)

    def fake_choice(seq):
        seq_list = list(seq)
        if seq_list == status_options:
            return target_status
        return seq_list[0]

    monkeypatch.setattr(seed_service.random, "choice", fake_choice)


def test_fr_seed_02_status_paths_constant_encodes_only_br02_legal_steps():
    """Independent, non-tautological check: walk STATUS_PATHS[target] from
    OPEN using the *real* BR-02 transition table (`ALLOWED_TRANSITIONS` from
    features/tickets/service.py, already tested in test_tickets_service.py)
    and confirm every single step is legal. Without this, the other AC-2
    tests below only prove seed_data calls transition_status in whatever
    order STATUS_PATHS says -- they can't catch STATUS_PATHS itself being
    wrong (e.g. skipping IN_PROGRESS on the way to RESOLVED)."""
    for target_status, path in STATUS_PATHS.items():
        current = "OPEN"
        for step in path:
            assert step in ALLOWED_TRANSITIONS.get(current, set()), (
                f"STATUS_PATHS[{target_status!r}] takes an illegal "
                f"{current!r} -> {step!r} step per BR-02."
            )
            current = step
        assert current == target_status


@pytest.mark.parametrize("target_status", list(STATUS_PATHS))
def test_fr_seed_02_ticket_walks_exact_legal_status_path(
    monkeypatch, make_conn, target_status
):
    _patch_random_choice_for_target_status(monkeypatch, target_status)

    fake_ticket = {"id": 77, "status": "OPEN"}
    monkeypatch.setattr(
        seed_service, "create_ticket", lambda *a, **kw: dict(fake_ticket)
    )

    transition_calls = []
    monkeypatch.setattr(
        seed_service,
        "transition_status",
        lambda conn, ticket_id, actor_id, new_status: transition_calls.append(
            (ticket_id, new_status)
        ),
    )

    conn = make_conn()
    result_status = _create_demo_ticket(conn, user_id=1)

    assert result_status == target_status

    expected_path = STATUS_PATHS[target_status]
    assert [status for _tid, status in transition_calls] == expected_path
    # Every transition call operates on the ticket that was actually created.
    assert all(tid == 77 for tid, _status in transition_calls)
    # A ticket landing in RESOLVED must have gone through exactly
    # CREATED + IN_PROGRESS + RESOLVED (3 activity-writing calls total, not
    # just a single "created" row) -- and never more/fewer than the legal
    # chain requires for any target.
    assert len(transition_calls) == len(expected_path)


def test_fr_seed_02_open_ticket_never_calls_transition_status(monkeypatch, make_conn):
    _patch_random_choice_for_target_status(monkeypatch, "OPEN")
    monkeypatch.setattr(
        seed_service, "create_ticket", lambda *a, **kw: {"id": 1, "status": "OPEN"}
    )

    def fail_transition(*args, **kwargs):
        pytest.fail("transition_status must not be called for an OPEN target")

    monkeypatch.setattr(seed_service, "transition_status", fail_transition)

    conn = make_conn()
    result_status = _create_demo_ticket(conn, user_id=1)

    assert result_status == "OPEN"


def test_fr_seed_02_full_run_every_ticket_transition_sequence_is_legal(
    monkeypatch, make_conn
):
    """Integration-flavored version of AC-2: run the full seed_demo_data
    orchestration (real _create_demo_ticket, mocked create_ticket/
    transition_status) and confirm, per ticket, that the recorded
    transition_status sequence exactly matches STATUS_PATHS for whichever
    status was reached. Path lengths (0, 1, 2, 3) are distinct per target
    status, so the sequence length alone identifies which legal chain must
    have been followed -- any deviation (skipped step, wrong order, extra
    step) fails this assertion."""

    ticket_id_counter = iter(range(1, 100000))

    def fake_create_ticket(conn, requester_id, title, description, category, priority):
        return {"id": next(ticket_id_counter), "status": "OPEN"}

    transitions_by_ticket = defaultdict(list)

    def fake_transition_status(conn, ticket_id, actor_id, new_status):
        transitions_by_ticket[ticket_id].append(new_status)

    monkeypatch.setattr(seed_service, "create_ticket", fake_create_ticket)
    monkeypatch.setattr(seed_service, "transition_status", fake_transition_status)

    conn = make_conn(fetchall_results=[[]], auto_increment_lastrowid=True)
    summary = seed_demo_data(conn, num_users=4, num_tickets=6)

    total_tickets = sum(summary["tickets_by_status"].values())
    assert total_tickets > 0  # sanity: this run actually created tickets

    path_lengths_to_status = {len(path): status for status, path in STATUS_PATHS.items()}
    reached_counts = {status: 0 for status in STATUS_PATHS}

    for ticket_id, sequence in transitions_by_ticket.items():
        expected_status = path_lengths_to_status[len(sequence)]
        assert sequence == STATUS_PATHS[expected_status]
        reached_counts[expected_status] += 1

    # Tickets that ended up OPEN never appear in transitions_by_ticket at
    # all (zero transition_status calls) -- account for those separately.
    reached_counts["OPEN"] += total_tickets - len(transitions_by_ticket)

    assert reached_counts == summary["tickets_by_status"]


# ---------------------------------------------------------------------------
# AC-3 (FR-SEED-03): re-running seed_demo_data never duplicates/corrupts
# rows and never touches non-demo (real) users -- every DELETE is scoped to
# ids that came from the `username LIKE 'demo_%'` filter.
# ---------------------------------------------------------------------------


def test_fr_seed_03_clear_seeded_data_scopes_every_delete_to_demo_prefixed_ids(
    make_conn,
):
    demo_user_rows = [{"id": 10}, {"id": 11}]
    demo_ticket_rows = [{"id": 100}, {"id": 101}]
    conn = make_conn(fetchall_results=[demo_user_rows, demo_ticket_rows])

    _clear_seeded_data(conn)

    executed = conn.cursor_obj.executed
    select_sql, select_params = executed[0]
    assert "SELECT id FROM users WHERE username LIKE" in select_sql
    assert select_params == ("demo_%",)

    delete_statements = [
        (sql, params) for sql, params in executed if sql.strip().upper().startswith("DELETE")
    ]
    # Every DELETE's params trace back only to ids collected via the
    # demo_%-scoped SELECTs above -- never an unscoped/blanket delete.
    assert delete_statements  # this scenario has rows to delete
    for sql, params in delete_statements:
        assert set(params).issubset({10, 11, 100, 101})
        assert "WHERE" in sql.upper()

    delete_users_sql, delete_users_params = next(
        (sql, params) for sql, params in delete_statements if "FROM users" in sql
    )
    assert set(delete_users_params) == {10, 11}

    delete_tickets_sql, delete_tickets_params = next(
        (sql, params) for sql, params in delete_statements if "FROM tickets" in sql
    )
    assert set(delete_tickets_params) == {100, 101}

    # The DELETEs happen strictly after the scoping SELECTs that produced
    # their ids -- never before.
    select_indexes = [
        i for i, (sql, _params) in enumerate(executed) if sql.strip().upper().startswith("SELECT")
    ]
    delete_indexes = [
        i for i, (sql, _params) in enumerate(executed) if sql.strip().upper().startswith("DELETE")
    ]
    assert max(select_indexes) < min(delete_indexes)

    assert conn.commit_calls == 1


def test_fr_seed_03_clear_seeded_data_no_demo_users_issues_no_delete_and_no_commit(
    make_conn,
):
    conn = make_conn(fetchall_results=[[]])

    _clear_seeded_data(conn)

    executed = conn.cursor_obj.executed
    assert len(executed) == 1  # only the demo_%-scoped SELECT, nothing else
    assert not any(sql.strip().upper().startswith("DELETE") for sql, _p in executed)
    # Never touches (or even opens a transaction against) real user data
    # when there is no seeded data to clear.
    assert conn.commit_calls == 0


def test_fr_seed_03_reseeding_clears_before_recreating(monkeypatch, make_conn):
    """seed_demo_data always clears existing demo rows before regenerating,
    so a second run doesn't duplicate: the demo_%-scoped SELECT executes
    before any new INSERT INTO users."""
    monkeypatch.setattr(seed_service, "_create_demo_ticket", lambda conn, user_id: "OPEN")

    conn = make_conn(
        fetchall_results=[[{"id": 5}], []],  # one stale demo user, no stale tickets
        auto_increment_lastrowid=True,
    )

    seed_demo_data(conn, num_users=2, num_tickets=1)

    executed = conn.cursor_obj.executed
    clear_select_index = next(
        i
        for i, (sql, _p) in enumerate(executed)
        if "SELECT id FROM users WHERE username LIKE" in sql
    )
    first_insert_users_index = next(
        i for i, (sql, _p) in enumerate(executed) if "INSERT INTO users" in sql
    )
    delete_users_index = next(
        i for i, (sql, _p) in enumerate(executed) if sql.strip().upper().startswith("DELETE") and "FROM users" in sql
    )
    assert clear_select_index < delete_users_index < first_insert_users_index


# ---------------------------------------------------------------------------
# AC-4 (out-of-scope guardrail / FR-SEED-01): seeded usernames/emails are
# obviously synthetic, never resembling real PII.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("index", [1, 42, 999])
def test_fr_seed_04_create_demo_user_username_and_email_are_synthetic(make_conn, index):
    conn = make_conn()

    _create_demo_user(conn, index)

    insert_sql, insert_params = conn.cursor_obj.executed[0]
    assert "INSERT INTO users" in insert_sql
    username, email, password_hash, role = insert_params

    assert username.startswith("demo_")
    assert email.endswith("@example.invalid")
    assert role in ("REQUESTER", "SUPPORT_AGENT")
    # Password is stored as a bcrypt hash, never plaintext (NFR-01).
    assert password_hash.startswith(("$2a$", "$2b$", "$2y$"))


def test_fr_seed_04_full_run_every_seeded_user_is_synthetic(monkeypatch, make_conn):
    monkeypatch.setattr(seed_service, "_create_demo_ticket", lambda conn, user_id: "OPEN")
    conn = make_conn(fetchall_results=[[]], auto_increment_lastrowid=True)

    seed_demo_data(conn, num_users=6, num_tickets=1)

    insert_user_calls = [
        params for sql, params in conn.cursor_obj.executed if "INSERT INTO users" in sql
    ]
    assert len(insert_user_calls) == 6
    for username, email, _password_hash, _role in insert_user_calls:
        assert username.startswith("demo_")
        assert email.endswith("@example.invalid")


# ---------------------------------------------------------------------------
# AC-5 (guardrail): refuses to run, with a clear error, against a database
# that doesn't look local/demo -- before any DB call. localhost/127.0.0.1
# (and the unset default) are allowed through.
# ---------------------------------------------------------------------------


def test_fr_seed_05_non_local_db_host_raises_guard_error_before_any_db_call(
    monkeypatch, make_conn
):
    monkeypatch.setenv("DB_HOST", "prod-db.example.com")
    conn = make_conn()

    with pytest.raises(SeedGuardError) as exc_info:
        seed_demo_data(conn, 1, 1)

    assert "prod-db.example.com" in str(exc_info.value)
    assert conn.cursor_obj.executed == []
    assert conn.commit_calls == 0


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "LOCALHOST"])
def test_fr_seed_05_local_db_host_allowed_through_guard(monkeypatch, host):
    monkeypatch.setenv("DB_HOST", host)
    _assert_demo_database()  # must not raise


def test_fr_seed_05_unset_db_host_defaults_to_local_and_is_allowed(monkeypatch):
    monkeypatch.delenv("DB_HOST", raising=False)
    _assert_demo_database()  # must not raise


def test_fr_seed_05_guard_checked_before_clearing_existing_demo_data(
    monkeypatch, make_conn
):
    """Even if the guard fired *after* the count check, it must still fire
    strictly before `_clear_seeded_data` touches the DB -- confirmed here by
    asserting the clear step's own SELECT never runs."""
    monkeypatch.setenv("DB_HOST", "some-remote-host")
    conn = make_conn(fetchall_results=[[]])

    with pytest.raises(SeedGuardError):
        seed_demo_data(conn, 3, 3)

    assert not any(
        "SELECT id FROM users WHERE username LIKE" in sql
        for sql, _params in conn.cursor_obj.executed
    )
