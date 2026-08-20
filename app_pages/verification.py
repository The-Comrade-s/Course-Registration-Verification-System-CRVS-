"""
Verification page.

Students view their verification results and correction guidance.
Academic officers and administrators review submitted/verified
registrations, trigger verification, and approve, reject or return them
for correction.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import (
    ACADEMIC_OFFICER,
    ADMINISTRATOR,
    STUDENT,
    current_student_id,
    current_user_id,
    get_current_role,
    require_authentication,
)
from database.connection import session_scope
from database.models import IssueSeverity, Registration, RegistrationStatus, VerificationResult
from services import approval_service, report_service, verification_engine
from utils.error_handling import safe_page
from utils.helpers import format_datetime
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, status_badge, success_message

_STATUS_SEVERITY = {
    "Passed": "success",
    "Failed": "error",
    "Requires Correction": "error",
    "Pending": "neutral",
}


@safe_page
@require_authentication
def render() -> None:
    page_header("Verification", "Automated registration verification results.")

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

        registrations = (
            session.query(Registration)
            .filter(Registration.student_id == student_id, Registration.status != RegistrationStatus.DRAFT)
            .order_by(Registration.submitted_at.desc())
            .all()
        )
        if not registrations:
            empty_state("You have no submitted registrations yet.")
            return

        latest = registrations[0]
        latest_result = (
            session.query(VerificationResult)
            .filter(VerificationResult.registration_id == latest.id)
            .order_by(VerificationResult.verified_at.desc())
            .first()
        )

        result_data = None
        if latest_result:
            result_data = {
                "status": latest_result.status.value,
                "total_units": latest_result.total_registered_units,
                "summary": latest_result.summary,
                "verified_at": latest_result.verified_at,
                "issues": [
                    {
                        "description": i.description,
                        "severity": i.severity.value,
                    }
                    for i in latest_result.issues
                ],
            }
        registration_status = latest.status.value
        latest_registration_id = latest.id

    section_header("Latest Registration")
    st.markdown(status_badge(registration_status, "warning" if registration_status != "Approved" else "success"), unsafe_allow_html=True)

    with session_scope() as session:
        slip_pdf = report_service.generate_registration_slip_pdf(session, latest_registration_id)
    st.download_button(
        "Download Registration Slip (PDF)",
        data=slip_pdf,
        file_name="course_registration_slip.pdf",
        mime="application/pdf",
    )
    st.caption("Print this slip and submit it to your department/HOD office as required.")

    if result_data is None:
        empty_state("Verification has not yet run for this registration.")
        return

    section_header("Verification Result")
    st.markdown(
        status_badge(result_data["status"], _STATUS_SEVERITY.get(result_data["status"], "neutral")),
        unsafe_allow_html=True,
    )
    st.caption(f"Registered Units: {result_data['total_units']}  |  Verified: {format_datetime(result_data['verified_at'])}")
    st.write(result_data["summary"])

    if result_data["issues"]:
        section_header("Issues")
        for issue in result_data["issues"]:
            st.markdown(f"- **{issue['severity']}**: {issue['description']}")
        st.caption("Return to Course Registration to correct these issues and resubmit.")
    else:
        empty_state("No verification issues found.")


def _render_staff_view() -> None:
    section_header("Registrations Awaiting Action")
    with session_scope() as session:
        registrations = (
            session.query(Registration)
            .filter(Registration.status != RegistrationStatus.DRAFT)
            .order_by(Registration.submitted_at.desc())
            .all()
        )
        options = {
            f"{r.student.matric_number} - {r.student.user.full_name} ({r.academic_session.name}, {r.semester.name}) - {r.status.value}": r.id
            for r in registrations
        }

    if not options:
        empty_state("No registrations to review.")
        return

    selection = st.selectbox("Select Registration", list(options.keys()))
    registration_id = options[selection]

    if st.button("Run Verification"):
        with session_scope() as session:
            verification_engine.run_verification(session, registration_id, performed_by_user_id=current_user_id())
        success_message("Verification completed.")
        st.rerun()

    with session_scope() as session:
        registration = session.get(Registration, registration_id)
        latest_result = (
            session.query(VerificationResult)
            .filter(VerificationResult.registration_id == registration_id)
            .order_by(VerificationResult.verified_at.desc())
            .first()
        )
        course_rows = [{"Code": rc.course.code, "Title": rc.course.title, "Units": rc.credit_units} for rc in registration.courses]
        result_data = None
        if latest_result:
            result_data = {
                "status": latest_result.status.value,
                "total_units": latest_result.total_registered_units,
                "issues": [{"description": i.description, "severity": i.severity.value} for i in latest_result.issues],
                "has_errors": any(i.severity == IssueSeverity.ERROR for i in latest_result.issues),
            }
        student_name = registration.student.user.full_name
        matric = registration.student.matric_number
        current_status = registration.status.value

    section_header(f"{student_name} ({matric})")
    st.caption(f"Current Status: {current_status}")
    if course_rows:
        data_table(course_rows)

    if result_data is None:
        empty_state("This registration has not yet been verified.")
        return

    st.markdown(status_badge(result_data["status"], _STATUS_SEVERITY.get(result_data["status"], "neutral")), unsafe_allow_html=True)
    st.caption(f"Total Units: {result_data['total_units']}")
    if result_data["issues"]:
        for issue in result_data["issues"]:
            st.markdown(f"- **{issue['severity']}**: {issue['description']}")
    else:
        empty_state("No issues found.")

    section_header("Review Decision")
    comment = st.text_area("Review Comment (optional)")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Approve", type="primary", disabled=result_data["has_errors"]):
            with session_scope() as session:
                try:
                    approval_service.approve_registration(session, registration_id, current_user_id(), comment or None)
                    success_message("Registration approved.")
                except approval_service.ApprovalError as exc:
                    error_message(str(exc))
            st.rerun()
    with col_b:
        if st.button("Return for Correction"):
            with session_scope() as session:
                approval_service.return_for_correction(session, registration_id, current_user_id(), comment or None)
            success_message("Registration returned for correction.")
            st.rerun()
    with col_c:
        if st.button("Reject"):
            with session_scope() as session:
                approval_service.reject_registration(session, registration_id, current_user_id(), comment or None)
            success_message("Registration rejected.")
            st.rerun()

    if result_data["has_errors"]:
        st.caption("Approval is disabled while unresolved errors remain on the latest verification run.")
