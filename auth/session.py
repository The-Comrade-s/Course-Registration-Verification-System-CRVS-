"""
Streamlit session-state helpers for the authentication foundation.

CRVS-001 defines the session-state contract that CRVS-002's full
authentication and RBAC implementation will populate. No real login
happens here; this module only defines a clean, consistent shape for
"who is logged in" so the rest of the application can be written against
a stable interface from day one.

Session-state keys used:
    is_authenticated : bool
    current_user      : dict | None   (id, full_name, email, role, ...)
    theme              : "light" | "dark"
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st


def init_session_state() -> None:
    """Ensure every session-state key this application relies on exists."""
    st.session_state.setdefault("is_authenticated", False)
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("theme", "light")


def is_authenticated() -> bool:
    """Return whether a user is currently authenticated in this session."""
    return bool(st.session_state.get("is_authenticated", False))


def get_current_user() -> Optional[dict[str, Any]]:
    """Return the current user's session record, or None if not logged in."""
    return st.session_state.get("current_user")


def get_current_role() -> Optional[str]:
    """Return the current user's role, or None if not logged in."""
    user = get_current_user()
    return user.get("role") if user else None


def set_current_user(user: dict[str, Any]) -> None:
    """
    Mark the session as authenticated for the given user record.

    Called by the real authentication implementation in CRVS-002.
    """
    st.session_state["is_authenticated"] = True
    st.session_state["current_user"] = user


def clear_session() -> None:
    """Clear authentication state, logging the current user out."""
    st.session_state["is_authenticated"] = False
    st.session_state["current_user"] = None


def get_theme() -> str:
    return st.session_state.get("theme", "light")


def set_theme(theme: str) -> None:
    if theme in ("light", "dark"):
        st.session_state["theme"] = theme
