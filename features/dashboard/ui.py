"""Dashboard / Home screen: status counts, recent tickets, quick actions
(specs/dashboard.md)."""

import streamlit as st

from common import design, session
from common.db import get_connection
from features.dashboard.service import get_dashboard_data
from features.tickets.service import STATUSES

# Must match app.py's sidebar Navigate options exactly (FR-DASH-04).
_QUICK_ACTIONS = ("Create Ticket", "Ticket List", "Reports", "Chat Assistant")


def render_dashboard_page():
    user = session.require_auth()
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>TicketFlow</h1>", unsafe_allow_html=True)
    st.write(f"Welcome, **{user['username']}**.")

    conn = get_connection()
    try:
        counts, recent = get_dashboard_data(conn, user["id"])
    finally:
        conn.close()

    st.subheader("Status Overview")
    for col, status in zip(st.columns(len(STATUSES)), STATUSES):
        col.metric(status.replace("_", " ").title(), counts[status])

    st.subheader("Quick Actions")
    for col, action in zip(st.columns(len(_QUICK_ACTIONS)), _QUICK_ACTIONS):
        if col.button(action, use_container_width=True):
            st.session_state["_pending_nav"] = action
            st.rerun()

    st.subheader("Recent Tickets")
    if not recent:
        st.info("No tickets yet.")
        return

    st.dataframe(
        [
            {
                "Ticket": t["ticket_number"],
                "Title": t["title"],
                "Status": t["status"],
                "Priority": t["priority"],
                "Created": t["created_at"],
            }
            for t in recent
        ],
        use_container_width=True,
        hide_index=True,
    )
