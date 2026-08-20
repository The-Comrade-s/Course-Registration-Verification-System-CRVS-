"""
Authorization.

Centralized role-based access control helpers. Every sensitive page and
operation must go through these rather than re-implementing role checks
locally. Navigation visibility is a convenience only -- every underlying
service call also re-checks permissions before touching the database.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable

import streamlit as st

from auth.session import get_current_role, get_current_user, is_authenticated
from utils.logging_config import get_logger

logger = get_logger("auth.authorization")

ADMINISTRATOR = "Administrator"
ACADEMIC_OFFICER = "Academic Officer"
STUDENT = "Student"

ALL_ROLES = (ADMINISTRATOR, ACADEMIC_OFFICER, STUDENT)
STAFF_ROLES = (ADMINISTRATOR, ACADEMIC_OFFICER)


def require_authentication(page_render_fn: Callable) -> Callable:
    @wraps(page_render_fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            st.warning("You must be logged in to view this page.")
            return None
        return page_render_fn(*args, **kwargs)

    return wrapper


def require_role(*allowed_roles: str) -> Callable:
    def decorator(page_render_fn: Callable) -> Callable:
        @wraps(page_render_fn)
        def wrapper(*args, **kwargs):
            if not is_authenticated():
                st.warning("You must be logged in to view this page.")
                return None
            role = get_current_role()
            if role not in allowed_roles:
                st.error("You do not have permission to access this page.")
                logger.info("Blocked role=%s from a page requiring roles=%s.", role, allowed_roles)
                return None
            return page_render_fn(*args, **kwargs)

        return wrapper

    return decorator


def has_permission(role: str | None, allowed_roles: Iterable[str]) -> bool:
    return role in set(allowed_roles)


def can_access(page_key: str) -> bool:
    """Determine whether the current user's role may see a navigation entry."""
    if not is_authenticated():
        return False
    role = get_current_role()
    student_only_pages = {"Course Registration", "Verification"}
    staff_only_pages = {"Students", "Staff", "Courses", "Programmes", "Administration", "Reports"}
    if role == STUDENT:
        return page_key not in staff_only_pages
    if role == ACADEMIC_OFFICER:
        return page_key != "Administration"
    if role == ADMINISTRATOR:
        return True
    return False


def current_user_id() -> int | None:
    user = get_current_user()
    return user.get("id") if user else None


def current_student_id(session) -> int | None:
    """Resolve the Student.id belonging to the current logged-in user, if any."""
    from database.models import Student

    user_id = current_user_id()
    if user_id is None:
        return None
    student = session.query(Student).filter(Student.user_id == user_id).one_or_none()
    return student.id if student else None
