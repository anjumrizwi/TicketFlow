"""Ticket creation, status-transition, field-update, and list/search logic
(specs/tickets.md, specs/status-workflow.md, specs/list-search.md).

FR-TKT-01..05, BR-01 (new ticket starts OPEN).
FR-STAT-01..06, BR-02/BR-03 (legal transitions, CLOSED is terminal),
BR-04/FR-STAT-05 (every change writes exactly one activity row, in the
same transaction as the change, rolled back together on failure), BR-05
(a user may only modify a ticket they are requester or assignee for).
FR-LIST-01..05 (composable status/priority/category/date filters plus
free-text search, always scoped to the user as requester or assignee).
"""
PRIORITIES = ("LOW", "MEDIUM", "HIGH", "URGENT")
CATEGORIES = ("Bug", "Feature Request", "Access", "Hardware", "How-to / Other")
STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")

ALLOWED_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS"},
    "IN_PROGRESS": {"RESOLVED"},
    "RESOLVED": {"CLOSED", "IN_PROGRESS"},
    "CLOSED": set(),
}

# Only these two fixed-set fields are editable post-creation per FR-STAT-03;
# used as a validated allowlist before building column names into SQL below
# (the column name itself can't be a bind parameter, so it must come only
# from this hardcoded dict, never from caller input).
FIELD_VALIDATORS = {
    "priority": PRIORITIES,
    "category": CATEGORIES,
}

TICKET_COLUMNS = (
    "id, ticket_number, requester_id, assignee_id, title, description, "
    "category, priority, status, created_at, updated_at"
)


class TicketError(Exception):
    """Raised for invalid ticket input or a ticket that doesn't exist."""


class TransitionError(Exception):
    """Raised for an illegal status transition (BR-02/BR-03)."""


class TicketPermissionError(Exception):
    """Raised when the actor is not the ticket's requester or assignee (BR-05)."""


def _require_non_empty(value, field_name):
    if not value or not value.strip():
        raise TicketError(f"{field_name} is required.")


def _require_owner(row, actor_id):
    if actor_id not in (row["requester_id"], row["assignee_id"]):
        raise TicketPermissionError(
            "You cannot modify a ticket you are not the requester or assignee for."
        )


def create_ticket(conn, requester_id, title, description, category, priority):
    """Create a ticket owned by `requester_id`. Raises TicketError on invalid input."""
    _require_non_empty(title, "Title")
    _require_non_empty(description, "Description")

    if category not in CATEGORIES:
        raise TicketError("Category must be one of: " + ", ".join(CATEGORIES))
    if priority not in PRIORITIES:
        raise TicketError("Priority must be one of: " + ", ".join(PRIORITIES))

    title = title.strip()
    description = description.strip()

    with conn.cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO tickets "
                "(requester_id, title, description, category, priority, status) "
                "VALUES (%s, %s, %s, %s, %s, 'OPEN')",
                (requester_id, title, description, category, priority),
            )
            ticket_id = cur.lastrowid
            ticket_number = f"TCK-{ticket_id:06d}"

            cur.execute(
                "UPDATE tickets SET ticket_number = %s WHERE id = %s",
                (ticket_number, ticket_id),
            )
            cur.execute(
                "INSERT INTO ticket_activity "
                "(ticket_id, actor_id, action, field_changed, old_value, new_value) "
                "VALUES (%s, %s, 'CREATED', NULL, NULL, %s)",
                (ticket_id, requester_id, "OPEN"),
            )
            cur.execute(f"SELECT {TICKET_COLUMNS} FROM tickets WHERE id = %s", (ticket_id,))
            ticket = cur.fetchone()
        except Exception:
            conn.rollback()
            raise

    conn.commit()
    return ticket


