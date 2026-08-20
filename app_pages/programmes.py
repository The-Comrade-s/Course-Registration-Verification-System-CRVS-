"""
Programmes page.

Administrators (and, in read-only form, academic officers) manage
academic programmes.
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, current_user_id, get_current_role, require_role
from database.connection import session_scope
from database.models import Department, Programme
from services import audit_service
from utils.error_handling import safe_page
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, success_message
from utils.validators import is_non_empty


@safe_page
@require_role(ADMINISTRATOR, ACADEMIC_OFFICER)
def render() -> None:
    page_header("Programmes", "Manage academic programmes.")

    with session_scope() as session:
        programmes = session.query(Programme).order_by(Programme.name).all()
        rows = [
            {
                "Programme": p.name,
                "Code": p.code,
                "Department": p.department.name,
                "Duration (Years)": p.duration_years,
                "Active": "Yes" if p.is_active else "No",
            }
            for p in programmes
        ]

    if rows:
        data_table(rows)
    else:
        empty_state("No programmes have been configured yet.")

    if get_current_role() != ADMINISTRATOR:
        return

    section_header("Create Programme")
    with session_scope() as session:
        department_options = {d.name: d.id for d in session.query(Department).order_by(Department.name).all()}

    if not department_options:
        st.caption("Create a department first, from Administration, before adding a programme.")
        return

    with st.form("create_programme_form", clear_on_submit=True):
        name = st.text_input("Programme Name")
        code = st.text_input("Programme Code")
        department_name = st.selectbox("Department", list(department_options.keys()))
        duration = st.number_input("Duration (Years)", min_value=1, max_value=8, value=4)
        description = st.text_area("Description", height=80)
        submitted = st.form_submit_button("Create Programme")

    if submitted:
        if not (is_non_empty(name) and is_non_empty(code)):
            error_message("Programme name and code are required.")
        else:
            created = False
            with session_scope() as session:
                if session.query(Programme).filter(Programme.code == code.strip().upper()).one_or_none():
                    error_message("A programme with this code already exists.")
                else:
                    programme = Programme(
                        name=name.strip(),
                        code=code.strip().upper(),
                        department_id=department_options[department_name],
                        duration_years=int(duration),
                        description=description.strip() or None,
                    )
                    session.add(programme)
                    session.flush()
                    audit_service.record(session, current_user_id(), "PROGRAMME_CREATED", "Programme", programme.id)
                    created = True
            if created:
                success_message(f"Programme '{name}' created.")
                st.rerun()
