"""
Dashboard page.

Role-specific overview built entirely from live database data. No
statistic is ever fabricated: where there is no data, an honest empty
state is shown instead.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, STUDENT, current_student_id, get_current_role, require_authentication
from auth.session import get_current_user
from database.connection import session_scope
from database.models import (
    AcademicSession,
    Course,
    Programme,
    Registration,
    RegistrationStatus,
    Student,
    VerificationResult,
)
from utils.error_handling import safe_page
from utils.ui_components import empty_state, metric_row, page_header, section_header


@safe_page
@require_authentication
def render() -> None:
    user = get_current_user()
    display_name = user.get("full_name", "User") if user else "User"
    role = get_current_role()

    page_header("Dashboard", f"Welcome, {display_name}.")

    if role == ADMINISTRATOR:
        _render_administrator_dashboard()
    elif role == ACADEMIC_OFFICER:
        _render_officer_dashboard()
    elif role == STUDENT:
        _render_student_dashboard()


def _render_administrator_dashboard() -> None:
    with session_scope() as session:
        total_students = session.query(Student).count()
        total_courses = session.query(Course).count()
        total_programmes = session.query(Programme).filter(Programme.is_active.is_(True)).count()
        pending = session.query(Registration).filter(
            Registration.status.in_([RegistrationStatus.SUBMITTED, RegistrationStatus.UNDER_REVIEW])
        ).count()
        requiring_correction = session.query(Registration).filter(
            Registration.status == RegistrationStatus.REQUIRES_CORRECTION
        ).count()
        approved = session.query(Registration).filter(Registration.status == RegistrationStatus.APPROVED).count()
        current_session = session.query(AcademicSession).filter(AcademicSession.is_current.is_(True)).one_or_none()
        current_session_name = current_session.name if current_session else "Not set"

    section_header("Key Metrics")
    metric_row(
        [
            ("Total Students", str(total_students)),
            ("Total Courses", str(total_courses)),
            ("Active Programmes", str(total_programmes)),
            ("Pending Verification", str(pending)),
            ("Approved Registrations", str(approved)),
            ("Requiring Correction", str(requiring_correction)),
        ]
    )
    section_header("Current Academic Context")
    st.write(f"Current Academic Session: **{current_session_name}**")


def _render_officer_dashboard() -> None:
    with session_scope() as session:
        pending = session.query(Registration).filter(
            Registration.status.in_([RegistrationStatus.SUBMITTED, RegistrationStatus.UNDER_REVIEW])
        ).count()
        requiring_correction = session.query(Registration).filter(
            Registration.status == RegistrationStatus.REQUIRES_CORRECTION
        ).count()
        approved = session.query(Registration).filter(Registration.status == RegistrationStatus.APPROVED).count()
        verified_runs = session.query(VerificationResult).count()

    section_header("Registration Activity")
    metric_row(
        [
            ("Pending Review", str(pending)),
            ("Requiring Correction", str(requiring_correction)),
            ("Approved", str(approved)),
            ("Verification Runs", str(verified_runs)),
        ]
    )
    st.caption("Open Verification to review and act on individual registrations.")


def _render_student_dashboard() -> None:
    with session_scope() as session:
        student_id = current_student_id(session)
        if student_id is None:
            empty_state("No student profile is linked to this account.")
            return

        student = session.get(Student, student_id)
        latest_registration = (
            session.query(Registration)
            .filter(Registration.student_id == student_id)
            .order_by(Registration.created_at.desc())
            .first()
        )

        latest_result = None
        if latest_registration:
            latest_result = (
                session.query(VerificationResult)
                .filter(VerificationResult.registration_id == latest_registration.id)
                .order_by(VerificationResult.verified_at.desc())
                .first()
            )

        profile = {
            "Matric Number": student.matric_number,
            "Programme": student.programme.name,
            "Department": student.department.name,
            "Level": student.level.name,
        }
        registration_status = latest_registration.status.value if latest_registration else "No Registration Yet"
        total_units = sum(rc.credit_units for rc in latest_registration.courses) if latest_registration else 0
        verification_status = latest_result.status.value if latest_result else "Not Verified"

    section_header("My Academic Profile")
    st.table(profile)

    section_header("Current Registration")
    metric_row(
        [
            ("Status", registration_status),
            ("Registered Units", str(total_units)),
            ("Verification Status", verification_status),
        ]
    )
    st.caption("Open Course Registration or Verification for full details.")
