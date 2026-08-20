"""
Course Registration page.

Students select courses relevant to their programme/level/session/
semester, build a draft registration, and submit it. Academic officers
and administrators can review submitted registrations for their
authorized scope from the same page.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, STUDENT, current_student_id, get_current_role, require_authentication
from database.connection import session_scope
from database.models import AcademicSession, Registration, RegistrationStatus, Semester, Student
from services import registration_service
from utils.error_handling import safe_page
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, status_badge, success_message


_STATUS_SEVERITY = {
    RegistrationStatus.DRAFT: "neutral",
    RegistrationStatus.SUBMITTED: "warning",
    RegistrationStatus.UNDER_REVIEW: "warning",
    RegistrationStatus.REQUIRES_CORRECTION: "error",
    RegistrationStatus.APPROVED: "success",
    RegistrationStatus.REJECTED: "error",
}


@safe_page
@require_authentication
def render() -> None:
    page_header("Course Registration", "Register courses for the current academic session.")

    role = get_current_role()
    if role == STUDENT:
        _render_student_view()
    elif role in (ADMINISTRATOR, ACADEMIC_OFFICER):
        _render_staff_view()


def _render_student_view() -> None:
    with session_scope() as session:
        student_id = current_student_id(session)
        if student_id is None:
            error_message("No student profile is linked to this account.")
            return

        student = session.get(Student, student_id)
        current_session = session.query(AcademicSession).filter(AcademicSession.is_current.is_(True)).one_or_none()
        if current_session is None:
            empty_state("No academic session is currently marked as active. Contact an administrator.")
            return

        current_semester = (
            session.query(Semester)
            .filter(Semester.academic_session_id == current_session.id, Semester.is_current.is_(True))
            .one_or_none()
        )
        if current_semester is None:
            empty_state("No semester is currently marked as active. Contact an administrator.")
            return

        registration = registration_service.get_or_create_draft(session, student.id, current_session.id, current_semester.id)
        registration_id = registration.id
        status = registration.status
        available_courses = registration_service.get_available_courses(session, student, current_session.id, current_semester.id)
        selected_course_ids = {rc.course_id for rc in registration.courses}
        selected_rows = [
            {"Code": rc.course.code, "Title": rc.course.title, "Units": rc.credit_units}
            for rc in registration.courses
        ]
        total_units = sum(rc.credit_units for rc in registration.courses)

    st.caption(f"Session: {current_session.name}  |  Semester: {current_semester.name}")
    st.markdown(status_badge(status.value, _STATUS_SEVERITY.get(status, "neutral")), unsafe_allow_html=True)

    if status not in (RegistrationStatus.DRAFT, RegistrationStatus.REQUIRES_CORRECTION):
        section_header("Your Registration")
        if selected_rows:
            data_table(selected_rows)
        st.caption(f"Total Units: {total_units}")
        empty_state("This registration has already been submitted and can no longer be edited here.")
        return

    section_header("Available Courses")
    if not available_courses:
        empty_state("No courses are currently configured for your programme, level, session and semester.")
        return

    search = st.text_input("Search by course code or title", key="course_search")
    for course in available_courses:
        if search and search.lower() not in course.code.lower() and search.lower() not in course.title.lower():
            continue
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{course.code}** &mdash; {course.title} ({course.credit_units} units)")
        with col2:
            if course.id in selected_course_ids:
                if st.button("Remove", key=f"remove_{course.id}"):
                    with session_scope() as session:
                        reg = session.get(Registration, registration_id)
                        registration_service.remove_course(session, reg, course.id)
                    st.rerun()
            else:
                if st.button("Add", key=f"add_{course.id}"):
                    with session_scope() as session:
                        reg = session.get(Registration, registration_id)
                        try:
                            registration_service.add_course(session, reg, course)
                        except registration_service.RegistrationError as exc:
                            error_message(str(exc))
                    st.rerun()

    section_header("Registration Summary")
    if selected_rows:
        data_table(selected_rows)
    else:
        empty_state("No courses selected yet.")
    st.caption(f"Total Registered Units: {total_units}")

    if st.button("Submit Registration", type="primary"):
        with session_scope() as session:
            reg = session.get(Registration, registration_id)
            try:
                registration_service.submit_registration(session, reg)
                success_message("Registration submitted. It will now be verified.")
            except registration_service.RegistrationError as exc:
                error_message(str(exc))
        st.rerun()


def _render_staff_view() -> None:
    section_header("Submitted Registrations")
    with session_scope() as session:
        registrations = (
            session.query(Registration)
            .filter(Registration.status != RegistrationStatus.DRAFT)
            .order_by(Registration.submitted_at.desc())
            .all()
        )
        rows = [
            {
                "Student ID": r.student.matric_number,
                "Student": r.student.user.full_name,
                "Programme": r.student.programme.name,
                "Level": r.student.level.name,
                "Session": r.academic_session.name,
                "Semester": r.semester.name,
                "Courses": len(r.courses),
                "Status": r.status.value,
            }
            for r in registrations
        ]
    if rows:
        data_table(rows)
    else:
        empty_state("No registrations have been submitted yet.")
    st.caption("Open the Verification page to review, verify and approve individual registrations.")
