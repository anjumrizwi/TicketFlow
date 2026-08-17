"""Chat Assistant screen (specs/chat-assistant.md) — messaging-app style
per BRD §12.3: right-aligned green user bubbles, left-aligned white
bubbles with a purple border for the assistant, black text throughout,
a fixed input bar, and a visible "Clear chat" control."""

import html

import streamlit as st

from common import design, session
from common.db import get_connection
from features.chat.service import ask, classify_chat_exception, log_chat_error

HISTORY_KEY = "chat_history"


def _render_bubble(role, content):
    safe_content = html.escape(content).replace("\n", "<br>")
    if role == "user":
        st.markdown(
            f"""
            <div style="display:flex; justify-content:flex-end; margin:6px 0;">
              <div style="background:{design.COLOR_GREEN}; color:#000000; padding:10px 14px;
                          border-radius:14px; max-width:70%; white-space:pre-wrap;">
                {safe_content}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="display:flex; justify-content:flex-start; margin:6px 0;">
              <div style="background:#FFFFFF; color:#000000; padding:10px 14px;
                          border-radius:14px; max-width:70%; white-space:pre-wrap;
                          border:2px solid {design.COLOR_PURPLE};">
                {safe_content}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_page():
    user = session.require_auth()
    design.inject_global_css()
    st.markdown("<h1 class='brand-header'>Chat Assistant</h1>", unsafe_allow_html=True)

    if st.sidebar.button("Clear chat"):
        st.session_state[HISTORY_KEY] = []
        st.rerun()

    history = st.session_state.setdefault(HISTORY_KEY, [])

    for message in history:
        _render_bubble(message["role"], message["content"])

    question = st.chat_input("Ask about your tickets…")
    if not question:
        return

    _render_bubble("user", question)

    history.append({"role": "user", "content": question})

    error_detail = None
    conn = None
    with st.spinner("Assistant is typing…"):
        try:
            conn = get_connection()
            result = ask(
                question,
                user["id"],
                [(m["role"], m["content"]) for m in history[:-1]],
                conn,
            )
            answer = result["answer"]
            if result["failed"]:
                error_detail = (
                    "SQL_VALIDATION",
                    result.get("validation_error")
                    or "The assistant could not generate a safe query.",
                )
        except Exception as exc:
            # Boundary to an external, unreliable third-party service (missing/
            # invalid OPENAI_API_KEY, network failure, rate limit, etc.) — never
            # let that surface as a raw traceback, and never touch any data
            # before this point since `ask()` only executes a query it has
            # already validated as safe. `get_connection()` itself failing
            # lands here too (AC-7): `conn` stays None, so nothing below
            # tries to log through it or close it.
            answer = (
                "The assistant is temporarily unavailable. Please try again shortly."
            )
            error_detail = classify_chat_exception(exc)
        finally:
            if conn is not None:
                if error_detail is not None:
                    # Never lets a logging failure break the chat turn (AC-7) —
                    # log_chat_error swallows its own DB errors.
                    log_chat_error(conn, user["id"], error_detail[0], error_detail[1])
                conn.close()

    history.append({"role": "assistant", "content": answer})
    _render_bubble("assistant", answer)
    if error_detail is not None:
        error_type, error_message = error_detail
        with st.expander("Error details"):
            st.write(f"**Type:** {error_type}")
            st.write(f"**Message:** {error_message}")
