"""
Development seed data.

Creates a small, clearly fictional dataset sufficient to exercise the
entire CRVS workflow end to end: one administrator, one academic officer,
a department, a programme, academic levels, an academic session and
semester, a course catalogue with compulsory/elective courses and a
prerequisite, a programme course structure, and two student accounts.

This data is for development/demo purposes only and must not be used in
production. Development credentials are documented in the README.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from database.connection import session_scope
from database.models import (
    AcademicSession,
    CompletedCourse,
    Course,
    CoursePrerequisite,
    Department,
    Level,
    Programme,
    ProgrammeCourseStructure,
    ProgrammeElectiveRule,
    Semester,
    Staff,
    Student,
    SystemInfo,
    User,
    UserRole,
    CourseType,
)
from config import settings
from utils.logging_config import get_logger
from utils.security import hash_password

logger = get_logger("database.seed")

DEV_PASSWORD = "ChangeMe123!"


def seed_system_info() -> None:
    with session_scope() as session:
        existing = session.query(SystemInfo).filter_by(key="app_version").one_or_none()
        if existing is None:
            session.add(SystemInfo(key="app_version", value=settings.app.app_version))
        else:
            existing.value = settings.app.app_version


def run_seed() -> None:
    """Entry point for development seeding. Safe to call repeatedly (idempotent)."""
    seed_system_info()

    with session_scope() as session:
        if session.query(User).count() > 0:
            logger.info("Seed data already present; skipping.")
            return

        try:
            logger.info("Seeding development data.")
            _insert_seed_data(session)
        except IntegrityError:
            # Two cold-start requests can both pass the "count() > 0" check
            # before either commits (e.g. two browser tabs opening the app
            # at the same moment). The loser of that race hits a unique
            # constraint here; that's expected and harmless -- the winner
            # already seeded the data -- so it's logged at info level and
            # swallowed rather than surfaced as an application error.
            session.rollback()
            logger.info("Seed data was created concurrently by another session; skipping.")
            return


def _insert_seed_data(session) -> None:

        # --- Academic structure -------------------------------------------------
        department = Department(name="Computer Science", code="CSC", description="Department of Computer Science")
        session.add(department)
        session.flush()

        programme = Programme(
            name="B.Sc. Computer Science", code="BSCCSC", department_id=department.id, duration_years=4
        )
        session.add(programme)
        session.flush()

        level_100 = Level(name="100 Level", numeric_value=100)
        level_200 = Level(name="200 Level", numeric_value=200)
        level_300 = Level(name="300 Level", numeric_value=300)
        session.add_all([level_100, level_200, level_300])
        session.flush()

        academic_session = AcademicSession(name="2025/2026", is_current=True)
        session.add(academic_session)
        session.flush()

        semester_1 = Semester(name="First Semester", academic_session_id=academic_session.id, is_current=True)
        semester_2 = Semester(name="Second Semester", academic_session_id=academic_session.id, is_current=False)
        session.add_all([semester_1, semester_2])
        session.flush()

        # --- Courses --------------------------------------------------------------
        csc201 = Course(code="CSC201", title="Introduction to Programming", credit_units=3,
                         level_id=level_200.id, department_id=department.id)
        csc301 = Course(code="CSC301", title="Data Structures and Algorithms", credit_units=4,
                         level_id=level_300.id, department_id=department.id)
        csc303 = Course(code="CSC303", title="Database Systems", credit_units=3,
                         level_id=level_300.id, department_id=department.id)
        csc305 = Course(code="CSC305", title="Operating Systems", credit_units=3,
                         level_id=level_300.id, department_id=department.id)
        mth301 = Course(code="MTH301", title="Numerical Methods", credit_units=3,
                         level_id=level_300.id, department_id=department.id)
        gst301 = Course(code="GST301", title="Entrepreneurship Studies", credit_units=2,
                         level_id=level_300.id, department_id=department.id)
        session.add_all([csc201, csc301, csc303, csc305, mth301, gst301])
        session.flush()

        # Prerequisite: CSC301 requires CSC201
        session.add(CoursePrerequisite(course_id=csc301.id, prerequisite_course_id=csc201.id))

        # --- Programme course structure: 300 Level, First Semester ---------------
        structure_rows = [
            (csc301.id, CourseType.COMPULSORY),
            (csc303.id, CourseType.COMPULSORY),
            (csc305.id, CourseType.COMPULSORY),
            (mth301.id, CourseType.ELECTIVE),
            (gst301.id, CourseType.ELECTIVE),
        ]
        for course_id, requirement_type in structure_rows:
            session.add(
                ProgrammeCourseStructure(
                    programme_id=programme.id,
                    level_id=level_300.id,
                    academic_session_id=academic_session.id,
                    semester_id=semester_1.id,
                    course_id=course_id,
                    requirement_type=requirement_type,
                )
            )

        session.add(
            ProgrammeElectiveRule(
                programme_id=programme.id,
                level_id=level_300.id,
                academic_session_id=academic_session.id,
                semester_id=semester_1.id,
                min_electives=1,
                max_electives=2,
                elective_min_units=2,
                elective_max_units=5,
                total_min_units=10,
                total_max_units=18,
            )
        )

        # --- Users -----------------------------------------------------------------
        admin_user = User(
            full_name="System Administrator",
            email="admin@crvs.local",
            password_hash=hash_password(DEV_PASSWORD),
            role=UserRole.ADMINISTRATOR,
        )
        officer_user = User(
            full_name="Amina Bello",
            email="officer@crvs.local",
            password_hash=hash_password(DEV_PASSWORD),
            role=UserRole.ACADEMIC_OFFICER,
        )
        student_user_1 = User(
            full_name="Tunde Adekunle",
            email="student1@crvs.local",
            password_hash=hash_password(DEV_PASSWORD),
            role=UserRole.STUDENT,
        )
        student_user_2 = User(
            full_name="Ngozi Eze",
            email="student2@crvs.local",
            password_hash=hash_password(DEV_PASSWORD),
            role=UserRole.STUDENT,
        )
        session.add_all([admin_user, officer_user, student_user_1, student_user_2])
        session.flush()

        session.add(Staff(staff_id="STF001", user_id=officer_user.id, department_id=department.id))

        student_1 = Student(
            matric_number="CSC/2023/001",
            user_id=student_user_1.id,
            department_id=department.id,
            programme_id=programme.id,
            level_id=level_300.id,
            admission_year=2023,
        )
        student_2 = Student(
            matric_number="CSC/2023/002",
            user_id=student_user_2.id,
            department_id=department.id,
            programme_id=programme.id,
            level_id=level_300.id,
            admission_year=2023,
        )
        session.add_all([student_1, student_2])
        session.flush()

        # Student 1 has already completed CSC201 (prerequisite for CSC301).
        session.add(CompletedCourse(student_id=student_1.id, course_id=csc201.id, passed=True))
        # Student 2 has NOT completed CSC201, to demonstrate prerequisite failure.

        logger.info("Development seed data created.")
