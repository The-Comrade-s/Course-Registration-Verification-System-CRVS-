"""
Login page.

CRVS-001 provides the professional login screen and wires it to the
authentication foundation. Real credential verification arrives with the
User model and password hashing in CRVS-002.
"""

from __future__ import annotations

import streamlit as st

from auth.authentication import authenticate
from config import settings
from utils.error_handling import safe_page
from utils.ui_components import warning_message


@safe_page
def render() -> None:
    st.markdown(
        f"""
        <div style="text-align:center; margin-top: 2rem; margin-bottom: 1.5rem;">
            <div style="font-size:1.6rem; font-weight:700; color: var(--crvs-text-primary);">
                {settings.app.app_name}
            </div>
            <div style="color: var(--crvs-text-secondary); font-size: 0.92rem;">
                Institutional Sign In
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 2, 1])
    with center:
        with st.form("login_form"):
            identifier = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not identifier or not password:
                warning_message("Please enter both your username/email and password.")
            else:
                result = authenticate(identifier, password)
                if result.success:
                    st.rerun()
                else:
                    warning_message(result.message)
