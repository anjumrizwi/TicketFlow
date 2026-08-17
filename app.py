"""TicketFlow entrypoint. Gates on auth, then routes to each feature once
its own spec is approved and implemented."""

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from common import design, session
from common.db import get_connection, init_schema
from features.auth.ui import render_auth_page, render_logout_button
from features.chat.ui import render_chat_page
from features.dashboard.ui import render_dashboard_page
from features.reports.ui import render_reports_page
from features.tickets.ui import (
    render_create_ticket_page,
    render_ticket_detail_page,
    render_ticket_list_page,
)

st.set_page_config(page_title="TicketFlow", layout="wide")


@st.cache_resource
def _ensure_schema():
    conn = get_connection()
    try:
        init_schema(conn)
    finally:
        conn.close()


_ensure_schema()

if not session.is_authenticated():
    render_auth_page()
else:
    design.inject_global_css()
    render_logout_button()
    user = session.current_user()

    # A Quick Action button can't set st.session_state["nav_page"] directly
    # once the radio widget below is instantiated with that key (Streamlit
    # forbids modifying a widget's bound state after creation). It instead
    # stages the target page here, applied before the radio is created.
    pending_nav = st.session_state.pop("_pending_nav", None)
    if pending_nav is not None:
        st.session_state["nav_page"] = pending_nav

    page = st.sidebar.radio(
        "Navigate",
        [
            "Home",
            "Create Ticket",
            "Ticket List",
            "Ticket Detail",
            "Reports",
            "Chat Assistant",
        ],
        key="nav_page",
    )

    if page == "Create Ticket":
        render_create_ticket_page()
    elif page == "Ticket List":
        render_ticket_list_page()
    elif page == "Ticket Detail":
        render_ticket_detail_page()
    elif page == "Reports":
        render_reports_page()
    elif page == "Chat Assistant":
        render_chat_page()
    else:
        render_dashboard_page()
