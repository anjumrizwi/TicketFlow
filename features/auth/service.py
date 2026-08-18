"""Registration and login logic for the auth feature (specs/auth.md).

FR-AUTH-01..03, FR-AUTH-02 (bcrypt only), NFR-01 (no plaintext password
ever logged/persisted). Callers own the connection's lifecycle.
"""
import bcrypt
import pyodbc

REGISTER_CONFLICT_MESSAGE = "That username or email is already registered."
LOGIN_FAILURE_MESSAGE = "Invalid username or password."

# Verified against a real login attempt so a nonexistent account takes
# roughly as long to reject as a wrong password does (AC-4: identical
# failure whether or not the account exists).
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt())


class AuthError(Exception):
    """Raised for invalid input, duplicate accounts, or failed login."""


def _require_non_empty(value, field_name):
    if not value or not value.strip():
        raise AuthError(f"{field_name} is required.")


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def register_user(conn, username, email, password):
    """Create a Requester account. Raises AuthError on invalid/duplicate input."""
    _require_non_empty(username, "Username")
    _require_non_empty(email, "Email")
    _require_non_empty(password, "Password")

    username = username.strip()
    email = email.strip()
    password_hash = hash_password(password)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        )
        if cur.fetchone():
            raise AuthError(REGISTER_CONFLICT_MESSAGE)

        try:
            cur.execute(
                "INSERT INTO users (username, email, password_hash, role) "
                "OUTPUT INSERTED.id "
                "VALUES (?, ?, ?, 'REQUESTER')",
                (username, email, password_hash),
            )
        except pyodbc.IntegrityError:
            # A concurrent registration won the race between the check above
            # and this insert; the unique constraint is the source of truth.
            conn.rollback()
            raise AuthError(REGISTER_CONFLICT_MESSAGE) from None

        user_id = cur.fetchone()["id"]
        conn.commit()

        cur.execute(
            "SELECT id, username, email, role, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        return cur.fetchone()


def authenticate_user(conn, identifier, password):
    """Return the user row on success. Raises AuthError on any failure,
    with an identical message whether the account exists or not."""
    _require_non_empty(identifier, "Username")
    _require_non_empty(password, "Password")

    identifier = identifier.strip()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, password_hash, role, created_at "
            "FROM users WHERE username = ? OR email = ?",
            (identifier, identifier),
        )
        row = cur.fetchone()

    if row is None:
        verify_password(password, _DUMMY_HASH.decode("utf-8"))
        raise AuthError(LOGIN_FAILURE_MESSAGE)

    if not verify_password(password, row["password_hash"]):
        raise AuthError(LOGIN_FAILURE_MESSAGE)

    row.pop("password_hash", None)
    return row
