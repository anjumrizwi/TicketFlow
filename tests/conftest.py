"""Shared hermetic test fixtures.

No real SQL Server instance is assumed to be reachable in this environment.
Every DB-touching test in this suite drives `features/auth/service.py`
through a fake pyodbc-shaped connection/cursor so the auth business logic
can be exercised without any network or server dependency.
"""

import pyodbc
import pytest


class FakeCursor:
    """Minimal stand-in for the app's pyodbc-backed DictCursor used as a
    context manager.

    Records every `execute()` call (sql + params) so tests can assert what
    was or wasn't sent to the database (e.g. "no INSERT happened"). Each
    call to `fetchone()` pops the next canned result off a queue supplied
    by the test, in the order the code under test actually calls
    `fetchone()` (note: not every `execute()` is followed by a
    `fetchone()`, e.g. an INSERT isn't — except the id-generating INSERTs
    described below).

    Production code has no `cursor.lastrowid` equivalent under pyodbc:
    every autoincrement-id INSERT instead uses `OUTPUT INSERTED.id` in the
    SQL text and reads the id via `cur.fetchone()["id"]` immediately after
    `execute()`. To keep that working here without changing any existing
    `make_conn(...)` call sites, `execute()` detects the `"OUTPUT INSERTED"`
    substring (case-insensitive) in the SQL and pushes `{"id": <value>}`
    onto the *front* of `fetchone_results`, so the very next `fetchone()`
    call returns it ahead of anything the test already queued.
    """

    def __init__(
        self,
        fetchone_results=None,
        raise_on_execute=None,
        lastrowid=1,
        fetchall_results=None,
        auto_increment_lastrowid=False,
    ):
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results or [])
        self.raise_on_execute = raise_on_execute or {}
        self.executed = []
        self.lastrowid = lastrowid
        self.auto_increment_lastrowid = auto_increment_lastrowid
        self._next_lastrowid = lastrowid

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        call_number = len(self.executed)
        if call_number in self.raise_on_execute:
            raise self.raise_on_execute[call_number]
        if "output inserted" in sql.strip().lower():
            if self.auto_increment_lastrowid:
                self.lastrowid = self._next_lastrowid
                self._next_lastrowid += 1
            self.fetchone_results.insert(0, {"id": self.lastrowid})

    def fetchone(self):
        if not self.fetchone_results:
            return None
        return self.fetchone_results.pop(0)

    def fetchall(self):
        """Pop the next canned result set off the queue (a list of row
        dicts), in the order the code under test actually calls
        `fetchall()`. Only used by features that issue multi-row SELECTs
        (e.g. seed-data's demo-row cleanup); existing single-row-fetch
        callers are unaffected."""
        if not self.fetchall_results:
            return []
        return self.fetchall_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeConnection:
    """Minimal stand-in for a pyodbc connection.

    Tracks commit()/rollback() calls so tests can assert transactional
    behavior (e.g. rollback on a race-condition IntegrityError, and that
    commit is only reached on a genuinely successful path).
    """

    def __init__(
        self,
        fetchone_results=None,
        raise_on_execute=None,
        lastrowid=1,
        fetchall_results=None,
        auto_increment_lastrowid=False,
    ):
        self.cursor_obj = FakeCursor(
            fetchone_results,
            raise_on_execute,
            lastrowid=lastrowid,
            fetchall_results=fetchall_results,
            auto_increment_lastrowid=auto_increment_lastrowid,
        )
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        # No-op: real pyodbc connections are closed by every UI page in a
        # `finally` block; callers that reach this double must be able to do
        # the same without needing a real socket to tear down.
        pass


@pytest.fixture
def make_conn():
    """Factory fixture: build a FakeConnection with scripted cursor behavior.

    Usage: make_conn(fetchone_results=[None, {"id": 1, ...}])
    `fetchall_results` (a list of row-dict lists) and
    `auto_increment_lastrowid` (True to make each INSERT hand back a fresh,
    increasing `lastrowid`, needed by features that create multiple rows in
    a loop, e.g. seed-data) are opt-in and don't affect existing callers.
    """

    def _make(
        fetchone_results=None,
        raise_on_execute=None,
        lastrowid=1,
        fetchall_results=None,
        auto_increment_lastrowid=False,
    ):
        return FakeConnection(
            fetchone_results=fetchone_results,
            raise_on_execute=raise_on_execute,
            lastrowid=lastrowid,
            fetchall_results=fetchall_results,
            auto_increment_lastrowid=auto_increment_lastrowid,
        )

    return _make


@pytest.fixture
def integrity_error():
    return pyodbc.IntegrityError("23000", "Duplicate entry")
