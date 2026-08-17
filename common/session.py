"""Streamlit session-state helpers shared by every feature.

FR-AUTH-06: ticket, reporting, and chat pages must call `require_auth()`
before touching any data.
"""
import streamlit as st

SESSION_USER_KEY = "auth_user"


def login(user):
    st.session_state[SESSION_USER_KEY] = user


def logout():
    st.session_state.pop(SESSION_USER_KEY, None)


def current_user():
    return st.session_state.get(SESSION_USER_KEY)


def is_authenticated():
    return current_user() is not None


def require_auth():
    """Stop rendering the page if there is no active session.

    Call this first, before any query, on every ticket/report/chat page.
    """
    if not is_authenticated():
        st.warning("Please log in to continue.")
        st.stop()
    return current_user()
