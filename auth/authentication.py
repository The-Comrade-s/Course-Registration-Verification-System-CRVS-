"""
Authentication.

Verifies credentials against the User model using bcrypt password
verification, and populates the session on success. Records login/logout
events to the audit log without ever recording the password itself.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from auth.session import clear_session, get_current_user, set_current_user
from database.connection import session_scope
from database.models import User
from services import audit_service
from utils.logging_config import get_logger
from utils.security import verify_password

logger = get_logger("auth.authentication")


@dataclass(frozen=True)
class LoginResult:
    success: bool
    message: str


def authenticate(identifier: str, password: str) -> LoginResult:
    """Verify credentials (by email) and populate the session on success."""
    identifier = (identifier or "").strip().lower()

    with session_scope() as session:
        user = session.query(User).filter(User.email == identifier).one_or_none()

        if user is None:
            logger.info("Login failed: no account for identifier=%s", identifier)
            return LoginResult(success=False, message="Invalid username/email or password.")

        if not user.is_active:
            audit_service.record(session, user.id, "LOGIN_FAILED_INACTIVE", "User", user.id)
            return LoginResult(success=False, message="This account has been deactivated. Contact an administrator.")

        if not verify_password(password, user.password_hash):
            audit_service.record(session, user.id, "LOGIN_FAILED_INVALID_PASSWORD", "User", user.id)
            logger.info("Login failed: invalid password for identifier=%s", identifier)
            return LoginResult(success=False, message="Invalid username/email or password.")

        user.last_login = datetime.datetime.now(datetime.timezone.utc)
        session_record = {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        }
        audit_service.record(session, user.id, "LOGIN", "User", user.id)

    set_current_user(session_record)
    logger.info("Login succeeded for identifier=%s", identifier)
    return LoginResult(success=True, message="Login successful.")


def logout() -> None:
    """Clear the current session, logging the user out."""
    user = get_current_user()
    clear_session()
    if user:
        with session_scope() as session:
            audit_service.record(session, user.get("id"), "LOGOUT", "User", user.get("id"))
    logger.info("User logged out.")
