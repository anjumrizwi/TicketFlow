"""Login/register/logout screens for the auth feature (specs/auth.md)."""
import streamlit as st

from common import design, session
from common.db import get_connection
from features.auth.service import AuthError, authenticate_user, register_user


def render_auth_page():
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>TicketFlow</h1>", unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["Log in", "Register"])
    with login_tab:
        _render_login_form()
    with register_tab:
        _render_register_form()


def _render_login_form():
    with st.form("login_form"):
        identifier = st.text_input("Username or email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if not submitted:
        return

    conn = get_connection()
    try:
        user = authenticate_user(conn, identifier, password)
    except AuthError as exc:
        st.error(str(exc))
    else:
        session.login(user)
        st.rerun()
    finally:
        conn.close()


def _render_register_form():
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register", type="primary")

    if not submitted:
        return

    conn = get_connection()
    try:
        user = register_user(conn, username, email, password)
    except AuthError as exc:
        st.error(str(exc))
    else:
        session.login(user)
        st.success("Account created.")
        st.rerun()
    finally:
        conn.close()


def render_logout_button():
    if st.sidebar.button("Log out"):
        session.logout()
        st.rerun()
