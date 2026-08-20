"""
Reporting service.

Builds report data as plain lists of dictionaries so pages can render
them as tables and export them to CSV without duplicating query logic.
Also generates a formal, printable course registration slip (PDF) --
the primary artifact students need to submit to their department/HOD
office as physical proof of registration.
"""

from __future__ import annotations

import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from config import settings
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


def generate_registration_slip_pdf(session: Session, registration_id: int) -> bytes:
    """
    Generate a formal, printable course registration slip for a single
    registration -- the document a student submits (physically or
    electronically) to their department/HOD office as evidence of
    registration. All data is read fresh from the database; nothing is
    fabricated, and the current verification/approval status is shown
    honestly rather than omitted.
    """
    registration = session.get(Registration, registration_id)
    if registration is None:
        raise ValueError("Registration not found.")

    student = registration.student
    user = student.user

    latest_result = (
        session.query(VerificationResult)
        .filter(VerificationResult.registration_id == registration_id)
        .order_by(VerificationResult.verified_at.desc())
        .first()
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SlipTitle", parent=styles["Heading1"], fontSize=15, alignment=1, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "SlipSubtitle", parent=styles["Normal"], fontSize=10, alignment=1,
        textColor=colors.HexColor("#4d5566"), spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "SlipSection", parent=styles["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=6,
        textColor=colors.HexColor("#1f3a63"),
    )
    normal = styles["Normal"]

    elements = []
    elements.append(Paragraph(settings.app.app_name, title_style))
    elements.append(Paragraph("Course Registration Slip", subtitle_style))

    student_info = [
        ["Student Name:", user.full_name, "Matriculation No.:", student.matric_number],
        ["Department:", student.department.name, "Programme:", student.programme.name],
        ["Level:", student.level.name, "Academic Session:", registration.academic_session.name],
        ["Semester:", registration.semester.name, "Registration Status:", registration.status.value],
    ]
    info_table = Table(student_info, colWidths=[3.2 * cm, 5.3 * cm, 3.6 * cm, 4.4 * cm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dde1e6")),
            ]
        )
    )
    elements.append(info_table)

    elements.append(Paragraph("Registered Courses", section_style))
    course_rows = [["Course Code", "Course Title", "Credit Units"]]
    total_units = 0
    for rc in registration.courses:
        course_rows.append([rc.course.code, rc.course.title, str(rc.credit_units)])
        total_units += rc.credit_units
    course_rows.append(["", "Total Credit Units", str(total_units)])

    course_table = Table(course_rows, colWidths=[3 * cm, 10.5 * cm, 3 * cm])
    course_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a63")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dde1e6")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#1f3a63")),
            ]
        )
    )
    elements.append(course_table)

    elements.append(Paragraph("Verification Status", section_style))
    if latest_result is None:
        elements.append(Paragraph("Not yet verified.", normal))
    else:
        elements.append(
            Paragraph(
                f"Status: {latest_result.status.value} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Verified: {latest_result.verified_at.strftime('%d %b %Y, %H:%M')} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Registered Units: {latest_result.total_registered_units}",
                normal,
            )
        )
        open_issues = [i for i in latest_result.issues if i.resolution_status == "Open"]
        if open_issues:
            elements.append(Spacer(1, 4))
            elements.append(Paragraph("Outstanding issues:", normal))
            for issue in open_issues:
                elements.append(Paragraph(f"&bull; {issue.description}", normal))

    elements.append(Spacer(1, 30))
    signature_style = ParagraphStyle("Signature", parent=normal, fontSize=9.5)
    signature_rows = [
        ["_________________________", "", "_________________________"],
        ["Student Signature / Date", "", "Head of Department Signature / Date"],
    ]
    signature_table = Table(signature_rows, colWidths=[7 * cm, 2.5 * cm, 7 * cm])
    signature_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
            ]
        )
    )
    elements.append(signature_table)

    elements.append(Spacer(1, 14))
    footer_style = ParagraphStyle(
        "Footer", parent=normal, fontSize=8, textColor=colors.HexColor("#4d5566"),
    )
    from utils.helpers import format_datetime
    import datetime
    elements.append(
        Paragraph(
            f"Generated {format_datetime(datetime.datetime.now(datetime.timezone.utc))} (UTC). "
            "This slip reflects the registration record at the time of generation.",
            footer_style,
        )
    )

    doc.build(elements)
    return buffer.getvalue()
