"""Tests for features/auth/service.py against specs/auth.md acceptance
criteria (AC-1..AC-4; AC-5..AC-7 are covered in test_session.py / noted as
not-yet-applicable, see that file's module docstring).

All tests use a fake, in-memory pyodbc-shaped connection (see
tests/conftest.py) — no real SQL Server instance is required or assumed.
"""

import bcrypt
import pytest

from features.auth.service import (
    LOGIN_FAILURE_MESSAGE,
    REGISTER_CONFLICT_MESSAGE,
    AuthError,
    authenticate_user,
    hash_password,
    register_user,
    verify_password,
)

# ---------------------------------------------------------------------------
# hash_password / verify_password (pure functions, no DB) — supports AC-3.
# ---------------------------------------------------------------------------


def test_fr_auth_03_hash_password_returns_bcrypt_not_plaintext():
    password = "correct horse battery staple"
    hashed = hash_password(password)

    assert hashed != password
    # bcrypt hashes are ASCII strings starting with one of these prefixes.
    assert hashed.startswith(("$2a$", "$2b$", "$2y$"))
    # Round-trips through real bcrypt so we know it's a genuine bcrypt hash,
    # not just a string that happens to look like one.
    assert bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def test_fr_auth_03_verify_password_accepts_correct_password():
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed) is True


def test_fr_auth_03_verify_password_rejects_incorrect_password():
    hashed = hash_password("s3cret!")
    assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# AC-1: duplicate username/email at registration -> generic rejection,
# no insert performed.
# ---------------------------------------------------------------------------


def test_fr_auth_01_duplicate_username_or_email_rejected_generically(make_conn):
    # First execute() (the uniqueness check) finds an existing row.
    conn = make_conn(fetchone_results=[{"id": 99}])

    with pytest.raises(AuthError) as exc_info:
        register_user(conn, "existing_user", "new@example.com", "password123")

    # Message is the fixed, generic conflict message (mentions both
    # "username" and "email" symmetrically) -- it never commits to saying
    # which field actually collided, so a caller can't distinguish a
    # username clash from an email clash by wording.
    assert str(exc_info.value) == REGISTER_CONFLICT_MESSAGE


def test_fr_auth_01_duplicate_registration_performs_no_insert(make_conn):
    conn = make_conn(fetchone_results=[{"id": 99}])

    with pytest.raises(AuthError):
        register_user(conn, "existing_user", "new@example.com", "password123")

    executed_sql = [sql for sql, _params in conn.cursor_obj.executed]
    assert not any("INSERT" in sql.upper() for sql in executed_sql)
    assert conn.commit_calls == 0


def test_fr_auth_01_email_only_collision_gets_same_generic_message(make_conn):
    """A collision purely on email (different username) must produce the
    exact same message as a username collision -- non-enumerating."""
    conn = make_conn(fetchone_results=[{"id": 42}])

    with pytest.raises(AuthError) as exc_info:
        register_user(conn, "brand_new_username", "taken@example.com", "password123")

    assert str(exc_info.value) == REGISTER_CONFLICT_MESSAGE


def test_fr_auth_01_race_condition_integrity_error_rolls_back_and_rejects(
    make_conn, integrity_error
):
    """A concurrent registration can win the race between the SELECT check
    and the INSERT. The unique constraint (surfaced as IntegrityError) must
    still produce the same generic message and must not leave a partial
    write: rollback() is called and commit() never is."""
    conn = make_conn(
        fetchone_results=[None],  # uniqueness check sees no conflict...
        raise_on_execute={2: integrity_error},  # ...but the INSERT (2nd execute) fails
    )

    with pytest.raises(AuthError) as exc_info:
        register_user(conn, "someone", "someone@example.com", "password123")

    assert str(exc_info.value) == REGISTER_CONFLICT_MESSAGE
    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0


# ---------------------------------------------------------------------------
# AC-2: empty username/email/password at registration -> rejected, no
# insert performed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "username,email,password",
    [
        ("", "user@example.com", "password123"),
        ("   ", "user@example.com", "password123"),
        ("user", "", "password123"),
        ("user", "   ", "password123"),
        ("user", "user@example.com", ""),
        ("user", "user@example.com", "   "),
        (None, "user@example.com", "password123"),
    ],
)
def test_fr_auth_02_empty_or_blank_fields_rejected(make_conn, username, email, password):
    conn = make_conn(fetchone_results=[])

    with pytest.raises(AuthError):
        register_user(conn, username, email, password)

    # No query at all should have been issued: validation happens before
    # any DB access, so a blank field can never reach the uniqueness check
    # or the insert.
    assert conn.cursor_obj.executed == []
    assert conn.commit_calls == 0


