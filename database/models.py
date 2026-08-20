"""
SQLAlchemy declarative base and the complete domain model for CRVS.

Built incrementally across CRVS-001 through CRVS-005:
    CRVS-001: Base, SystemInfo
    CRVS-002: User, Student, Staff, Department, Programme, Level,
              AcademicSession, Semester
    CRVS-003: Course, ProgrammeCourseStructure, CoursePrerequisite,
              Registration, RegistrationCourse
    CRVS-004: VerificationResult, VerificationIssue, ApprovalHistory
    CRVS-005: Notification, AuditLog

A single Base.metadata.create_all() call (via database.connection.init_db)
initializes the full schema.
"""

from __future__ import annotations

import datetime
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for every model in the application."""
    pass


# ---------------------------------------------------------------------------
# CRVS-001 foundation
# ---------------------------------------------------------------------------

class SystemInfo(Base):
    __tablename__ = "system_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# CRVS-002: Roles, Users, Academic structure
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    ADMINISTRATOR = "Administrator"
    ACADEMIC_OFFICER = "Academic Officer"
    STUDENT = "Student"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_login: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    student_profile: Mapped["Student"] = relationship(back_populates="user", uselist=False)
    staff_profile: Mapped["Staff"] = relationship(back_populates="user", uselist=False)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    programmes: Mapped[list["Programme"]] = relationship(back_populates="department")
    staff: Mapped[list["Staff"]] = relationship(back_populates="department")
    students: Mapped[list["Student"]] = relationship(back_populates="department")


class Programme(Base):
    __tablename__ = "programmes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, default=4)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    department: Mapped[Department] = relationship(back_populates="programmes")
    students: Mapped[list["Student"]] = relationship(back_populates="programme")


class Level(Base):
    __tablename__ = "levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    numeric_value: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AcademicSession(Base):
    __tablename__ = "academic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    start_date: Mapped[datetime.date | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime.date | None] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    semesters: Mapped[list["Semester"]] = relationship(back_populates="academic_session")


class Semester(Base):
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    academic_session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    academic_session: Mapped[AcademicSession] = relationship(back_populates="semesters")

    __table_args__ = (UniqueConstraint("name", "academic_session_id", name="uq_semester_session"),)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    matric_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"), nullable=False)
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id"), nullable=False)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    academic_status: Mapped[str] = mapped_column(String(30), default="Active")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="student_profile")
    department: Mapped[Department] = relationship(back_populates="students")
    programme: Mapped[Programme] = relationship(back_populates="students")
    level: Mapped[Level] = relationship()
    registrations: Mapped[list["Registration"]] = relationship(back_populates="student")


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    user: Mapped[User] = relationship(back_populates="staff_profile")
    department: Mapped[Department] = relationship(back_populates="staff")


# ---------------------------------------------------------------------------
# CRVS-003: Courses, course structure, prerequisites, registration
# ---------------------------------------------------------------------------

class CourseType(str, enum.Enum):
    COMPULSORY = "Compulsory"
    ELECTIVE = "Elective"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_units: Mapped[int] = mapped_column(Integer, nullable=False)
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id"), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    level: Mapped[Level] = relationship()
    department: Mapped[Department] = relationship()


class ProgrammeCourseStructure(Base):
    """Defines which courses apply to a programme/level/session/semester, and how."""

    __tablename__ = "programme_course_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"), nullable=False)
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id"), nullable=False)
    academic_session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"), nullable=False)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    requirement_type: Mapped[CourseType] = mapped_column(Enum(CourseType), nullable=False)

    programme: Mapped[Programme] = relationship()
    level: Mapped[Level] = relationship()
    academic_session: Mapped[AcademicSession] = relationship()
    semester: Mapped[Semester] = relationship()
    course: Mapped[Course] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "programme_id", "level_id", "academic_session_id", "semester_id", "course_id",
            name="uq_programme_course_structure",
        ),
    )


class ProgrammeElectiveRule(Base):
    """
    Elective and overall credit-load requirements for a programme/level/
    session/semester context. Elective unit limits constrain only the
    elective courses within a registration; total unit limits constrain
    the registration's entire credit load (compulsory + elective).
    """

    __tablename__ = "programme_elective_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programmes.id"), nullable=False)
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id"), nullable=False)
    academic_session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"), nullable=False)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"), nullable=False)
    min_electives: Mapped[int] = mapped_column(Integer, default=0)
    max_electives: Mapped[int] = mapped_column(Integer, default=0)
    elective_min_units: Mapped[int] = mapped_column(Integer, default=0)
    elective_max_units: Mapped[int] = mapped_column(Integer, default=0)
    total_min_units: Mapped[int] = mapped_column(Integer, default=0)
    total_max_units: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint(
            "programme_id", "level_id", "academic_session_id", "semester_id",
            name="uq_programme_elective_rule",
        ),
    )


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    prerequisite_course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    course: Mapped[Course] = relationship(foreign_keys=[course_id])
    prerequisite_course: Mapped[Course] = relationship(foreign_keys=[prerequisite_course_id])

    __table_args__ = (
        UniqueConstraint("course_id", "prerequisite_course_id", name="uq_course_prerequisite"),
    )


class CompletedCourse(Base):
    """
    Minimal academic-history record used solely to determine whether a
    student has previously completed a prerequisite course. Full transcript
    management is outside the scope of CRVS; this table exists only to
    support prerequisite verification honestly, without fabricating history.
    """

    __tablename__ = "completed_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    academic_session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_completed_course"),)


class RegistrationStatus(str, enum.Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "Under Review"
    REQUIRES_CORRECTION = "Requires Correction"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    academic_session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"), nullable=False)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"), nullable=False)
    status: Mapped[RegistrationStatus] = mapped_column(Enum(RegistrationStatus), default=RegistrationStatus.DRAFT)
    submitted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    student: Mapped[Student] = relationship(back_populates="registrations")
    academic_session: Mapped[AcademicSession] = relationship()
    semester: Mapped[Semester] = relationship()
    courses: Mapped[list["RegistrationCourse"]] = relationship(back_populates="registration", cascade="all, delete-orphan")
    verification_results: Mapped[list["VerificationResult"]] = relationship(back_populates="registration")

    __table_args__ = (
        UniqueConstraint("student_id", "academic_session_id", "semester_id", name="uq_registration_per_semester"),
    )


class RegistrationCourse(Base):
    __tablename__ = "registration_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    credit_units: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    registration: Mapped[Registration] = relationship(back_populates="courses")
    course: Mapped[Course] = relationship()

    __table_args__ = (UniqueConstraint("registration_id", "course_id", name="uq_registration_course"),)


# ---------------------------------------------------------------------------
# CRVS-004: Verification and approval
# ---------------------------------------------------------------------------

class VerificationStatus(str, enum.Enum):
    PENDING = "Pending"
    PASSED = "Passed"
    FAILED = "Failed"
    REQUIRES_CORRECTION = "Requires Correction"


class IssueSeverity(str, enum.Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFORMATION = "Information"


class IssueType(str, enum.Enum):
    MISSING_COMPULSORY_COURSE = "MISSING_COMPULSORY_COURSE"
    INVALID_COURSE = "INVALID_COURSE"
    DUPLICATE_COURSE = "DUPLICATE_COURSE"
    CREDIT_LOAD_TOO_LOW = "CREDIT_LOAD_TOO_LOW"
    CREDIT_LOAD_TOO_HIGH = "CREDIT_LOAD_TOO_HIGH"
    ELECTIVE_REQUIREMENT_NOT_MET = "ELECTIVE_REQUIREMENT_NOT_MET"
    TOO_MANY_ELECTIVES = "TOO_MANY_ELECTIVES"
    PREREQUISITE_NOT_SATISFIED = "PREREQUISITE_NOT_SATISFIED"
    INVALID_SEMESTER = "INVALID_SEMESTER"
    INACTIVE_COURSE = "INACTIVE_COURSE"
    REGISTRATION_DATA_ERROR = "REGISTRATION_DATA_ERROR"


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    total_registered_units: Mapped[int] = mapped_column(Integer, default=0)
    required_min_units: Mapped[int] = mapped_column(Integer, default=0)
    required_max_units: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    registration: Mapped[Registration] = relationship(back_populates="verification_results")
    issues: Mapped[list["VerificationIssue"]] = relationship(back_populates="verification_result", cascade="all, delete-orphan")


class VerificationIssue(Base):
    __tablename__ = "verification_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verification_result_id: Mapped[int] = mapped_column(ForeignKey("verification_results.id"), nullable=False)
    issue_type: Mapped[IssueType] = mapped_column(Enum(IssueType), nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(Enum(IssueSeverity), default=IssueSeverity.ERROR)
    course_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actual_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(20), default="Open")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    verification_result: Mapped[VerificationResult] = relationship(back_populates="issues")


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), nullable=False)
    officer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    registration: Mapped[Registration] = relationship()
    officer: Mapped[User] = relationship()


# ---------------------------------------------------------------------------
# CRVS-005: Notifications and audit logging
# ---------------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User | None] = relationship()
