"""Shared MySQL connection handling (used by every feature).

Per CLAUDE.md: single `root` connection, demo-only; credentials come only
from environment variables, never hardcoded.
"""

import os

import pymysql
import pymysql.cursors


def get_connection():
    """Open a new PyMySQL connection scoped to one request/action.

    Autocommit is off so callers can group a change with its
    `ticket_activity` row (or, for auth, a uniqueness check with an
    insert) in a single transaction.
    """
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "ticketflow"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def init_schema(conn):
    """Create tables this feature owns if they don't already exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(60) NOT NULL,
                role ENUM('REQUESTER', 'SUPPORT_AGENT') NOT NULL DEFAULT 'REQUESTER',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                -- Nullable so it can be set from the AUTO_INCREMENT id right
                -- after insert, in the same transaction, with no collision
                -- window between concurrent creations (MySQL allows
                -- multiple NULLs under a UNIQUE index).
                ticket_number VARCHAR(20) UNIQUE,
                requester_id INT NOT NULL,
                assignee_id INT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                category ENUM('Bug', 'Feature Request', 'Access', 'Hardware', 'How-to / Other') NOT NULL,
                priority ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT') NOT NULL,
                status ENUM('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED') NOT NULL DEFAULT 'OPEN',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (requester_id) REFERENCES users(id),
                FOREIGN KEY (assignee_id) REFERENCES users(id)
            )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ticket_activity (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL,
                actor_id INT NOT NULL,
                action VARCHAR(32) NOT NULL,
                field_changed VARCHAR(64) NULL,
                old_value TEXT NULL,
                new_value TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id),
                FOREIGN KEY (actor_id) REFERENCES users(id)
            )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_error_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                error_type VARCHAR(64) NOT NULL,
                error_message VARCHAR(500) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)
    conn.commit()
