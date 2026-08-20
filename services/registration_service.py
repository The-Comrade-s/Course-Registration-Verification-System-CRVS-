"""
Student course registration service.

Handles draft creation, adding/removing courses, and submission. Keeps
this logic out of the Streamlit page so it stays testable and reusable.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import (
    Course,
    ProgrammeCourseStructure,
    Registration,
    RegistrationCourse,
    RegistrationStatus,
    Student,
)
from services import audit_service, notification_service
from utils.logging_config import get_logger

logger = get_logger("services.registration_service")


class RegistrationError(Exception):
    pass


def get_or_create_draft(session: Session, student_id: int, academic_session_id: int, semester_id: int) -> Registration:
    registration = (
        session.query(Registration)
        .filter(
            Registration.student_id == student_id,
            Registration.academic_session_id == academic_session_id,
            Registration.semester_id == semester_id,
        )
        .one_or_none()
    )
    if registration is None:
        registration = Registration(
            student_id=student_id,
            academic_session_id=academic_session_id,
            semester_id=semester_id,
            status=RegistrationStatus.DRAFT,
        )
        session.add(registration)
        session.flush()
        audit_service.record(session, None, "REGISTRATION_CREATED", "Registration", registration.id)
    return registration


def get_available_courses(session: Session, student: Student, academic_session_id: int, semester_id: int) -> list[Course]:
    structure_rows = (
        session.query(ProgrammeCourseStructure)
        .filter(
            ProgrammeCourseStructure.programme_id == student.programme_id,
            ProgrammeCourseStructure.level_id == student.level_id,
            ProgrammeCourseStructure.academic_session_id == academic_session_id,
            ProgrammeCourseStructure.semester_id == semester_id,
        )
        .all()
    )
    course_ids = [row.course_id for row in structure_rows]
    if not course_ids:
        return []
    return (
        session.query(Course)
        .filter(Course.id.in_(course_ids), Course.is_active.is_(True))
        .order_by(Course.code)
        .all()
    )


def add_course(session: Session, registration: Registration, course: Course) -> None:
    if registration.status != RegistrationStatus.DRAFT:
        raise RegistrationError("Only a draft registration can be modified.")
    existing = (
        session.query(RegistrationCourse)
        .filter(RegistrationCourse.registration_id == registration.id, RegistrationCourse.course_id == course.id)
        .one_or_none()
    )
    if existing is not None:
        raise RegistrationError(f"{course.code} is already registered.")
    session.add(
        RegistrationCourse(registration_id=registration.id, course_id=course.id, credit_units=course.credit_units)
    )
    session.flush()
    session.expire(registration, ["courses"])
    audit_service.record(session, None, "COURSE_ADDED", "Registration", registration.id, details=course.code)


def remove_course(session: Session, registration: Registration, course_id: int) -> None:
    if registration.status != RegistrationStatus.DRAFT:
        raise RegistrationError("Only a draft registration can be modified.")
    entry = (
        session.query(RegistrationCourse)
        .filter(RegistrationCourse.registration_id == registration.id, RegistrationCourse.course_id == course_id)
        .one_or_none()
    )
    if entry is not None:
        session.delete(entry)
        session.flush()
        session.expire(registration, ["courses"])
        audit_service.record(session, None, "COURSE_REMOVED", "Registration", registration.id, details=str(course_id))


def submit_registration(session: Session, registration: Registration) -> None:
    import datetime

    if registration.status not in (RegistrationStatus.DRAFT, RegistrationStatus.REQUIRES_CORRECTION):
        raise RegistrationError("This registration cannot be submitted from its current status.")
    if not registration.courses:
        raise RegistrationError("At least one course must be registered before submission.")

    registration.status = RegistrationStatus.SUBMITTED
    registration.submitted_at = datetime.datetime.now(datetime.timezone.utc)
    audit_service.record(session, None, "REGISTRATION_SUBMITTED", "Registration", registration.id)
    notification_service.notify_student(
        session, registration.student_id, "REGISTRATION_SUBMITTED",
        "Your course registration has been submitted and is awaiting verification.",
    )
