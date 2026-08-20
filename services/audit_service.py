"""
Audit logging service.

Centralizes creation of audit records so every layer of the application
records important actions consistently. Audit records are append-only:
no update/delete helper is provided intentionally.

Deliberately takes the caller's active SQLAlchemy session rather than
opening its own: audit events are almost always recorded as part of a
larger business transaction (e.g. registering a course, running
verification), and opening a second, independent session/transaction
against the same SQLite file while the first is still open causes
writer-lock contention. Passing the session keeps everything in one
atomic transaction.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import AuditLog
from utils.logging_config import get_logger

logger = get_logger("services.audit_service")


def record(
    session: Session,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: str | None = None,
) -> None:
    """Add an audit event to the given session. Never pass passwords or secrets in `details`."""
    try:
        session.add(
            AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        )
    except Exception:
        logger.exception("Failed to record audit event action=%s", action)
