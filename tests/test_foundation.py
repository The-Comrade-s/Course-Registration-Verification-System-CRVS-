"""
Foundation tests for CRVS-001.

Verifies:
    - The application and its submodules import successfully.
    - The database initializes successfully.
    - The SQLAlchemy connection works.
    - Configuration loads correctly.
    - Utility modules import successfully.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import uuid

# Point the database at a throwaway file before any application module is
# imported, so the module-level SQLAlchemy engine in database.connection
# is created against a clean, disposable database for this test run.
_TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_crvs.db")
if os.path.exists(_TEST_DB_PATH):
    os.remove(_TEST_DB_PATH)
os.environ["CRVS_DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"


class TestConfiguration(unittest.TestCase):
    def test_settings_load(self):
        from config import settings

        self.assertTrue(settings.app.app_name)
        self.assertTrue(settings.database.database_url)


class TestModuleImports(unittest.TestCase):
    def test_core_modules_import(self):
        import auth.authentication  # noqa: F401
        import auth.authorization  # noqa: F401
        import auth.session  # noqa: F401
        import database.connection  # noqa: F401
        import database.models  # noqa: F401
        import database.seed  # noqa: F401
        import services.application_service  # noqa: F401
        import utils.error_handling  # noqa: F401
        import utils.helpers  # noqa: F401
        import utils.logging_config  # noqa: F401
        import utils.security  # noqa: F401
        import utils.theme  # noqa: F401
        import utils.ui_components  # noqa: F401
        import utils.validators  # noqa: F401

    def test_page_modules_import(self):
        import app_pages.administration  # noqa: F401
        import app_pages.courses  # noqa: F401
        import app_pages.dashboard  # noqa: F401
        import app_pages.login  # noqa: F401
        import app_pages.programmes  # noqa: F401
        import app_pages.registration  # noqa: F401
        import app_pages.reports  # noqa: F401
        import app_pages.settings  # noqa: F401
        import app_pages.students  # noqa: F401
        import app_pages.verification  # noqa: F401


class TestDatabase(unittest.TestCase):
    def test_engine_connects(self):
        from database.connection import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            self.assertEqual(result.scalar(), 1)

    def test_init_db_creates_schema(self):
        from database.connection import engine, init_db
        from sqlalchemy import inspect

        init_db()
        inspector = inspect(engine)
        self.assertIn("system_info", inspector.get_table_names())

    def test_session_scope_commits(self):
        from database.connection import init_db, session_scope
        from database.models import SystemInfo

        init_db()
        unique_key = f"test_key_{uuid.uuid4().hex}"
        with session_scope() as session:
            session.add(SystemInfo(key=unique_key, value="test_value"))

        with session_scope() as session:
            record = session.query(SystemInfo).filter_by(key=unique_key).one_or_none()
            self.assertIsNotNone(record)
            self.assertEqual(record.value, "test_value")


class TestValidators(unittest.TestCase):
    def test_email_validation(self):
        from utils.validators import is_valid_email

        self.assertTrue(is_valid_email("student@example.edu"))
        self.assertFalse(is_valid_email("not-an-email"))
        self.assertFalse(is_valid_email(""))

    def test_positive_number(self):
        from utils.validators import is_positive_number

        self.assertTrue(is_positive_number(3))
        self.assertFalse(is_positive_number(-1))
        self.assertFalse(is_positive_number("abc"))


class TestApplicationService(unittest.TestCase):
    def test_status_returns_expected_keys(self):
        from services.application_service import get_application_status

        status = get_application_status()
        self.assertIn("app_name", status)
        self.assertIn("app_version", status)
        self.assertIn("environment", status)


if __name__ == "__main__":
    unittest.main()
