"""Create Ticket, Ticket Detail, and Ticket List screens (specs/tickets.md,
specs/status-workflow.md, specs/list-search.md)."""
import streamlit as st

from common import design, session
from common.db import get_connection
from features.tickets.service import (
    ALLOWED_TRANSITIONS,
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    TicketError,
    TicketPermissionError,
    TransitionError,
    create_ticket,
    get_ticket_activity,
    get_ticket_by_number,
    list_tickets,
    transition_status,
    update_ticket_field,
)

_ALL_OPTION = "All"


def render_create_ticket_page():
    user = session.require_auth()
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>Create Ticket</h1>", unsafe_allow_html=True)

    with st.form("create_ticket_form"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        category = st.selectbox("Category", CATEGORIES)
        priority = st.selectbox("Priority", PRIORITIES)
        submitted = st.form_submit_button("Create Ticket", type="primary")

    if not submitted:
        return

    conn = get_connection()
    try:
        ticket = create_ticket(conn, user["id"], title, description, category, priority)
    except TicketError as exc:
        st.error(str(exc))
    else:
        st.success(f"Ticket {ticket['ticket_number']} created.")
    finally:
        conn.close()


def render_ticket_detail_page():
    user = session.require_auth()
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>Ticket Detail</h1>", unsafe_allow_html=True)

    with st.form("lookup_ticket_form"):
        ticket_number = st.text_input(
            "Ticket number", value=st.session_state.get("ticket_detail_number", "")
        )
        lookup_submitted = st.form_submit_button("View")

    if lookup_submitted:
        st.session_state["ticket_detail_number"] = ticket_number.strip()

    ticket_number = st.session_state.get("ticket_detail_number", "")
    if not ticket_number:
        return

    conn = get_connection()
    try:
        ticket = get_ticket_by_number(conn, ticket_number, user["id"])
        if ticket is None:
            st.error(f"No ticket {ticket_number} found for your account.")
            return

        st.subheader(f"{ticket['ticket_number']} — {ticket['title']}")
        st.write(ticket["description"])
        st.write(f"Status: **{ticket['status']}**")

        next_statuses = sorted(ALLOWED_TRANSITIONS.get(ticket["status"], set()))
        if next_statuses:
            with st.form("transition_form"):
                new_status = st.selectbox("Move to", next_statuses)
                transition_submitted = st.form_submit_button("Update Status", type="primary")
            if transition_submitted:
                try:
                    transition_status(conn, ticket["id"], user["id"], new_status)
                except (TransitionError, TicketPermissionError) as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Status updated to {new_status}.")
                    st.rerun()
        else:
            st.info("No further status transitions are available.")

        with st.form("field_update_form"):
            category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(ticket["category"]))
            priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(ticket["priority"]))
            field_submitted = st.form_submit_button("Save Changes")
        if field_submitted:
            changed = False
            try:
                if category != ticket["category"]:
                    update_ticket_field(conn, ticket["id"], user["id"], "category", category)
                    changed = True
                if priority != ticket["priority"]:
                    update_ticket_field(conn, ticket["id"], user["id"], "priority", priority)
                    changed = True
            except (TicketError, TicketPermissionError) as exc:
                st.error(str(exc))
            else:
                if changed:
                    st.success("Ticket updated.")
                    st.rerun()
                else:
                    st.info("No changes to save.")

        st.subheader("Activity History")
        for row in get_ticket_activity(conn, ticket["id"], user["id"]):
            detail = (
                f" ({row['field_changed']}: {row['old_value']} → {row['new_value']})"
                if row["field_changed"]
                else ""
            )
            st.write(f"{row['created_at']} — **{row['actor_username']}** {row['action']}{detail}")
    finally:
        conn.close()


def render_ticket_list_page():
    user = session.require_auth()
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>Ticket List</h1>", unsafe_allow_html=True)

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

    if not tickets:
        st.info("No tickets match the current filters.")
        return

    st.dataframe(
        [
            {
                "Ticket": t["ticket_number"],
                "Title": t["title"],
                "Status": t["status"],
                "Priority": t["priority"],
                "Category": t["category"],
                "Created": t["created_at"],
            }
            for t in tickets
        ],
        use_container_width=True,
        hide_index=True,
    )
