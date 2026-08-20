"""
Administration page.

Administrator-only. Organizes user management and academic structure
configuration (departments, programmes, levels, academic sessions,
semesters) into tabs, plus an audit log viewer.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ADMINISTRATOR, current_user_id, require_role
from database.connection import session_scope
from database.models import (
    AcademicSession,
    AuditLog,
    Department,
    Level,
    Programme,
    Semester,
    Staff,
    User,
    UserRole,
)
from services import audit_service
from utils.error_handling import safe_page
from utils.helpers import format_datetime
from utils.security import hash_password
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, success_message
from utils.validators import is_non_empty, is_valid_email


@safe_page
@require_role(ADMINISTRATOR)
def render() -> None:
    page_header("Administration", "System-wide administrative functions.")

    sections = {
        "Users": _render_users_tab,
        "Staff": _render_staff_tab,
        "Departments": _render_departments_tab,
        "Programmes": _render_programmes_tab,
        "Levels": _render_levels_tab,
        "Academic Sessions": _render_sessions_tab,
        "Semesters": _render_semesters_tab,
        "Audit Log": _render_audit_log_tab,
    }
    # A session-state-bound selector is used instead of st.tabs because
    # st.tabs has no persistence key: after a form submission triggers a
    # rerun (e.g. via st.rerun()), st.tabs silently resets to its first
    # entry, which made newly created records look like they had vanished
    # even though they were saved correctly. Binding the section choice to
    # a widget key keeps the user on the same section across reruns.
    section = st.radio(
        "Administration Section", list(sections.keys()), horizontal=True,
        key="administration_active_section", label_visibility="collapsed",
    )
    sections[section]()


def _render_users_tab() -> None:
    section_header("User Management")
    with session_scope() as session:
        users = session.query(User).order_by(User.full_name).all()
        rows = [
            {
                "Name": u.full_name,
                "Email": u.email,
                "Role": u.role.value,
                "Active": "Yes" if u.is_active else "No",
                "Last Login": format_datetime(u.last_login),
            }
            for u in users
        ]
    if rows:
        data_table(rows)
    else:
        empty_state("No users found.")

    section_header("Create User")
    with st.form("create_user_form", clear_on_submit=True):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        role = st.selectbox("Role", [r.value for r in UserRole])
        password = st.text_input("Initial Password", type="password")
        submitted = st.form_submit_button("Create User")

    if submitted:
        if not (is_non_empty(full_name) and is_valid_email(email) and is_non_empty(password)):
            error_message("Please provide a valid name, email address and password.")
        else:
            created = False
            with session_scope() as session:
                existing = session.query(User).filter(User.email == email.strip().lower()).one_or_none()
                if existing is not None:
                    error_message("A user with this email already exists.")
                else:
                    new_user = User(
                        full_name=full_name.strip(),
                        email=email.strip().lower(),
                        password_hash=hash_password(password),
                        role=UserRole(role),
                    )
                    session.add(new_user)
                    session.flush()
                    audit_service.record(session, current_user_id(), "USER_CREATED", "User", new_user.id, details=role)
                    created = True
            if created:
                success_message(f"User '{full_name}' created successfully.")
                st.rerun()

    section_header("Activate / Deactivate User")
    with session_scope() as session:
        users = session.query(User).order_by(User.full_name).all()
        user_options = {f"{u.full_name} ({u.email})": u.id for u in users}
    if user_options:
        selection = st.selectbox("Select User", list(user_options.keys()), key="toggle_user_select")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Activate", use_container_width=True):
                _set_user_active(user_options[selection], True)
                st.rerun()
        with col_b:
            if st.button("Deactivate", use_container_width=True):
                _set_user_active(user_options[selection], False)
                st.rerun()
    else:
        empty_state("No users available.")


def _set_user_active(user_id: int, active: bool) -> None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user is not None:
            user.is_active = active
            audit_service.record(session, current_user_id(), "USER_STATUS_CHANGED", "User", user.id, details=str(active))


def _render_staff_tab() -> None:
    section_header("Staff")
    with session_scope() as session:
        staff_members = session.query(Staff).order_by(Staff.staff_id).all()
        rows = [
            {
                "Staff ID": s.staff_id,
                "Name": s.user.full_name,
                "Department": s.department.name,
                "Active": "Yes" if s.is_active else "No",
            }
            for s in staff_members
        ]
        officer_users = {
            u.full_name: u.id
            for u in session.query(User).filter(User.role == UserRole.ACADEMIC_OFFICER).all()
        }
        department_options = {d.name: d.id for d in session.query(Department).order_by(Department.name).all()}

    if rows:
        data_table(rows)
    else:
        empty_state("No staff records found.")

    if not (officer_users and department_options):
        st.caption("Create an Academic Officer user and a department first.")
        return

    with st.form("create_staff_form", clear_on_submit=True):
        staff_id = st.text_input("Staff ID")
        user_name = st.selectbox("User Account", list(officer_users.keys()))
        department_name = st.selectbox("Department", list(department_options.keys()), key="staff_department")
        submitted = st.form_submit_button("Create Staff Record")

    if submitted:
        if not is_non_empty(staff_id):
            error_message("Staff ID is required.")
        else:
            created = False
            with session_scope() as session:
                if session.query(Staff).filter(Staff.staff_id == staff_id.strip().upper()).one_or_none():
                    error_message("A staff record with this ID already exists.")
                else:
                    staff = Staff(
                        staff_id=staff_id.strip().upper(),
                        user_id=officer_users[user_name],
                        department_id=department_options[department_name],
                    )
                    session.add(staff)
                    session.flush()
                    audit_service.record(session, current_user_id(), "STAFF_CREATED", "Staff", staff.id)
                    created = True
            if created:
                success_message(f"Staff record for '{user_name}' created.")
                st.rerun()


def _render_departments_tab() -> None:
    section_header("Departments")
    with session_scope() as session:
        departments = session.query(Department).order_by(Department.name).all()
        rows = [{"Name": d.name, "Code": d.code, "Active": "Yes" if d.is_active else "No"} for d in departments]
    if rows:
        data_table(rows)
    else:
        empty_state("No departments configured yet.")

    with st.form("create_department_form", clear_on_submit=True):
        name = st.text_input("Department Name")
        code = st.text_input("Department Code")
        description = st.text_area("Description", height=80)
        submitted = st.form_submit_button("Create Department")

    if submitted:
        if not (is_non_empty(name) and is_non_empty(code)):
            error_message("Department name and code are required.")
        else:
            created = False
            with session_scope() as session:
                if session.query(Department).filter(Department.code == code.strip().upper()).one_or_none():
                    error_message("A department with this code already exists.")
                else:
                    dept = Department(name=name.strip(), code=code.strip().upper(), description=description.strip() or None)
                    session.add(dept)
                    session.flush()
                    audit_service.record(session, current_user_id(), "DEPARTMENT_CREATED", "Department", dept.id)
                    created = True
            if created:
                success_message(f"Department '{name}' created.")
                st.rerun()


def _render_programmes_tab() -> None:
    section_header("Programmes")
    st.caption("Full programme management is available on the dedicated Programmes page.")


def _render_levels_tab() -> None:
    section_header("Academic Levels")
    with session_scope() as session:
        levels = session.query(Level).order_by(Level.numeric_value).all()
        rows = [{"Name": l.name, "Numeric Value": l.numeric_value, "Active": "Yes" if l.is_active else "No"} for l in levels]
    if rows:
        data_table(rows)
    else:
        empty_state("No academic levels configured yet.")

    with st.form("create_level_form", clear_on_submit=True):
        name = st.text_input("Level Name (e.g. 400 Level)")
        numeric_value = st.number_input("Numeric Value", min_value=1, step=100, value=100)
        submitted = st.form_submit_button("Create Level")

    if submitted:
        if not is_non_empty(name):
            error_message("Level name is required.")
        else:
            created = False
            with session_scope() as session:
                if session.query(Level).filter(Level.name == name.strip()).one_or_none():
                    error_message("This level already exists.")
                else:
                    level = Level(name=name.strip(), numeric_value=int(numeric_value))
                    session.add(level)
                    session.flush()
                    audit_service.record(session, current_user_id(), "LEVEL_CREATED", "Level", level.id)
                    created = True
            if created:
                success_message(f"Level '{name}' created.")
                st.rerun()


def _render_sessions_tab() -> None:
    section_header("Academic Sessions")
    with session_scope() as session:
        sessions = session.query(AcademicSession).order_by(AcademicSession.name.desc()).all()
        rows = [
            {"Session": s.name, "Current": "Yes" if s.is_current else "No", "Active": "Yes" if s.is_active else "No"}
            for s in sessions
        ]
    if rows:
        data_table(rows)
    else:
        empty_state("No academic sessions configured yet.")

    with st.form("create_session_form", clear_on_submit=True):
        name = st.text_input("Session Name (e.g. 2026/2027)")
        make_current = st.checkbox("Set as current session")
        submitted = st.form_submit_button("Create Session")

    if submitted:
        if not is_non_empty(name):
            error_message("Session name is required.")
        else:
            created = False
            with session_scope() as session:
                if session.query(AcademicSession).filter(AcademicSession.name == name.strip()).one_or_none():
                    error_message("This academic session already exists.")
                else:
                    if make_current:
                        session.query(AcademicSession).update({AcademicSession.is_current: False})
                    new_session = AcademicSession(name=name.strip(), is_current=make_current)
                    session.add(new_session)
                    session.flush()
                    audit_service.record(session, current_user_id(), "ACADEMIC_SESSION_CREATED", "AcademicSession", new_session.id)
                    created = True
            if created:
                success_message(f"Academic session '{name}' created.")
                st.rerun()


def _render_semesters_tab() -> None:
    section_header("Semesters")
    with session_scope() as session:
        semesters = session.query(Semester).order_by(Semester.id.desc()).all()
        rows = [
            {
                "Semester": s.name,
                "Session": s.academic_session.name,
                "Current": "Yes" if s.is_current else "No",
            }
            for s in semesters
        ]
        session_options = {s.name: s.id for s in session.query(AcademicSession).order_by(AcademicSession.name.desc()).all()}

    if rows:
        data_table(rows)
    else:
        empty_state("No semesters configured yet.")

    if not session_options:
        st.caption("Create an academic session before adding semesters.")
        return

    with st.form("create_semester_form", clear_on_submit=True):
        name = st.selectbox("Semester Name", ["First Semester", "Second Semester"])
        session_name = st.selectbox("Academic Session", list(session_options.keys()))
        make_current = st.checkbox("Set as current semester")
        submitted = st.form_submit_button("Create Semester")

    if submitted:
        created = False
        with session_scope() as session:
            session_id = session_options[session_name]
            existing = (
                session.query(Semester)
                .filter(Semester.name == name, Semester.academic_session_id == session_id)
                .one_or_none()
            )
            if existing:
                error_message("This semester already exists for the selected session.")
            else:
                if make_current:
                    session.query(Semester).filter(Semester.academic_session_id == session_id).update(
                        {Semester.is_current: False}
                    )
                new_semester = Semester(name=name, academic_session_id=session_id, is_current=make_current)
                session.add(new_semester)
                session.flush()
                audit_service.record(session, current_user_id(), "SEMESTER_CREATED", "Semester", new_semester.id)
                created = True
        if created:
            success_message(f"Semester '{name}' created.")
            st.rerun()


def _render_audit_log_tab() -> None:
    section_header("Audit Log")
    with session_scope() as session:
        logs = session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
        rows = [
            {
                "Timestamp": format_datetime(log.created_at),
                "User ID": log.user_id if log.user_id else "-",
                "Action": log.action,
                "Entity": f"{log.entity_type or '-'} #{log.entity_id or '-'}",
                "Details": log.details or "-",
            }
            for log in logs
        ]
    if rows:
        data_table(rows)
    else:
        empty_state("No audit records found.")
