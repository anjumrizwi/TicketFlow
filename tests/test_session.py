"""Tests for common/session.py against specs/auth.md AC-5, AC-6, AC-7.

AC-5 (session persists across page navigation) and AC-6 (logout clears the
session) are thin wrappers over `st.session_state`, so we stub Streamlit
with a minimal fake (a dict-backed `session_state` plus a `stop()` that
raises, mirroring Streamlit's real halt-the-script behavior) rather than
pulling in the full `streamlit.testing` app-harness. That keeps the test
hermetic and fast while still exercising TicketFlow's own logic.

AC-7 (ticket/report/chat access blocked without a session) is exercised
here only at the `require_auth()` unit level, since no ticket/report/chat
pages exist in the repository yet (FR-AUTH-06 is a convention those future
pages must follow: call `require_auth()` first). Once those pages exist,
this suite should grow a test asserting each page module calls
`require_auth()` before any data access -- flagged as not yet applicable
rather than faked here.
"""

import sys
import types

import pytest


class _StopRendering(Exception):
    """Stand-in for Streamlit halting script execution via st.stop()."""


class _FakeStreamlit(types.SimpleNamespace):
    def __init__(self):
        super().__init__(session_state={})

    def warning(self, *args, **kwargs):
        pass

    def stop(self):
        raise _StopRendering()


@pytest.fixture
def session_module(monkeypatch):
    """Import common.session with a fake `streamlit` module injected, so
    session state lives in a plain dict we fully control."""
    fake_st = _FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    # Force a fresh import bound to the fake streamlit module, and forget it
    # afterwards so other test modules that need the real thing aren't
    # affected.
    # `import common.session` (not `from common import session`) is required
    # here: `from common import session` would just return the stale
    # `session` attribute still cached on the `common` package object even
    # after popping "common.session" from sys.modules, defeating the
    # fresh-import-per-test isolation this fixture exists to provide.
    sys.modules.pop("common.session", None)
    import common.session as session  # noqa: PLR0402

    yield session

    sys.modules.pop("common.session", None)


def test_fr_auth_05_login_persists_user_in_session_state(session_module):
    user = {"id": 1, "username": "alice", "role": "REQUESTER"}

    session_module.login(user)

    assert session_module.is_authenticated() is True
    assert session_module.current_user() == user


def test_fr_auth_05_current_user_none_when_never_logged_in(session_module):
    assert session_module.is_authenticated() is False
    assert session_module.current_user() is None


def test_fr_auth_06_logout_clears_session(session_module):
    user = {"id": 1, "username": "alice", "role": "REQUESTER"}
    session_module.login(user)
    assert session_module.is_authenticated() is True

    session_module.logout()

    assert session_module.is_authenticated() is False
    assert session_module.current_user() is None


def test_fr_auth_06_logout_is_safe_when_not_logged_in(session_module):
    # Logging out without an active session must not raise.
    session_module.logout()
    assert session_module.is_authenticated() is False


def test_fr_auth_07_require_auth_blocks_when_no_session(session_module):
    with pytest.raises(_StopRendering):
        session_module.require_auth()


def test_fr_auth_07_require_auth_passes_through_when_authenticated(session_module):
    user = {"id": 1, "username": "alice", "role": "REQUESTER"}
    session_module.login(user)

    result = session_module.require_auth()

    assert result == user
