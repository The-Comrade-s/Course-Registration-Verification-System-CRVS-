"""
Automated course registration verification engine.

Independent of the Streamlit UI: pages call run_verification() and render
whatever VerificationResult/VerificationIssue records it produces. The
engine loads the student's actual configured academic context (programme,
level, session, semester, course structure, prerequisites, completed
courses) and never hard-codes course codes or programme assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from database.models import (
    CompletedCourse,
    Course,
    CoursePrerequisite,
    CourseType,
    IssueSeverity,
    IssueType,
    ProgrammeCourseStructure,
    ProgrammeElectiveRule,
    Registration,
    RegistrationCourse,
    RegistrationStatus,
    Student,
    VerificationIssue,
    VerificationResult,
    VerificationStatus,
)
from services import audit_service
from utils.logging_config import get_logger

logger = get_logger("services.verification_engine")


@dataclass
class _Finding:
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    course_code: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None


@dataclass
class VerificationOutcome:
    status: VerificationStatus
    total_units: int
    required_min_units: int
    required_max_units: int
    findings: list[_Finding] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.status == VerificationStatus.PASSED:
            return "Registration is valid. No blocking issues were found."
        error_count = sum(1 for f in self.findings if f.severity == IssueSeverity.ERROR)
        return f"{error_count} issue(s) require correction before this registration can be approved."


def _evaluate(session: Session, registration: Registration) -> VerificationOutcome:
    findings: list[_Finding] = []

    student: Student | None = session.get(Student, registration.student_id)
    if student is None or not student.is_active:
        findings.append(
            _Finding(
                IssueType.REGISTRATION_DATA_ERROR,
                IssueSeverity.ERROR,
                "The student record for this registration is missing or inactive.",
            )
        )
        return VerificationOutcome(VerificationStatus.FAILED, 0, 0, 0, findings)

    reg_courses = registration.courses
    course_ids = [rc.course_id for rc in reg_courses]

    # Duplicate courses
    seen: set[int] = set()
    for rc in reg_courses:
        if rc.course_id in seen:
            course = session.get(Course, rc.course_id)
            findings.append(
                _Finding(
                    IssueType.DUPLICATE_COURSE,
                    IssueSeverity.ERROR,
                    f"Course {course.code if course else rc.course_id} is registered more than once.",
                    course_code=course.code if course else None,
                )
            )
        seen.add(rc.course_id)

    # Load the applicable programme course structure for this student's context.
    structure_rows = (
        session.query(ProgrammeCourseStructure)
        .filter(
            ProgrammeCourseStructure.programme_id == student.programme_id,
            ProgrammeCourseStructure.level_id == student.level_id,
            ProgrammeCourseStructure.academic_session_id == registration.academic_session_id,
            ProgrammeCourseStructure.semester_id == registration.semester_id,
        )
        .all()
    )
    valid_course_ids = {row.course_id for row in structure_rows}
    compulsory_course_ids = {row.course_id for row in structure_rows if row.requirement_type == CourseType.COMPULSORY}
    elective_course_ids = {row.course_id for row in structure_rows if row.requirement_type == CourseType.ELECTIVE}

    # Course validity, activity, and semester/level/programme applicability.
    total_units = 0
    for rc in reg_courses:
        course = session.get(Course, rc.course_id)
        if course is None:
            findings.append(_Finding(IssueType.INVALID_COURSE, IssueSeverity.ERROR,
                                      "A registered course no longer exists in the catalogue."))
            continue

        total_units += rc.credit_units

        if not course.is_active:
            findings.append(
                _Finding(IssueType.INACTIVE_COURSE, IssueSeverity.ERROR,
                          f"{course.code} is not currently active.", course_code=course.code)
            )

        if course.id not in valid_course_ids:
            findings.append(
                _Finding(
                    IssueType.INVALID_COURSE,
                    IssueSeverity.ERROR,
                    f"{course.code} is not configured for this programme, level, session and semester.",
                    course_code=course.code,
                )
            )

    # Missing compulsory courses.
    for course_id in compulsory_course_ids - set(course_ids):
        course = session.get(Course, course_id)
        findings.append(
            _Finding(
                IssueType.MISSING_COMPULSORY_COURSE,
                IssueSeverity.ERROR,
                f"Compulsory course {course.code if course else course_id} is missing from the registration.",
                course_code=course.code if course else None,
            )
        )

    # Elective requirements.
    elective_rule = (
        session.query(ProgrammeElectiveRule)
        .filter(
            ProgrammeElectiveRule.programme_id == student.programme_id,
            ProgrammeElectiveRule.level_id == student.level_id,
            ProgrammeElectiveRule.academic_session_id == registration.academic_session_id,
            ProgrammeElectiveRule.semester_id == registration.semester_id,
        )
        .one_or_none()
    )
    registered_electives = [c for c in course_ids if c in elective_course_ids]
    elective_units = sum(rc.credit_units for rc in reg_courses if rc.course_id in elective_course_ids)
    if elective_rule:
        if len(registered_electives) < elective_rule.min_electives:
            findings.append(
                _Finding(
                    IssueType.ELECTIVE_REQUIREMENT_NOT_MET,
                    IssueSeverity.ERROR,
                    f"At least {elective_rule.min_electives} elective course(s) are required; "
                    f"{len(registered_electives)} registered.",
                    expected_value=str(elective_rule.min_electives),
                    actual_value=str(len(registered_electives)),
                )
            )
        if elective_rule.max_electives and len(registered_electives) > elective_rule.max_electives:
            findings.append(
                _Finding(
                    IssueType.TOO_MANY_ELECTIVES,
                    IssueSeverity.ERROR,
                    f"No more than {elective_rule.max_electives} elective course(s) are permitted; "
                    f"{len(registered_electives)} registered.",
                    expected_value=str(elective_rule.max_electives),
                    actual_value=str(len(registered_electives)),
                )
            )
        if elective_rule.elective_min_units and elective_units < elective_rule.elective_min_units:
            findings.append(
                _Finding(
                    IssueType.ELECTIVE_REQUIREMENT_NOT_MET,
                    IssueSeverity.ERROR,
                    f"Elective credit units ({elective_units}) are below the minimum required "
                    f"({elective_rule.elective_min_units}).",
                    expected_value=str(elective_rule.elective_min_units),
                    actual_value=str(elective_units),
                )
            )
        if elective_rule.elective_max_units and elective_units > elective_rule.elective_max_units:
            findings.append(
                _Finding(
                    IssueType.TOO_MANY_ELECTIVES,
                    IssueSeverity.ERROR,
                    f"Elective credit units ({elective_units}) exceed the maximum permitted "
                    f"({elective_rule.elective_max_units}).",
                    expected_value=str(elective_rule.elective_max_units),
                    actual_value=str(elective_units),
                )
            )

    # Overall credit load (compulsory + elective combined).
    required_min = elective_rule.total_min_units if elective_rule else 0
    required_max = elective_rule.total_max_units if elective_rule else 0
    if required_min and total_units < required_min:
        findings.append(
            _Finding(
                IssueType.CREDIT_LOAD_TOO_LOW,
                IssueSeverity.ERROR,
                f"Registered credit load ({total_units}) is below the minimum required ({required_min}).",
                expected_value=str(required_min),
                actual_value=str(total_units),
            )
        )
    if required_max and total_units > required_max:
        findings.append(
            _Finding(
                IssueType.CREDIT_LOAD_TOO_HIGH,
                IssueSeverity.ERROR,
                f"Registered credit load ({total_units}) exceeds the maximum permitted ({required_max}).",
                expected_value=str(required_max),
                actual_value=str(total_units),
            )
        )

    # Prerequisites.
    completed_ids = {
        cc.course_id
        for cc in session.query(CompletedCourse).filter(
            CompletedCourse.student_id == student.id, CompletedCourse.passed.is_(True)
        )
    }
    for rc in reg_courses:
        prereqs = session.query(CoursePrerequisite).filter(CoursePrerequisite.course_id == rc.course_id).all()
        for prereq in prereqs:
            if prereq.prerequisite_course_id not in completed_ids:
                course = session.get(Course, rc.course_id)
                prereq_course = session.get(Course, prereq.prerequisite_course_id)
                findings.append(
                    _Finding(
                        IssueType.PREREQUISITE_NOT_SATISFIED,
                        IssueSeverity.ERROR,
                        f"{course.code if course else rc.course_id} requires "
                        f"{prereq_course.code if prereq_course else prereq.prerequisite_course_id}, "
                        "which has not been completed.",
                        course_code=course.code if course else None,
                        expected_value=prereq_course.code if prereq_course else None,
                    )
                )

    has_errors = any(f.severity == IssueSeverity.ERROR for f in findings)
    status = VerificationStatus.REQUIRES_CORRECTION if has_errors else VerificationStatus.PASSED

    return VerificationOutcome(status, total_units, required_min, required_max, findings)


def run_verification(session: Session, registration_id: int, performed_by_user_id: int | None = None) -> VerificationResult:
    """
    Execute a full verification run on a submitted registration and persist
    the result and its individual issues. Previous verification runs are
    preserved -- this always creates a new VerificationResult record.
    """
    registration = session.get(Registration, registration_id)
    if registration is None:
        raise ValueError("Registration not found.")

    outcome = _evaluate(session, registration)

    result = VerificationResult(
        registration_id=registration.id,
        status=outcome.status,
        total_registered_units=outcome.total_units,
        required_min_units=outcome.required_min_units,
        required_max_units=outcome.required_max_units,
        summary=outcome.summary,
    )
    session.add(result)
    session.flush()

    for finding in outcome.findings:
        session.add(
            VerificationIssue(
                verification_result_id=result.id,
                issue_type=finding.issue_type,
                severity=finding.severity,
                course_code=finding.course_code,
                description=finding.description,
                expected_value=finding.expected_value,
                actual_value=finding.actual_value,
            )
        )

    registration.status = (
        RegistrationStatus.UNDER_REVIEW
        if outcome.status == VerificationStatus.PASSED
        else RegistrationStatus.REQUIRES_CORRECTION
    )

    session.flush()
    session.refresh(result, attribute_names=["issues"])

    audit_service.record(
        session, performed_by_user_id, "VERIFICATION_COMPLETED", "Registration", registration.id,
        details=f"status={outcome.status.value}, issues={len(outcome.findings)}",
    )

    return result