# ---------------------------------------------------------------------------
# AC-3: valid unique registration -> row inserted with role REQUESTER and a
# bcrypt hash (never the raw password).
# ---------------------------------------------------------------------------


def test_fr_auth_03_valid_registration_inserts_requester_with_bcrypt_hash(make_conn):
    created_row = {
        "id": 1,
        "username": "newuser",
        "email": "newuser@example.com",
        "role": "REQUESTER",
        "created_at": "2026-08-17 00:00:00",
    }
    conn = make_conn(fetchone_results=[None, created_row], lastrowid=1)

    result = register_user(conn, "newuser", "newuser@example.com", "hunter2")

    insert_calls = [
        (sql, params) for sql, params in conn.cursor_obj.executed if "INSERT" in sql.upper()
    ]
    assert len(insert_calls) == 1
    insert_sql, insert_params = insert_calls[0]

    assert "REQUESTER" in insert_sql
    stored_password_value = insert_params[2]
    assert stored_password_value != "hunter2"  # raw password never stored
    assert stored_password_value.startswith(("$2a$", "$2b$", "$2y$"))
    assert bcrypt.checkpw(b"hunter2", stored_password_value.encode("utf-8"))

    assert conn.commit_calls == 1
    assert result == created_row


def test_fr_auth_03_registration_strips_surrounding_whitespace(make_conn):
    created_row = {"id": 1, "username": "trimmed", "email": "trimmed@example.com"}
    conn = make_conn(fetchone_results=[None, created_row])

    register_user(conn, "  trimmed  ", "  trimmed@example.com  ", "hunter2")

    _select_sql, select_params = conn.cursor_obj.executed[0]
    assert select_params == ("trimmed", "trimmed@example.com")


# ---------------------------------------------------------------------------
# AC-4: correct login succeeds and never exposes password_hash; incorrect
# password on an existing account and login on a nonexistent account raise
# AuthError with the identical message text.
# ---------------------------------------------------------------------------


def test_fr_auth_04_correct_login_succeeds_and_omits_password_hash(make_conn):
    password_hash = hash_password("correct-password")
    user_row = {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": password_hash,
        "role": "REQUESTER",
        "created_at": "2026-08-17 00:00:00",
    }
    conn = make_conn(fetchone_results=[user_row])

    result = authenticate_user(conn, "alice", "correct-password")

    assert result["username"] == "alice"
    assert "password_hash" not in result


def test_fr_auth_04_wrong_password_on_existing_account_raises_generic_error(make_conn):
    password_hash = hash_password("correct-password")
    user_row = {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": password_hash,
        "role": "REQUESTER",
        "created_at": "2026-08-17 00:00:00",
    }
    conn = make_conn(fetchone_results=[user_row])

    with pytest.raises(AuthError) as exc_info:
        authenticate_user(conn, "alice", "wrong-password")

    assert str(exc_info.value) == LOGIN_FAILURE_MESSAGE


def test_fr_auth_04_nonexistent_account_raises_generic_error(make_conn):
    conn = make_conn(fetchone_results=[None])

    with pytest.raises(AuthError) as exc_info:
        authenticate_user(conn, "ghost", "whatever")

    assert str(exc_info.value) == LOGIN_FAILURE_MESSAGE


def test_fr_auth_04_failure_message_identical_wrong_password_vs_no_account(make_conn):
    """The core non-enumeration guarantee: a caller must not be able to
    distinguish 'wrong password' from 'no such account' by message text."""
    password_hash = hash_password("correct-password")
    existing_user_row = {
        "id": 1,
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": password_hash,
        "role": "REQUESTER",
        "created_at": "2026-08-17 00:00:00",
    }

    conn_wrong_password = make_conn(fetchone_results=[existing_user_row])
    conn_no_account = make_conn(fetchone_results=[None])

    with pytest.raises(AuthError) as wrong_password_exc:
        authenticate_user(conn_wrong_password, "alice", "wrong-password")

    with pytest.raises(AuthError) as no_account_exc:
        authenticate_user(conn_no_account, "ghost", "wrong-password")

    assert str(wrong_password_exc.value) == str(no_account_exc.value)


def test_fr_auth_04_empty_identifier_or_password_rejected_without_query(make_conn):
    conn = make_conn(fetchone_results=[])

    with pytest.raises(AuthError):
        authenticate_user(conn, "", "somepassword")

    with pytest.raises(AuthError):
        authenticate_user(conn, "someone", "")

    assert conn.cursor_obj.executed == []
