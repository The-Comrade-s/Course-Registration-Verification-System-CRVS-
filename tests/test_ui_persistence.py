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
    at.radio[0].set_value("Administration").run()
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
        at.radio[0].set_value("Programmes").run()
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
        at.radio[0].set_value("Courses").run()
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


if __name__ == "__main__":
    unittest.main()
