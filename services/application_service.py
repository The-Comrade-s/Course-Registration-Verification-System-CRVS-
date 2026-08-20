"""
Application service layer foundation.

Business logic that spans multiple pages or coordinates multiple models
should live in dedicated service modules like this one, rather than being
duplicated inside individual Streamlit pages. CRVS-001 defines the
pattern; later stages add real domain services (registration_service,
verification_engine, approval_service, notification_service,
report_service, audit_service) alongside this one.
"""

from __future__ import annotations

from utils.logging_config import get_logger

logger = get_logger("services.application_service")


def get_application_status() -> dict[str, str]:
    """
    Return a small structural status summary.

    Used by the foundation test suite to verify that the service layer
    itself is importable and callable end to end.
    """
    from config import settings

    return {
        "app_name": settings.app.app_name,
        "app_version": settings.app.app_version,
        "environment": settings.app.environment,
    }
