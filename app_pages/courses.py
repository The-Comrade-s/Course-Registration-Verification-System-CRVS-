"""
Courses page.

Administrators and academic officers manage the course catalogue,
programme course structures, elective rules, and prerequisites. Students
have no access to this page (course definitions are read-only to them,
surfaced instead through Course Registration).
"""

from __future__ import annotations

import streamlit as st

from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, current_user_id, require_role
from database.connection import session_scope
from database.models import (
    AcademicSession,
    Course,
    CoursePrerequisite,
    CourseType,
    Department,
    Level,
    Programme,
    ProgrammeCourseStructure,
    ProgrammeElectiveRule,
    Semester,
)
from services import audit_service
from utils.error_handling import safe_page
from utils.ui_components import data_table, empty_state, error_message, page_header, section_header, success_message
from utils.validators import is_non_empty, is_positive_number


@safe_page
@require_role(ADMINISTRATOR, ACADEMIC_OFFICER)
def render() -> None:
    page_header("Courses", "Manage the course catalogue.")

    sections = {
        "Course Catalogue": _render_catalogue_tab,
        "Programme Course Structure": _render_structure_tab,
        "Prerequisites": _render_prerequisites_tab,
    }
    section = st.radio(
        "Courses Section", list(sections.keys()), horizontal=True,
        key="courses_active_section", label_visibility="collapsed",
    )
    sections[section]()


def _render_catalogue_tab() -> None:
    section_header("Course Catalogue")
    with session_scope() as session:
        courses = session.query(Course).order_by(Course.code).all()
        rows = [
            {
                "Code": c.code,
                "Title": c.title,
                "Units": c.credit_units,
                "Level": c.level.name,
                "Department": c.department.name,
                "Active": "Yes" if c.is_active else "No",
            }
            for c in courses
        ]
        department_options = {d.name: d.id for d in session.query(Department).order_by(Department.name).all()}
        level_options = {l.name: l.id for l in session.query(Level).order_by(Level.numeric_value).all()}

    if rows:
        data_table(rows)
    else:
        empty_state("No courses have been added yet.")

    if not (department_options and level_options):
        st.caption("Create at least one department and level before adding courses.")
        return

    section_header("Add Course")
    with st.form("create_course_form", clear_on_submit=True):
        code = st.text_input("Course Code (e.g. CSC307)")
        title = st.text_input("Course Title")
        credit_units = st.number_input("Credit Units", min_value=1, max_value=12, value=3)
        level_name = st.selectbox("Level", list(level_options.keys()))
        department_name = st.selectbox("Department", list(department_options.keys()))
        description = st.text_area("Description", height=80)
        submitted = st.form_submit_button("Add Course")

    if submitted:
        if not (is_non_empty(code) and is_non_empty(title) and is_positive_number(credit_units)):
            error_message("Course code, title and a positive credit unit value are required.")
        else:
            created = False
            normalized_code = code.strip().upper()
            with session_scope() as session:
                if session.query(Course).filter(Course.code == normalized_code).one_or_none():
                    error_message(f"Course code {normalized_code} already exists.")
                else:
                    course = Course(
                        code=normalized_code,
                        title=title.strip(),
                        credit_units=int(credit_units),
                        level_id=level_options[level_name],
                        department_id=department_options[department_name],
                        description=description.strip() or None,
                    )
                    session.add(course)
                    session.flush()
                    audit_service.record(session, current_user_id(), "COURSE_CREATED", "Course", course.id)
                    created = True
            if created:
                success_message(f"Course {normalized_code} added.")
                st.rerun()

    section_header("Activate / Deactivate Course")
    with session_scope() as session:
        course_options = {c.code: c.id for c in session.query(Course).order_by(Course.code).all()}
    if course_options:
        selection = st.selectbox("Select Course", list(course_options.keys()), key="toggle_course_select")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Activate", key="activate_course", use_container_width=True):
                _set_course_active(course_options[selection], True)
                st.rerun()
        with col_b:
            if st.button("Deactivate", key="deactivate_course", use_container_width=True):
                _set_course_active(course_options[selection], False)
                st.rerun()


