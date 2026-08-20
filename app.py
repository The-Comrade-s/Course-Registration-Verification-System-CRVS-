"""
Course Registration Verification System (CRVS)
Main Streamlit application entry point.

This module is intentionally thin: it wires together session state,
theming, database initialization, navigation and page routing. Actual
page content lives in the pages/ package, and business logic lives in
the services/ package.
"""

from __future__ import annotations

import streamlit as st

from auth.authentication import logout
from auth.authorization import can_access
from auth.session import get_current_role, get_current_user, init_session_state, is_authenticated
from config import settings
from database.connection import init_db
from database.seed import run_seed
from utils.logging_config import get_logger
from utils.theme import apply_theme, theme_toggle_control
from utils.ui_components import render_footer_identity

logger = get_logger("app")


PAGE_REGISTRY: dict[str, dict[str, str]] = {
    "Dashboard": {"module": "app_pages.dashboard", "icon": "dashboard"},
    "Students": {"module": "app_pages.students", "icon": "students"},
    "Courses": {"module": "app_pages.courses", "icon": "courses"},
    "Programmes": {"module": "app_pages.programmes", "icon": "programmes"},
    "Course Registration": {"module": "app_pages.registration", "icon": "registration"},
    "Verification": {"module": "app_pages.verification", "icon": "verification"},
    "Reports": {"module": "app_pages.reports", "icon": "reports"},
    "Administration": {"module": "app_pages.administration", "icon": "administration"},
    "Settings": {"module": "app_pages.settings", "icon": "settings"},
}


def _configure_page() -> None:
    st.set_page_config(
        page_title=settings.app.app_name,
        layout=settings.ui.page_layout,
        initial_sidebar_state="expanded",
    )


def _initialize_backend() -> None:
    """Run one-time backend initialization for this process."""
    if not st.session_state.get("_backend_initialized", False):
        try:
            init_db()
            run_seed()
        except Exception:
            logger.exception("Failed to initialize the database on startup.")
        st.session_state["_backend_initialized"] = True


def _render_sidebar() -> str:
    """Render the sidebar and return the selected page key."""
    st.sidebar.markdown(
        f"""
        <div style="padding: 0.5rem 0 1rem 0;">
            <div style="font-size:1.15rem; font-weight:700; color: var(--crvs-text-primary);">
                {settings.app.app_name}
            </div>
            <div style="font-size:0.78rem; color: var(--crvs-text-secondary);">
                {settings.app.app_abbreviation} &middot; Institutional Administration
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_authenticated():
        user = get_current_user() or {}
        st.sidebar.markdown(
            f"""
            <div style="padding: 0.6rem 0.75rem; margin-bottom: 0.75rem;
                        background-color: var(--crvs-surface);
                        border: 1px solid var(--crvs-border); border-radius: 6px;">
                <div style="font-weight:600; color: var(--crvs-text-primary);">
                    {user.get('full_name', 'User')}
                </div>
                <div style="font-size:0.78rem; color: var(--crvs-text-secondary);">
                    {user.get('role', 'Unassigned Role')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    selection = "Dashboard"
    if is_authenticated():
        visible_pages = [key for key in PAGE_REGISTRY if can_access(key)]
        selection = st.sidebar.radio(
            "Navigation",
            visible_pages,
            label_visibility="collapsed",
        )

    st.sidebar.markdown("---")
    theme_toggle_control()

    if is_authenticated():
        if st.sidebar.button("Log Out", use_container_width=True):
            logout()
            st.rerun()

    render_footer_identity()
    return selection


def _render_current_page(selection: str) -> None:
    if not is_authenticated():
        from app_pages import login

        login.render()
        return

    import importlib

    page_info = PAGE_REGISTRY.get(selection)
    if page_info is None:
        st.error("The requested page could not be found.")
        return

    page_module = importlib.import_module(page_info["module"])
    page_module.render()


def main() -> None:
    _configure_page()
    init_session_state()
    apply_theme()
    _initialize_backend()

    selection = _render_sidebar()
    _render_current_page(selection)


if __name__ == "__main__":
    main()
