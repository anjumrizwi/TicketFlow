"""Idempotent demo data generation (specs/seed-data.md).

FR-SEED-01..04. Reuses `features.auth.service.hash_password` and
`features.tickets.service.create_ticket`/`transition_status` rather than
re-deriving password hashing or status-transition rules here.
"""
import os
import random

from features.auth.service import hash_password
from features.tickets.service import CATEGORIES, PRIORITIES, create_ticket, transition_status

DEMO_USERNAME_PREFIX = "demo_"
# Not a real credential: a fixed, obviously-synthetic password shared by
# every seeded demo account so a presenter/tester can log in as any of them.
DEMO_PASSWORD = "DemoPass123!"

# Weighted so most seeded users are ordinary requesters (BRD §10 roles).
ROLE_WEIGHTS = (("REQUESTER", 4), ("SUPPORT_AGENT", 1))

TITLES_BY_CATEGORY = {
    "Bug": [
        "Login button unresponsive on mobile",
        "Export cuts off the last row",
        "Dashboard counts don't refresh after status change",
        "Search returns duplicate results",
    ],
    "Feature Request": [
        "Add dark mode",
        "Allow bulk status updates",
        "Support saved filter presets",
        "Add a keyboard shortcut for ticket search",
    ],
    "Access": [
        "Need access to the reporting folder",
        "Locked out after password reset",
        "Request elevated permissions for new hire",
        "Cannot see tickets assigned to my team",
    ],
    "Hardware": [
        "Laptop battery draining too fast",
        "Monitor flickering intermittently",
        "Keyboard keys unresponsive",
        "Docking station not detected",
    ],
    "How-to / Other": [
        "How do I change my notification settings?",
        "Where can I find past export reports?",
        "How do I reassign a ticket?",
        "General question about the onboarding process",
    ],
}

# Status -> ordered legal transitions from OPEN needed to reach it. Each
# step is validated against BR-02 by `transition_status` itself, so this
# is just the walk order, not a second copy of the transition rules.
STATUS_PATHS = {
    "OPEN": [],
    "IN_PROGRESS": ["IN_PROGRESS"],
    "RESOLVED": ["IN_PROGRESS", "RESOLVED"],
    "CLOSED": ["IN_PROGRESS", "RESOLVED", "CLOSED"],
}


class SeedError(Exception):
    """Raised for invalid seed-data input."""


class SeedGuardError(Exception):
    """Raised when the target database doesn't look like a local/demo DB."""


def _assert_demo_database():
    host = os.environ.get("DB_HOST", "localhost").strip().lower()
    if host not in ("localhost", "127.0.0.1"):
        raise SeedGuardError(
            f"Refusing to seed: DB_HOST={host!r} does not look like a local/demo database."
        )


def _random_role():
    roles, weights = zip(*ROLE_WEIGHTS)
    return random.choices(roles, weights=weights, k=1)[0]


def _clear_seeded_data(conn):
    """Delete only demo-prefixed users and their tickets/activity (BR-05-
    adjacent: never touch non-seeded/real user data)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE username LIKE %s",
            (f"{DEMO_USERNAME_PREFIX}%",),
        )
        demo_user_ids = [row["id"] for row in cur.fetchall()]
        if not demo_user_ids:
            return

        user_placeholders = ",".join(["%s"] * len(demo_user_ids))
        cur.execute(
            f"SELECT id FROM tickets WHERE requester_id IN ({user_placeholders})",
            demo_user_ids,
        )
        demo_ticket_ids = [row["id"] for row in cur.fetchall()]

        if demo_ticket_ids:
            ticket_placeholders = ",".join(["%s"] * len(demo_ticket_ids))
            cur.execute(
                f"DELETE FROM ticket_activity WHERE ticket_id IN ({ticket_placeholders})",
                demo_ticket_ids,
            )
            cur.execute(
                f"DELETE FROM tickets WHERE id IN ({ticket_placeholders})",
                demo_ticket_ids,
            )

        cur.execute(
            f"DELETE FROM users WHERE id IN ({user_placeholders})",
            demo_user_ids,
        )
    conn.commit()


def _create_demo_user(conn, index):
    username = f"{DEMO_USERNAME_PREFIX}user{index:03d}"
    email = f"{username}@example.invalid"
    password_hash = hash_password(DEMO_PASSWORD)
    role = _random_role()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, email, password_hash, role) "
            "VALUES (%s, %s, %s, %s)",
            (username, email, password_hash, role),
        )
        user_id = cur.lastrowid
    conn.commit()
    return user_id


def _create_demo_ticket(conn, user_id):
    category = random.choice(CATEGORIES)
    priority = random.choice(PRIORITIES)
    title = random.choice(TITLES_BY_CATEGORY[category])
    description = f"Demo seed data: {title.lower()}."

    ticket = create_ticket(conn, user_id, title, description, category, priority)

    target_status = random.choice(list(STATUS_PATHS))
    for step in STATUS_PATHS[target_status]:
        transition_status(conn, ticket["id"], user_id, step)

    return target_status


def seed_demo_data(conn, num_users, num_tickets):
    """Idempotently (re)generate `num_users` demo users, each with
    1..`num_tickets` tickets reached only via legal BR-02 transitions.

    Refuses to run against a database that doesn't look local/demo
    (`SeedGuardError`) or against invalid counts (`SeedError`). Always
    clears any previously seeded demo rows first, so re-running never
    duplicates or corrupts data and never touches real user data.
    """
    if num_users < 0 or num_tickets < 0:
        raise SeedError("<users> and <tickets> must be zero or positive.")

    _assert_demo_database()
    _clear_seeded_data(conn)

    summary = {"users": 0, "tickets_by_status": {status: 0 for status in STATUS_PATHS}}

    for i in range(1, num_users + 1):
        user_id = _create_demo_user(conn, i)
        summary["users"] += 1

        ticket_count = random.randint(1, num_tickets) if num_tickets > 0 else 0
        for _ in range(ticket_count):
            status = _create_demo_ticket(conn, user_id)
            summary["tickets_by_status"][status] += 1

    return summary