def _set_course_active(course_id: int, active: bool) -> None:
    with session_scope() as session:
        course = session.get(Course, course_id)
        if course is not None:
            course.is_active = active
            audit_service.record(session, current_user_id(), "COURSE_STATUS_CHANGED", "Course", course.id, details=str(active))


def _render_structure_tab() -> None:
    section_header("Programme Course Structure")
    st.caption("Define which courses apply to a programme, level, session and semester, and whether each is compulsory or elective.")

    with session_scope() as session:
        programme_options = {p.name: p.id for p in session.query(Programme).order_by(Programme.name).all()}
        level_options = {l.name: l.id for l in session.query(Level).order_by(Level.numeric_value).all()}
        session_options = {s.name: s.id for s in session.query(AcademicSession).order_by(AcademicSession.name.desc()).all()}
        course_options = {c.code: c.id for c in session.query(Course).filter(Course.is_active.is_(True)).order_by(Course.code).all()}

    if not (programme_options and level_options and session_options and course_options):
        st.caption("Programmes, levels, an academic session, and at least one course are required before configuring structure.")
        return

    col1, col2 = st.columns(2)
    with col1:
        programme_name = st.selectbox("Programme", list(programme_options.keys()), key="structure_programme")
        level_name = st.selectbox("Level", list(level_options.keys()), key="structure_level")
    with col2:
        session_name = st.selectbox("Academic Session", list(session_options.keys()), key="structure_session")
        with session_scope() as session:
            semesters = (
                session.query(Semester)
                .filter(Semester.academic_session_id == session_options[session_name])
                .all()
            )
            semester_options = {s.name: s.id for s in semesters}
        semester_name = st.selectbox("Semester", list(semester_options.keys()) or ["-"], key="structure_semester")

    if not semester_options:
        st.caption("Create a semester for the selected session first, from Administration.")
        return

    with session_scope() as session:
        existing_rows = (
            session.query(ProgrammeCourseStructure)
            .filter(
                ProgrammeCourseStructure.programme_id == programme_options[programme_name],
                ProgrammeCourseStructure.level_id == level_options[level_name],
                ProgrammeCourseStructure.academic_session_id == session_options[session_name],
                ProgrammeCourseStructure.semester_id == semester_options[semester_name],
            )
            .all()
        )
        display_rows = [{"Course": row.course.code, "Requirement": row.requirement_type.value} for row in existing_rows]

    if display_rows:
        data_table(display_rows)
    else:
        empty_state("No courses configured for this programme/level/session/semester yet.")

    with st.form("add_structure_row_form", clear_on_submit=True):
        course_name = st.selectbox("Course", list(course_options.keys()))
        requirement = st.selectbox("Requirement Type", [t.value for t in CourseType])
        submitted = st.form_submit_button("Add to Structure")

    if submitted:
        created = False
        with session_scope() as session:
            duplicate = (
                session.query(ProgrammeCourseStructure)
                .filter(
                    ProgrammeCourseStructure.programme_id == programme_options[programme_name],
                    ProgrammeCourseStructure.level_id == level_options[level_name],
                    ProgrammeCourseStructure.academic_session_id == session_options[session_name],
                    ProgrammeCourseStructure.semester_id == semester_options[semester_name],
                    ProgrammeCourseStructure.course_id == course_options[course_name],
                )
                .one_or_none()
            )
            if duplicate:
                error_message(f"{course_name} is already configured for this context.")
            else:
                row = ProgrammeCourseStructure(
                    programme_id=programme_options[programme_name],
                    level_id=level_options[level_name],
                    academic_session_id=session_options[session_name],
                    semester_id=semester_options[semester_name],
                    course_id=course_options[course_name],
                    requirement_type=CourseType(requirement),
                )
                session.add(row)
                session.flush()
                audit_service.record(session, current_user_id(), "COURSE_STRUCTURE_MODIFIED", "ProgrammeCourseStructure", row.id)
                created = True
        if created:
            success_message(f"{course_name} added to the structure as {requirement}.")
            st.rerun()

    section_header("Elective Requirements for This Context")
    with session_scope() as session:
        rule = (
            session.query(ProgrammeElectiveRule)
            .filter(
                ProgrammeElectiveRule.programme_id == programme_options[programme_name],
                ProgrammeElectiveRule.level_id == level_options[level_name],
                ProgrammeElectiveRule.academic_session_id == session_options[session_name],
                ProgrammeElectiveRule.semester_id == semester_options[semester_name],
            )
            .one_or_none()
        )
        defaults = (
            (rule.min_electives, rule.max_electives, rule.elective_min_units, rule.elective_max_units,
             rule.total_min_units, rule.total_max_units)
            if rule else (0, 0, 0, 0, 0, 0)
        )

    with st.form("elective_rule_form"):
        min_electives = st.number_input("Minimum Electives", min_value=0, value=defaults[0])
        max_electives = st.number_input("Maximum Electives", min_value=0, value=defaults[1])
        elective_min_units = st.number_input("Minimum Elective Credit Units", min_value=0, value=defaults[2])
        elective_max_units = st.number_input("Maximum Elective Credit Units", min_value=0, value=defaults[3])
        total_min_units = st.number_input("Minimum Total Registration Units", min_value=0, value=defaults[4])
        total_max_units = st.number_input("Maximum Total Registration Units", min_value=0, value=defaults[5])
        submitted_rule = st.form_submit_button("Save Elective Rule")

    if submitted_rule:
        with session_scope() as session:
            rule = (
                session.query(ProgrammeElectiveRule)
                .filter(
                    ProgrammeElectiveRule.programme_id == programme_options[programme_name],
                    ProgrammeElectiveRule.level_id == level_options[level_name],
                    ProgrammeElectiveRule.academic_session_id == session_options[session_name],
                    ProgrammeElectiveRule.semester_id == semester_options[semester_name],
                )
                .one_or_none()
            )
            if rule is None:
                rule = ProgrammeElectiveRule(
                    programme_id=programme_options[programme_name],
                    level_id=level_options[level_name],
                    academic_session_id=session_options[session_name],
                    semester_id=semester_options[semester_name],
                )
                session.add(rule)
            rule.min_electives = int(min_electives)
            rule.max_electives = int(max_electives)
            rule.elective_min_units = int(elective_min_units)
            rule.elective_max_units = int(elective_max_units)
            rule.total_min_units = int(total_min_units)
            rule.total_max_units = int(total_max_units)
            session.flush()
            audit_service.record(session, current_user_id(), "ELECTIVE_RULE_SAVED", "ProgrammeElectiveRule", rule.id)
        success_message("Elective rule saved.")
        st.rerun()


