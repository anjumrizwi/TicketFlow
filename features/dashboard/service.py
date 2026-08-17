"""Dashboard summary data: status counts and recent tickets
(specs/dashboard.md).

FR-DASH-02..03, BR-05. Reuses `list_tickets` rather than a separate query
path, so the dashboard always reflects the same live, user-scoped data as
the Ticket List page (FR-DASH-05) with no risk of the two drifting apart.
"""
from features.tickets.service import STATUSES, list_tickets

RECENT_TICKET_LIMIT = 5


def get_dashboard_data(conn, user_id):
    """Return `(counts, recent)` for `user_id`'s tickets (requester or
    assignee, BR-05): `counts` is a dict of every status to its count
    (FR-DASH-02), `recent` is the newest `RECENT_TICKET_LIMIT` tickets
    (FR-DASH-03), newest first."""
    tickets = list_tickets(conn, user_id)

    counts = {status: 0 for status in STATUSES}
    for ticket in tickets:
        counts[ticket["status"]] += 1

    return counts, tickets[:RECENT_TICKET_LIMIT]
