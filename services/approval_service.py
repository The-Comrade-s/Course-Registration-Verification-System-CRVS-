"""
Approval workflow service.

Authorized academic officers/administrators review verified registrations
and approve, reject, or return them for correction. A registration with
unresolved blocking (Error severity) issues from its latest verification
run may never be approved.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import (
    ApprovalHistory,
    IssueSeverity,
    Registration,
    RegistrationStatus,
    VerificationResult,
)
from services import audit_service, notification_service
from utils.logging_config import get_logger

logger = get_logger("services.approval_service")


class ApprovalError(Exception):
    pass


def _latest_verification(session: Session, registration_id: int) -> VerificationResult | None:
    return (
        session.query(VerificationResult)
        .filter(VerificationResult.registration_id == registration_id)
        .order_by(VerificationResult.verified_at.desc())
        .first()
    )


def approve_registration(session: Session, registration_id: int, officer_user_id: int, comment: str | None = None) -> Registration:
    registration = session.get(Registration, registration_id)
    if registration is None:
        raise ApprovalError("Registration not found.")

    latest = _latest_verification(session, registration_id)
    if latest is None:
        raise ApprovalError("This registration has not yet been verified.")

    blocking_errors = [i for i in latest.issues if i.severity == IssueSeverity.ERROR]
    if blocking_errors:
        raise ApprovalError("This registration has unresolved errors and cannot be approved.")

    previous_status = registration.status.value
    registration.status = RegistrationStatus.APPROVED

    session.add(
        ApprovalHistory(
            registration_id=registration.id,
            officer_user_id=officer_user_id,
            action="APPROVED",
            previous_status=previous_status,
            new_status=RegistrationStatus.APPROVED.value,
            comment=comment,
        )
    )
    audit_service.record(session, officer_user_id, "REGISTRATION_APPROVED", "Registration", registration.id, details=comment)
    notification_service.notify_student(
        session, registration.student_id, "REGISTRATION_APPROVED",
        "Your course registration has been approved.",
    )
    return registration


def reject_registration(session: Session, registration_id: int, officer_user_id: int, comment: str | None = None) -> Registration:
    registration = session.get(Registration, registration_id)
    if registration is None:
        raise ApprovalError("Registration not found.")

    previous_status = registration.status.value
    registration.status = RegistrationStatus.REJECTED

    session.add(
        ApprovalHistory(
            registration_id=registration.id,
            officer_user_id=officer_user_id,
            action="REJECTED",
            previous_status=previous_status,
            new_status=RegistrationStatus.REJECTED.value,
            comment=comment,
        )
    )
    audit_service.record(session, officer_user_id, "REGISTRATION_REJECTED", "Registration", registration.id, details=comment)
    notification_service.notify_student(
        session, registration.student_id, "REGISTRATION_REJECTED",
        "Your course registration has been rejected. Contact your academic officer for details.",
    )
    return registration


def return_for_correction(session: Session, registration_id: int, officer_user_id: int, comment: str | None = None) -> Registration:
    registration = session.get(Registration, registration_id)
    if registration is None:
        raise ApprovalError("Registration not found.")

    previous_status = registration.status.value
    registration.status = RegistrationStatus.REQUIRES_CORRECTION

    session.add(
        ApprovalHistory(
            registration_id=registration.id,
            officer_user_id=officer_user_id,
            action="RETURNED_FOR_CORRECTION",
            previous_status=previous_status,
            new_status=RegistrationStatus.REQUIRES_CORRECTION.value,
            comment=comment,
        )
    )
    audit_service.record(session, officer_user_id, "REGISTRATION_RETURNED", "Registration", registration.id, details=comment)
    notification_service.notify_student(
        session, registration.student_id, "REGISTRATION_REQUIRES_CORRECTION",
        "Your course registration requires correction. Please review the issues and resubmit.",
    )
    return registration