def _render_prerequisites_tab() -> None:
    section_header("Course Prerequisites")
    with session_scope() as session:
        prereqs = session.query(CoursePrerequisite).all()
        rows = [
            {"Course": p.course.code, "Requires": p.prerequisite_course.code}
            for p in prereqs
        ]
        course_options = {c.code: c.id for c in session.query(Course).order_by(Course.code).all()}

    if rows:
        data_table(rows)
    else:
        empty_state("No prerequisites configured yet.")

    if len(course_options) < 2:
        st.caption("At least two courses are required to configure a prerequisite.")
        return

    with st.form("add_prerequisite_form", clear_on_submit=True):
        course_name = st.selectbox("Course", list(course_options.keys()), key="prereq_course")
        prereq_name = st.selectbox("Requires (Prerequisite)", list(course_options.keys()), key="prereq_required")
        submitted = st.form_submit_button("Add Prerequisite")

    if submitted:
        if course_name == prereq_name:
            error_message("A course cannot be its own prerequisite.")
        else:
            created = False
            with session_scope() as session:
                duplicate = (
                    session.query(CoursePrerequisite)
                    .filter(
                        CoursePrerequisite.course_id == course_options[course_name],
                        CoursePrerequisite.prerequisite_course_id == course_options[prereq_name],
                    )
                    .one_or_none()
                )
                if duplicate:
                    error_message("This prerequisite relationship already exists.")
                else:
                    prereq = CoursePrerequisite(
                        course_id=course_options[course_name],
                        prerequisite_course_id=course_options[prereq_name],
                    )
                    session.add(prereq)
                    session.flush()
                    audit_service.record(session, current_user_id(), "PREREQUISITE_ADDED", "CoursePrerequisite", prereq.id)
                    created = True
            if created:
                success_message(f"{course_name} now requires {prereq_name}.")
                st.rerun()
