"""
Students page.

Administrators and academic officers manage student records. A student
account itself never sees this page (their profile lives on Settings /
Dashboard) -- the navigation already hides this entry from that role.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, current_user_id, require_role
from database.connection import session_scope
from database.models import Department, Level, Programme, Student, User, UserRole
from services import audit_service
from utils.error_handling import safe_page
from utils.security import hash_password
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, success_message
from utils.validators import is_non_empty, is_valid_email


@safe_page
@require_role(ADMINISTRATOR, ACADEMIC_OFFICER)
def render() -> None:
    page_header("Students", "Manage student records.")

    with session_scope() as session:
        students = session.query(Student).order_by(Student.matric_number).all()
        rows = [
            {
                "Matric Number": s.matric_number,
                "Name": s.user.full_name,
                "Programme": s.programme.name,
                "Level": s.level.name,
                "Status": s.academic_status,
                "Active": "Yes" if s.is_active else "No",
            }
            for s in students
        ]

    if rows:
        data_table(rows)
    else:
        empty_state("No students have been added yet.")

    section_header("Add Student")
    with session_scope() as session:
        department_options = {d.name: d.id for d in session.query(Department).order_by(Department.name).all()}
        programme_options = {p.name: p.id for p in session.query(Programme).order_by(Programme.name).all()}
        level_options = {l.name: l.id for l in session.query(Level).order_by(Level.numeric_value).all()}

    if not (department_options and programme_options and level_options):
        st.caption("Create at least one department, programme and level before adding students.")
        return

    with st.form("create_student_form", clear_on_submit=True):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        matric_number = st.text_input("Matriculation Number")
        department_name = st.selectbox("Department", list(department_options.keys()))
        programme_name = st.selectbox("Programme", list(programme_options.keys()))
        level_name = st.selectbox("Level", list(level_options.keys()))
        admission_year = st.number_input("Admission Year", min_value=2000, max_value=2100, value=2025)
        password = st.text_input("Initial Password", type="password")
        submitted = st.form_submit_button("Add Student")

    if submitted:
        if not (is_non_empty(full_name) and is_valid_email(email) and is_non_empty(matric_number) and is_non_empty(password)):
            error_message("Please complete all required fields with a valid email and password.")
        else:
            created = False
            with session_scope() as session:
                if session.query(User).filter(User.email == email.strip().lower()).one_or_none():
                    error_message("A user with this email already exists.")
                elif session.query(Student).filter(Student.matric_number == matric_number.strip().upper()).one_or_none():
                    error_message("A student with this matriculation number already exists.")
                else:
                    user = User(
                        full_name=full_name.strip(),
                        email=email.strip().lower(),
                        password_hash=hash_password(password),
                        role=UserRole.STUDENT,
                    )
                    session.add(user)
                    session.flush()
                    student = Student(
                        matric_number=matric_number.strip().upper(),
                        user_id=user.id,
                        department_id=department_options[department_name],
                        programme_id=programme_options[programme_name],
                        level_id=level_options[level_name],
                        admission_year=int(admission_year),
                    )
                    session.add(student)
                    session.flush()
                    audit_service.record(session, current_user_id(), "STUDENT_CREATED", "Student", student.id)
                    created = True
            if created:
                success_message(f"Student '{full_name}' added.")
                st.rerun()

    section_header("Activate / Deactivate Student")
    with session_scope() as session:
        student_options = {f"{s.matric_number} - {s.user.full_name}": s.id for s in session.query(Student).all()}
    if student_options:
        selection = st.selectbox("Select Student", list(student_options.keys()))
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Activate", key="activate_student", use_container_width=True):
                _set_student_active(student_options[selection], True)
                st.rerun()
        with col_b:
            if st.button("Deactivate", key="deactivate_student", use_container_width=True):
                _set_student_active(student_options[selection], False)
                st.rerun()


def _set_student_active(student_id: int, active: bool) -> None:
    with session_scope() as session:
        student = session.get(Student, student_id)
        if student is not None:
            student.is_active = active
            audit_service.record(session, current_user_id(), "STUDENT_STATUS_CHANGED", "Student", student.id, details=str(active))
