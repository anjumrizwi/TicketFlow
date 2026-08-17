"""Reports screen: filter tickets, then export the filtered set
(specs/reports-export.md). Mirrors the Ticket List filters exactly, since
the export must reflect precisely what's currently filtered — no separate
query logic (FR-EXP-03)."""
import streamlit as st

from common import design, session
from common.db import get_connection
from features.reports.service import generate_csv, generate_pdf
from features.tickets.service import CATEGORIES, PRIORITIES, STATUSES, list_tickets

_ALL_OPTION = "All"


def render_reports_page():
    user = session.require_auth()
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>Reports</h1>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    status = col1.selectbox("Status", [_ALL_OPTION, *STATUSES])
    priority = col2.selectbox("Priority", [_ALL_OPTION, *PRIORITIES])
    category = col3.selectbox("Category", [_ALL_OPTION, *CATEGORIES])

    col4, col5 = st.columns(2)
    date_from = col4.date_input("Created from", value=None)
    date_to = col5.date_input("Created to", value=None)

    search = st.text_input("Search title/description")

    conn = get_connection()
    try:
        tickets = list_tickets(
            conn,
            user["id"],
            status=None if status == _ALL_OPTION else status,
            priority=None if priority == _ALL_OPTION else priority,
            category=None if category == _ALL_OPTION else category,
            date_from=date_from or None,
            date_to=date_to or None,
            search=search.strip() or None,
        )
    finally:
        conn.close()

    st.write(f"{len(tickets)} ticket(s) match the current filters.")

    col_csv, col_pdf = st.columns(2)
    col_csv.download_button(
        "Download CSV",
        data=generate_csv(tickets, user["id"]),
        file_name="tickets.csv",
        mime="text/csv",
    )
    col_pdf.download_button(
        "Download PDF",
        data=generate_pdf(tickets, user["id"]),
        file_name="tickets.pdf",
        mime="application/pdf",
    )
