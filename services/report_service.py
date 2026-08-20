"""
Reporting service.

Builds report data as plain lists of dictionaries so pages can render
them as tables and export them to CSV without duplicating query logic.
"""

from __future__ import annotations

import io

import pandas as pd
from sqlalchemy.orm import Session

from database.models import (
    Course,
    Registration,
    RegistrationCourse,
    Student,
    User,
    VerificationResult,
)


def student_registration_report(session: Session, student_id: int | None = None) -> pd.DataFrame:
    query = (
        session.query(Registration, Student, User)
        .join(Student, Registration.student_id == Student.id)
        .join(User, Student.user_id == User.id)
    )
    if student_id is not None:
        query = query.filter(Student.id == student_id)

    rows = []
    for registration, student, user in query.all():
        total_units = sum(rc.credit_units for rc in registration.courses)
        rows.append(
            {
                "Student ID": student.matric_number,
                "Student Name": user.full_name,
                "Session": registration.academic_session.name,
                "Semester": registration.semester.name,
                "Courses": len(registration.courses),
                "Total Units": total_units,
                "Status": registration.status.value,
                "Submitted At": registration.submitted_at,
            }
        )
    return pd.DataFrame(rows)


def verification_report(session: Session) -> pd.DataFrame:
    rows = []
    for result in session.query(VerificationResult).order_by(VerificationResult.verified_at.desc()).all():
        registration = result.registration
        student = registration.student
        rows.append(
            {
                "Student ID": student.matric_number,
                "Session": registration.academic_session.name,
                "Semester": registration.semester.name,
                "Status": result.status.value,
                "Total Units": result.total_registered_units,
                "Issues": len(result.issues),
                "Verified At": result.verified_at,
            }
        )
    return pd.DataFrame(rows)


def to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    dataframe.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")