def transition_status(conn, ticket_id, actor_id, new_status):
    """Move a ticket to `new_status` if the actor owns it (BR-05) and the
    transition is legal (BR-02, BR-03), writing exactly one activity row
    in the same transaction as the status change (FR-STAT-05)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, requester_id, assignee_id FROM tickets WHERE id = %s",
            (ticket_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise TicketError("Ticket not found.")

        _require_owner(row, actor_id)

        current_status = row["status"]
        if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
            raise TransitionError(f"Cannot transition from {current_status} to {new_status}.")

        try:
            cur.execute(
                "UPDATE tickets SET status = %s WHERE id = %s",
                (new_status, ticket_id),
            )
            cur.execute(
                "INSERT INTO ticket_activity "
                "(ticket_id, actor_id, action, field_changed, old_value, new_value) "
                "VALUES (%s, %s, 'STATUS_CHANGE', 'status', %s, %s)",
                (ticket_id, actor_id, current_status, new_status),
            )
        except Exception:
            conn.rollback()
            raise

    conn.commit()


def update_ticket_field(conn, ticket_id, actor_id, field, new_value):
    """Update a permitted ticket field (priority or category) if the actor
    owns the ticket (BR-05), writing exactly one activity row in the same
    transaction as the field change (FR-STAT-03/04/05). A no-op update
    (new value equal to current) writes nothing, since BR-04 covers actual
    changes, not resubmission of the same value."""
    if field not in FIELD_VALIDATORS:
        raise TicketError(f"Field '{field}' cannot be updated.")
    if new_value not in FIELD_VALIDATORS[field]:
        raise TicketError(f"{field.capitalize()} must be one of: " + ", ".join(FIELD_VALIDATORS[field]))

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {field}, requester_id, assignee_id FROM tickets WHERE id = %s",
            (ticket_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise TicketError("Ticket not found.")

        _require_owner(row, actor_id)

        old_value = row[field]
        if old_value == new_value:
            return

        try:
            cur.execute(
                f"UPDATE tickets SET {field} = %s WHERE id = %s",
                (new_value, ticket_id),
            )
            cur.execute(
                "INSERT INTO ticket_activity "
                "(ticket_id, actor_id, action, field_changed, old_value, new_value) "
                "VALUES (%s, %s, 'FIELD_UPDATE', %s, %s, %s)",
                (ticket_id, actor_id, field, old_value, new_value),
            )
        except Exception:
            conn.rollback()
            raise

    conn.commit()


def get_ticket(conn, ticket_id, user_id):
    """Fetch a ticket scoped to the user as requester or assignee (BR-05)."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {TICKET_COLUMNS} FROM tickets "
            "WHERE id = %s AND (requester_id = %s OR assignee_id = %s)",
            (ticket_id, user_id, user_id),
        )
        return cur.fetchone()


def get_ticket_by_number(conn, ticket_number, user_id):
    """Fetch a ticket by its human-facing number, scoped to the user as
    requester or assignee (BR-05)."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {TICKET_COLUMNS} FROM tickets "
            "WHERE ticket_number = %s AND (requester_id = %s OR assignee_id = %s)",
            (ticket_number, user_id, user_id),
        )
        return cur.fetchone()


def list_tickets(
    conn,
    user_id,
    status=None,
    priority=None,
    category=None,
    date_from=None,
    date_to=None,
    search=None,
):
    """Return the user's tickets (requester or assignee), newest first,
    narrowed by any combination of the given filters/search — filters
    intersect (AND), and search composes with them rather than replacing
    them (FR-LIST-01..05, BR-05). Omit a filter (leave it None) to not
    narrow by it; call with no filters to get the full user-scoped list.
    """
    clauses = ["(requester_id = %s OR assignee_id = %s)"]
    params = [user_id, user_id]

    if status is not None:
        clauses.append("status = %s")
        params.append(status)
    if priority is not None:
        clauses.append("priority = %s")
        params.append(priority)
    if category is not None:
        clauses.append("category = %s")
        params.append(category)
    if date_from is not None:
        clauses.append("DATE(created_at) >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("DATE(created_at) <= %s")
        params.append(date_to)
    if search:
        clauses.append("(title LIKE %s OR description LIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])

    where = " AND ".join(clauses)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {TICKET_COLUMNS} FROM tickets WHERE {where} "
            "ORDER BY created_at DESC, id DESC",
            params,
        )
        return cur.fetchall()


def get_ticket_activity(conn, ticket_id, user_id):
    """Return a ticket's activity rows newest-first (FR-STAT-06), scoped to
    the user as requester or assignee (BR-05). Empty if the ticket doesn't
    exist or isn't the user's."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM tickets WHERE id = %s AND (requester_id = %s OR assignee_id = %s)",
            (ticket_id, user_id, user_id),
        )
        if cur.fetchone() is None:
            return []

        cur.execute(
            "SELECT ta.id, ta.actor_id, u.username AS actor_username, ta.action, "
            "ta.field_changed, ta.old_value, ta.new_value, ta.created_at "
            "FROM ticket_activity ta JOIN users u ON u.id = ta.actor_id "
            "WHERE ta.ticket_id = %s ORDER BY ta.created_at DESC, ta.id DESC",
            (ticket_id,),
        )
        return cur.fetchall()
