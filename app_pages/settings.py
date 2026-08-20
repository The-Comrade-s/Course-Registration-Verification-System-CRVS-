"""
Settings page.

Personal preferences and notifications. Every authenticated role sees
their own notification center and can change their password here.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import current_user_id, require_authentication
from database.connection import session_scope
from database.models import User
from services import notification_service
from utils.error_handling import safe_page
from utils.helpers import format_datetime
from utils.security import hash_password, verify_password
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, success_message
from utils.validators import is_non_empty


@safe_page
@require_authentication
def render() -> None:
    page_header("Settings", "Personal and system preferences.")

    sections = {"Notifications": _render_notifications_tab, "Change Password": _render_password_tab}
    section = st.radio(
        "Settings Section", list(sections.keys()), horizontal=True,
        key="settings_active_section", label_visibility="collapsed",
    )
    sections[section]()


def _render_notifications_tab() -> None:
    section_header("Notifications")
    user_id = current_user_id()
    with session_scope() as session:
        notifications = notification_service.get_notifications_for_user(session, user_id)
        rows = [
            {
                "Received": format_datetime(n.created_at),
                "Type": n.notification_type.replace("_", " ").title(),
                "Message": n.message,
                "Read": "Yes" if n.is_read else "No",
            }
            for n in notifications
        ]
        unread_ids = [n.id for n in notifications if not n.is_read]

    if not rows:
        empty_state("No notifications yet.")
        return

    data_table(rows)

    if unread_ids and st.button("Mark All as Read"):
        with session_scope() as session:
            for notification_id in unread_ids:
                notification_service.mark_as_read(session, notification_id, user_id)
        st.rerun()


def _render_password_tab() -> None:
    section_header("Change Password")
    user_id = current_user_id()

    with st.form("change_password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update Password")

    if not submitted:
        return

    if not (is_non_empty(current_password) and is_non_empty(new_password)):
        error_message("Please complete all fields.")
        return
    if new_password != confirm_password:
        error_message("New password and confirmation do not match.")
        return
    if len(new_password) < 8:
        error_message("New password must be at least 8 characters long.")
        return

    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None or not verify_password(current_password, user.password_hash):
            error_message("Current password is incorrect.")
            return
        user.password_hash = hash_password(new_password)

    success_message("Password updated successfully.")
