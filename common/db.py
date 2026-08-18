"""Shared SQL Server connection handling (used by every feature).

Per CLAUDE.md: single local/demo instance, Windows/AD integrated auth
(Trusted_Connection) by default; any credentials, if ever needed, come
only from environment variables, never hardcoded.
"""

import os

import pyodbc

_ODBC_DRIVER = "{ODBC Driver 18 for SQL Server}"


class DictCursor:
    """Wraps a pyodbc cursor so fetchone/fetchall return dicts keyed by
    column name. pyodbc rows are positional/attribute-accessed only, but
    every feature in this app is written against dict-style row access
    (`row["field"]`), so this keeps that contract intact.
    """

    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def _column_names(self):
        return [col[0] for col in self._cursor.description] if self._cursor.description else []

    def execute(self, sql, params=None):
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, tuple(params))
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(zip(self._column_names(), row))

    def fetchall(self):
        columns = self._column_names()
        return [dict(zip(columns, row)) for row in self._cursor.fetchall()]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()
        return False


class Connection:
    """Wraps a pyodbc connection so `.cursor()` hands back a `DictCursor`."""

    def __init__(self, raw_connection):
        self._connection = raw_connection

    def cursor(self):
        return DictCursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_connection():
    """Open a new SQL Server connection scoped to one request/action.

    Autocommit is off so callers can group a change with its
    `ticket_activity` row (or, for auth, a uniqueness check with an
    insert) in a single transaction. `TrustServerCertificate` is on
    because a local/demo instance won't have a CA-signed TLS cert.
    """
    server = os.environ.get("DB_HOST", "localhost\\SQLEXPRESS")
    port = os.environ.get("DB_PORT")
    if port:
        server = f"{server},{port}"

    conn_str = (
        f"DRIVER={_ODBC_DRIVER};"
        f"SERVER={server};"
        f"DATABASE={os.environ.get('DB_NAME', 'TicketFlow')};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    raw = pyodbc.connect(conn_str, autocommit=False)
    return Connection(raw)


def init_schema(conn):
    """Create tables this feature owns if they don't already exist."""
    with conn.cursor() as cur:
        cur.execute("""
            IF OBJECT_ID('dbo.users', 'U') IS NULL
            CREATE TABLE users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(60) NOT NULL,
                role VARCHAR(16) NOT NULL DEFAULT 'REQUESTER'
                    CHECK (role IN ('REQUESTER', 'SUPPORT_AGENT')),
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
            )
            """)
        cur.execute("""
            IF OBJECT_ID('dbo.tickets', 'U') IS NULL
            CREATE TABLE tickets (
                id INT IDENTITY(1,1) PRIMARY KEY,
                -- Nullable so it can be set from the IDENTITY id right after
                -- insert, in the same transaction. Unlike MySQL, a plain
                -- SQL Server UNIQUE constraint allows only one NULL, so the
                -- "many NULLs briefly, one real value later" pattern needs
                -- the filtered unique index below instead of an inline
                -- UNIQUE column constraint.
                ticket_number VARCHAR(20) NULL,
                requester_id INT NOT NULL,
                assignee_id INT NULL,
                title VARCHAR(255) NOT NULL,
                description VARCHAR(MAX) NOT NULL,
                category VARCHAR(32) NOT NULL
                    CHECK (category IN ('Bug', 'Feature Request', 'Access', 'Hardware', 'How-to / Other')),
                priority VARCHAR(16) NOT NULL
                    CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
                status VARCHAR(16) NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')),
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                FOREIGN KEY (requester_id) REFERENCES users(id),
                FOREIGN KEY (assignee_id) REFERENCES users(id)
            )
            """)
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.indexes
                WHERE name = 'UQ_tickets_ticket_number' AND object_id = OBJECT_ID('dbo.tickets')
            )
            CREATE UNIQUE INDEX UQ_tickets_ticket_number ON tickets(ticket_number)
                WHERE ticket_number IS NOT NULL
            """)
        # MySQL's column-level "ON UPDATE CURRENT_TIMESTAMP" has no direct
        # T-SQL equivalent; a trigger is the standard replacement. CREATE
        # TRIGGER must be the only statement in its batch, hence EXEC(...).
        cur.execute("""
            IF OBJECT_ID('dbo.trg_tickets_updated_at', 'TR') IS NULL
            EXEC('
                CREATE TRIGGER trg_tickets_updated_at ON tickets
                AFTER UPDATE AS
                BEGIN
                    SET NOCOUNT ON;
                    UPDATE t SET updated_at = SYSDATETIME()
                    FROM tickets t
                    INNER JOIN inserted i ON t.id = i.id
                END
            ')
            """)
        cur.execute("""
            IF OBJECT_ID('dbo.ticket_activity', 'U') IS NULL
            CREATE TABLE ticket_activity (
                id INT IDENTITY(1,1) PRIMARY KEY,
                ticket_id INT NOT NULL,
                actor_id INT NOT NULL,
                action VARCHAR(32) NOT NULL,
                field_changed VARCHAR(64) NULL,
                old_value VARCHAR(MAX) NULL,
                new_value VARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                FOREIGN KEY (ticket_id) REFERENCES tickets(id),
                FOREIGN KEY (actor_id) REFERENCES users(id)
            )
            """)
        cur.execute("""
            IF OBJECT_ID('dbo.chat_error_log', 'U') IS NULL
            CREATE TABLE chat_error_log (
                id INT IDENTITY(1,1) PRIMARY KEY,
                user_id INT NOT NULL,
                error_type VARCHAR(64) NOT NULL,
                error_message VARCHAR(500) NOT NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)
    conn.commit()
