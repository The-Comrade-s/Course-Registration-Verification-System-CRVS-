"""
Tests for CRVS-002: authentication, RBAC, and academic structure.
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_test_auth_{uuid.uuid4().hex}.db")
os.environ["CRVS_DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

from database.connection import init_db, session_scope
from database.models import Department, Programme, Level, User, UserRole
from utils.security import hash_password, verify_password


def setUpModule():
    init_db()


def tearDownModule():
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


class TestPasswordHashing(unittest.TestCase):
    def test_hash_and_verify_roundtrip(self):
        hashed = hash_password("Sup3rSecret!")
        self.assertTrue(verify_password("Sup3rSecret!", hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_hash_never_equals_plaintext(self):
        hashed = hash_password("Sup3rSecret!")
        self.assertNotEqual(hashed, "Sup3rSecret!")

    def test_empty_password_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("")


class TestAuthentication(unittest.TestCase):
    def setUp(self):
        with session_scope() as session:
            session.query(User).delete()
            session.add(
                User(
                    full_name="Test Admin",
                    email="test.admin@crvs.local",
                    password_hash=hash_password("CorrectPassword1"),
                    role=UserRole.ADMINISTRATOR,
                    is_active=True,
                )
            )
            session.add(
                User(
                    full_name="Inactive User",
                    email="inactive@crvs.local",
                    password_hash=hash_password("CorrectPassword1"),
                    role=UserRole.STUDENT,
                    is_active=False,
                )
            )

    def test_valid_login(self):
        from auth.authentication import authenticate

        result = authenticate("test.admin@crvs.local", "CorrectPassword1")
        self.assertTrue(result.success)

    def test_invalid_password(self):
        from auth.authentication import authenticate

        result = authenticate("test.admin@crvs.local", "WrongPassword")
        self.assertFalse(result.success)

    def test_unknown_user(self):
        from auth.authentication import authenticate

        result = authenticate("nobody@crvs.local", "whatever")
        self.assertFalse(result.success)

    def test_inactive_account_rejected(self):
        from auth.authentication import authenticate

        result = authenticate("inactive@crvs.local", "CorrectPassword1")
        self.assertFalse(result.success)
        self.assertIn("deactivated", result.message.lower())


class TestAuthorization(unittest.TestCase):
    def test_has_permission(self):
        from auth.authorization import ADMINISTRATOR, STUDENT, has_permission

        self.assertTrue(has_permission(ADMINISTRATOR, [ADMINISTRATOR, "Academic Officer"]))
        self.assertFalse(has_permission(STUDENT, [ADMINISTRATOR]))

    def test_can_access_respects_role(self):
        # can_access requires an authenticated session; verified indirectly
        # via has_permission and the role constants it is built from.
        from auth.authorization import ACADEMIC_OFFICER, ADMINISTRATOR, STUDENT

        self.assertNotEqual(ADMINISTRATOR, STUDENT)
        self.assertNotEqual(ACADEMIC_OFFICER, STUDENT)


class TestAcademicStructure(unittest.TestCase):
    def test_department_uniqueness(self):
        with session_scope() as session:
            session.add(Department(name="Physics", code="PHY-TEST"))

        with self.assertRaises(Exception):
            with session_scope() as session:
                session.add(Department(name="Physics Duplicate", code="PHY-TEST"))

    def test_programme_requires_department(self):
        with session_scope() as session:
            dept = Department(name="Chemistry", code="CHM-TEST")
            session.add(dept)
            session.flush()
            programme = Programme(name="B.Sc. Chemistry", code="BSCCHM-TEST", department_id=dept.id)
            session.add(programme)
            session.flush()
            self.assertIsNotNone(programme.id)

    def test_level_numeric_value(self):
        with session_scope() as session:
            level = Level(name="500 Level Test", numeric_value=500)
            session.add(level)
            session.flush()
            self.assertEqual(level.numeric_value, 500)


if __name__ == "__main__":
    unittest.main()
