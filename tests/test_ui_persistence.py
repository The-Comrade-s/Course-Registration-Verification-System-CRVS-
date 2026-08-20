"""
Regression tests for a specific, previously-shipped bug class: calling
st.rerun() from inside a `with session_scope() as session:` block.

st.rerun() raises streamlit's RerunException, which subclasses
BaseException (not Exception) specifically so application code doesn't
accidentally swallow it -- but that also means it unwinds straight past
`session.commit()` in database/connection.py's session_scope(), so
`session.close()` runs on an uncommitted transaction and silently
discards it. No exception is raised anywhere, so nothing looks wrong
except that the record never appears. These tests drive the real
Streamlit app end to end (via streamlit.testing.v1.AppTest) through each
create form that previously exhibited this bug, and assert the record
is actually persisted to the database afterward.
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_test_ui_{uuid.uuid4().hex}.db")
os.environ["CRVS_DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

from database.connection import init_db, session_scope
from database.seed import run_seed


def setUpModule():
    init_db()
    run_seed()


def tearDownModule():
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


def _logged_in_admin_test():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
        default_timeout=30,
    )
    at.run()
    at.text_input[0].input("admin@crvs.local").run()
    at.text_input[1].input("ChangeMe123!").run()
    at.button[0].click().run()
    return at


def _goto_administration_section(at, section: str):
    [r for r in at.radio if r.label == "Navigation"][0].set_value("Administration").run()
    admin_section_radio = [r for r in at.radio if r.label == "Administration Section"][0]
    admin_section_radio.set_value(section).run()
    return at


class TestCreateFormsActuallyPersist(unittest.TestCase):
    """Each test submits a real create form through the running app and
    checks the database directly -- not just that the UI showed no error."""

    def test_department_creation_persists(self):
        at = _logged_in_admin_test()
        _goto_administration_section(at, "Departments")
        name_input = [t for t in at.text_input if t.label == "Department Name"][0]
        code_input = [t for t in at.text_input if t.label == "Department Code"][0]
        name_input.input(f"Test Dept {uuid.uuid4().hex[:6]}").run()
        code = f"TD{uuid.uuid4().hex[:5].upper()}"
        code_input.input(code).run()
        create_btn = [b for b in at.button if b.label == "Create Department"][0]
        create_btn.click().run()

        self.assertFalse(bool(at.exception), f"Unexpected exception: {at.exception}")
        from database.models import Department
        with session_scope() as session:
            found = session.query(Department).filter(Department.code == code).one_or_none()
        self.assertIsNotNone(found, "Department was not actually committed to the database")

    def test_level_creation_persists(self):
        at = _logged_in_admin_test()
        _goto_administration_section(at, "Levels")
        level_name = f"Level {uuid.uuid4().hex[:6]}"
        name_input = [t for t in at.text_input if "Level Name" in t.label][0]
        name_input.input(level_name).run()
        create_btn = [b for b in at.button if b.label == "Create Level"][0]
        create_btn.click().run()

        self.assertFalse(bool(at.exception), f"Unexpected exception: {at.exception}")
        from database.models import Level
        with session_scope() as session:
            found = session.query(Level).filter(Level.name == level_name).one_or_none()
        self.assertIsNotNone(found, "Level was not actually committed to the database")

    def test_academic_session_creation_persists(self):
        at = _logged_in_admin_test()
        _goto_administration_section(at, "Academic Sessions")
        session_name = f"9{uuid.uuid4().hex[:3]}/9{uuid.uuid4().hex[:3]}"
        name_input = [t for t in at.text_input if "Session Name" in t.label][0]
        name_input.input(session_name).run()
        create_btn = [b for b in at.button if b.label == "Create Session"][0]
        create_btn.click().run()

        self.assertFalse(bool(at.exception), f"Unexpected exception: {at.exception}")
        from database.models import AcademicSession
        with session_scope() as session:
            found = session.query(AcademicSession).filter(AcademicSession.name == session_name).one_or_none()
        self.assertIsNotNone(found, "Academic session was not actually committed to the database")

    def test_programme_creation_persists(self):
        at = _logged_in_admin_test()
        [r for r in at.radio if r.label == "Navigation"][0].set_value("Programmes").run()
        name = f"Test Programme {uuid.uuid4().hex[:6]}"
        code = f"TP{uuid.uuid4().hex[:5].upper()}"
        name_input = [t for t in at.text_input if t.label == "Programme Name"][0]
        code_input = [t for t in at.text_input if t.label == "Programme Code"][0]
        name_input.input(name).run()
        code_input.input(code).run()
        create_btn = [b for b in at.button if b.label == "Create Programme"][0]
        create_btn.click().run()

        self.assertFalse(bool(at.exception), f"Unexpected exception: {at.exception}")
        from database.models import Programme
        with session_scope() as session:
            found = session.query(Programme).filter(Programme.code == code).one_or_none()
        self.assertIsNotNone(found, "Programme was not actually committed to the database")

    def test_course_creation_persists(self):
        at = _logged_in_admin_test()
        [r for r in at.radio if r.label == "Navigation"][0].set_value("Courses").run()
        code = f"TC{uuid.uuid4().hex[:5].upper()}"
        code_input = [t for t in at.text_input if "Course Code" in t.label][0]
        title_input = [t for t in at.text_input if t.label == "Course Title"][0]
        code_input.input(code).run()
        title_input.input("Test Course").run()
        create_btn = [b for b in at.button if b.label == "Add Course"][0]
        create_btn.click().run()

        self.assertFalse(bool(at.exception), f"Unexpected exception: {at.exception}")
        from database.models import Course
        with session_scope() as session:
            found = session.query(Course).filter(Course.code == code).one_or_none()
        self.assertIsNotNone(found, "Course was not actually committed to the database")


class TestStaffCreationDoesNotCrashOnReusedOfficer(unittest.TestCase):
    """
    Regression test: the Staff tab's officer dropdown used to offer every
    Academic Officer account regardless of whether they already had a
    Staff record. Since Staff.user_id is one-to-one, re-selecting an
    already-assigned officer raised an uncaught IntegrityError, which
    surfaced to the user as a generic "unexpected error" with no
    indication of what went wrong or how to fix it.
    """

    def test_dropdown_excludes_already_assigned_officers_and_new_ones_appear(self):
        at = _logged_in_admin_test()
        _goto_administration_section(at, "Staff")

        # With every seeded officer already assigned, the dropdown should
        # not be offered at all -- it should explain why instead of
        # crashing when the admin tries anyway.
        staff_dropdowns = [s for s in at.selectbox if s.label == "User Account"]
        self.assertEqual(staff_dropdowns, [], "Dropdown should not appear when every officer is already assigned")
        guidance = " ".join(c.value for c in at.caption)
        self.assertIn("already has a staff record", guidance)

        # Create a fresh Academic Officer user; they should become
        # selectable, and creating their staff record should succeed
        # without any exception.
        _goto_administration_section(at, "Users")
        email = f"officer-{uuid.uuid4().hex[:8]}@crvs.local"
        [t for t in at.text_input if t.label == "Full Name"][0].input("New Officer").run()
        [t for t in at.text_input if t.label == "Email"][0].input(email).run()
        [s for s in at.selectbox if s.label == "Role"][0].set_value("Academic Officer").run()
        [t for t in at.text_input if t.label == "Initial Password"][0].input("SecurePass123!").run()
        [b for b in at.button if b.label == "Create User"][0].click().run()
        self.assertFalse(bool(at.exception), f"Unexpected exception creating user: {at.exception}")

        _goto_administration_section(at, "Staff")
        staff_dropdowns = [s for s in at.selectbox if s.label == "User Account"]
        self.assertIn("New Officer", staff_dropdowns[0].options)

        staff_id = f"STF{uuid.uuid4().hex[:5].upper()}"
        [t for t in at.text_input if t.label == "Staff ID"][0].input(staff_id).run()
        [b for b in at.button if b.label == "Create Staff Record"][0].click().run()
        self.assertFalse(bool(at.exception), f"Unexpected exception creating staff: {at.exception}")

        from database.models import Staff
        with session_scope() as session:
            found = session.query(Staff).filter(Staff.staff_id == staff_id).one_or_none()
        self.assertIsNotNone(found, "Staff record was not actually committed to the database")


class TestStudentRegistrationPageDoesNotCrash(unittest.TestCase):
    """
    Regression test: SQLAlchemy expires ORM object attributes once a
    session commits, so any object read inside a `with session_scope()`
    block and then used after that block closes raises
    DetachedInstanceError. This previously crashed the entire student
    Course Registration page (current_session.name / current_semester.name
    were accessed after the session closed), and would also have crashed
    the moment a student clicked "Add" on any course.
    """

    def test_registration_page_loads_and_add_course_works(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
            default_timeout=30,
        )
        at.run()
        at.text_input[0].input("student1@crvs.local").run()
        at.text_input[1].input("ChangeMe123!").run()
        at.button[0].click().run()
        [r for r in at.radio if r.label == "Navigation"][0].set_value("Course Registration").run()

        self.assertFalse(bool(at.exception), f"Unexpected exception loading registration page: {at.exception}")
        error_shown = any("unexpected error" in md.value.lower() for md in at.markdown)
        self.assertFalse(error_shown, "Registration page showed an error instead of rendering")

        add_buttons = [b for b in at.button if b.label == "Add"]
        self.assertTrue(add_buttons, "Expected at least one available course with an Add button")
        add_buttons[0].click().run()
        self.assertFalse(bool(at.exception), f"Unexpected exception adding a course: {at.exception}")


if __name__ == "__main__":
    unittest.main()
