"""Shared design-system constants and CSS (BRD Section 12).

White background, black text, no gradients. Green = success/primary
actions. Purple = brand/headers/sidebar. Pink = accents/urgent. Kept in
one place so every feature and the ticket-export skill stay visually
consistent.
"""
import streamlit as st

COLOR_GREEN = "#00E676"
COLOR_PURPLE = "#6C3FC5"
COLOR_PINK = "#FF4FA3"
COLOR_BACKGROUND = "#FFFFFF"
COLOR_TEXT = "#000000"


def inject_global_css():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {COLOR_BACKGROUND};
            color: {COLOR_TEXT};
        }}
        h1, h2, h3, .brand-header {{
            color: {COLOR_PURPLE};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {COLOR_PURPLE};
        }}
        section[data-testid="stSidebar"] * {{
            color: #FFFFFF;
        }}
        div.stButton > button[kind="primary"] {{
            background-color: {COLOR_GREEN};
            color: {COLOR_TEXT};
            border: none;
            border-radius: 8px;
        }}
        div.stButton > button:not([kind="primary"]) {{
            border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
