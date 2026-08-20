"""
Reports page.

Administrators and academic officers generate and export registration
and verification reports. Students see only their own registration
report.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, STUDENT, current_student_id, get_current_role, require_authentication
from database.connection import session_scope
from services import report_service
from utils.error_handling import safe_page
from utils.ui_components import data_table, empty_state, page_header, section_header


@safe_page
@require_authentication
def render() -> None:
    page_header("Reports", "Generate and export institutional reports.")

    role = get_current_role()
    if role == STUDENT:
        _render_student_report()
    elif role in (ADMINISTRATOR, ACADEMIC_OFFICER):
        _render_staff_reports()


def _render_student_report() -> None:
    section_header("My Registration Report")
    with session_scope() as session:
        student_id = current_student_id(session)
        if student_id is None:
            empty_state("No student profile is linked to this account.")
            return
        dataframe = report_service.student_registration_report(session, student_id)

    if dataframe.empty:
        empty_state("No registration history to report yet.")
        return

    data_table(dataframe)
    st.download_button(
        "Download CSV",
        data=report_service.to_csv_bytes(dataframe),
        file_name="my_registration_report.csv",
        mime="text/csv",
    )


def _render_staff_reports() -> None:
    section = st.radio(
        "Reports Section", ["Registration Report", "Verification Report"], horizontal=True,
        key="reports_active_section", label_visibility="collapsed",
    )

    if section == "Registration Report":
        section_header("Registration Report")
        with session_scope() as session:
            dataframe = report_service.student_registration_report(session)
        if dataframe.empty:
            empty_state("No registration data available yet.")
        else:
            data_table(dataframe)
            st.download_button(
                "Download CSV",
                data=report_service.to_csv_bytes(dataframe),
                file_name="registration_report.csv",
                mime="text/csv",
                key="download_registration_report",
            )
    else:
        section_header("Verification Report")
        with session_scope() as session:
            dataframe = report_service.verification_report(session)
        if dataframe.empty:
            empty_state("No verification data available yet.")
        else:
            data_table(dataframe)
            st.download_button(
                "Download CSV",
                data=report_service.to_csv_bytes(dataframe),
                file_name="verification_report.csv",
                mime="text/csv",
                key="download_verification_report",
            )
