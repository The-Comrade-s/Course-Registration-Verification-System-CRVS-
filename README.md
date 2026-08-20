# Course Registration Verification System (CRVS)

## Project Description

CRVS is a web-based Course Registration Verification System for tertiary
institutions, built as a single Python/Streamlit application. Students
register courses; the system automatically verifies those registrations
against configured academic rules (compulsory courses, elective
requirements, credit-unit load, and prerequisites); and authorized
academic officers review and approve valid registrations.

This repository contains the complete system through **CRVS-005**: all
five planned development stages plus the final integration pass.

## Objectives

- A single, coherent Python/Streamlit application (no separate frontend/
  backend services).
- A modular, maintainable, testable architecture.
- Data-driven academic configuration -- no institution, programme,
  course code, or credit-load assumption is hard-coded.
- An automated verification engine that identifies specific, actionable
  issues rather than a generic pass/fail.
- A complete, auditable approval workflow.

## User Roles

| Role | Capabilities |
|---|---|
| **Administrator** | Full system access: users, academic structure, courses, all reports, audit log. |
| **Academic Officer** | Manages students, courses and course structure; reviews, verifies, and approves/rejects registrations within the institution. |
| **Student** | Manages their own registration, views verification results, corrects and resubmits, views their own reports and notifications. |

## Technology Stack

- Python 3.x
- Streamlit
- SQLAlchemy (SQLite by default; the engine URL is the only thing that
  changes to move to PostgreSQL)
- bcrypt (password hashing)
- pandas (report building / CSV export)

## Project Structure

```
course_registration_verification/
├── app.py                       Main entry point (routing, sidebar, theming)
├── config.py                    Centralized configuration
├── requirements.txt
├── README.md
│
├── database/
│   ├── connection.py             Engine, session factory, init_db(), session_scope()
│   ├── models.py                 Full domain model (see below)
│   └── seed.py                   Development seed data (idempotent)
│
├── auth/
│   ├── authentication.py         bcrypt-backed login/logout, audit-logged
│   ├── authorization.py          require_authentication, require_role, can_access, RBAC constants
│   └── session.py                Streamlit session-state contract
│
├── pages/
│   ├── login.py                  Login screen
│   ├── dashboard.py               Role-specific live dashboard
│   ├── students.py                Student management (Administrator / Academic Officer)
│   ├── courses.py                 Course catalogue, programme course structure, prerequisites
│   ├── programmes.py              Programme management
│   ├── registration.py            Student registration workflow + staff registration list
│   ├── verification.py            Student verification results + staff review/approve
│   ├── reports.py                 Registration/verification reports with CSV export
│   ├── administration.py          Users, staff, departments, levels, sessions, semesters, audit log
│   └── settings.py                Notifications, password change
│
├── services/
│   ├── registration_service.py    Draft/add/remove/submit registration logic
│   ├── verification_engine.py     The automated verification engine (CRVS-004 core)
│   ├── approval_service.py        Approve / reject / return-for-correction workflow
│   ├── notification_service.py    Internal notifications
│   ├── report_service.py          Report data + CSV export
│   ├── audit_service.py           Append-only audit logging (session-scoped)
│   └── application_service.py     Foundation status helper
│
├── utils/
│   ├── validators.py, security.py (bcrypt), helpers.py
│   ├── ui_components.py           Reusable header/metric/card/badge components
│   ├── theme.py                   Light/dark theme mechanism
│   ├── error_handling.py          safe_page decorator (no raw tracebacks to users)
│   └── logging_config.py          Centralized logging
│
├── assets/styles.css              Institutional design system (deep blue / off-white / dark)
│
└── tests/
    ├── run_all.py                       Runs every test module in its own subprocess
    ├── test_foundation.py               Imports, config, DB layer
    ├── test_auth_and_structure.py       Password hashing, login, RBAC, academic structure
    └── test_registration_and_verification.py
        Course management, registration workflow, verification engine, approval workflow
```

## Domain Model

`database/models.py` defines the complete schema:

- **Identity & structure**: `User`, `Department`, `Programme`, `Level`,
  `AcademicSession`, `Semester`, `Student`, `Staff`
- **Courses**: `Course`, `ProgrammeCourseStructure` (programme + level +
  session + semester -> course, compulsory/elective), `ProgrammeElectiveRule`
  (elective count/unit limits and overall credit-load limits, kept
  separate so one never silently constrains the other), `CoursePrerequisite`,
  `CompletedCourse` (minimal academic history, used only for honest
  prerequisite verification)
- **Registration**: `Registration`, `RegistrationCourse`
- **Verification & approval**: `VerificationResult`, `VerificationIssue`,
  `ApprovalHistory`
- **CRVS-005**: `Notification`, `AuditLog`

All relationships use real foreign keys and unique constraints (e.g. one
registration per student per session/semester, one course per
registration, unique course codes, unique department/programme codes).

## The Verification Engine

`services/verification_engine.run_verification()` loads the student's
actual configured academic context and checks, in one pass:

- Course validity for the student's programme/level/session/semester
- Inactive courses
- Duplicate courses
- Missing compulsory courses (every one, not just the first)
- Elective count and elective credit-unit requirements
- Overall registration credit load (min/max)
- Prerequisites, checked against real completed-course records (never
  fabricated)

Every verification run is persisted as a new `VerificationResult` with
individual `VerificationIssue` rows -- history is never overwritten, so a
registration can be corrected and reverified with a full audit trail.
Approval is blocked at the service layer whenever the latest run has any
unresolved `Error`-severity issue, regardless of what the UI shows.

## Installation

```bash
cd course_registration_verification
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Read from environment variables (or `.streamlit/secrets.toml`), with
development defaults. No secrets are hard-coded.

| Variable | Purpose | Default |
|---|---|---|
| `CRVS_APP_NAME` | Displayed institution/system name | Course Registration Verification System |
| `CRVS_ENVIRONMENT` | `development` / `production` | development |
| `CRVS_DATABASE_URL` | SQLAlchemy database URL | `sqlite:///crvs.db` |
| `CRVS_DEFAULT_THEME` | `light` / `dark` | light |

## Database Setup and Seed Data

The schema is created automatically on first run (`init_db()`), and
`database/seed.py` populates a small, clearly fictional development
dataset the first time the `users` table is empty (safe to call
repeatedly -- it is a no-op once data exists):

- 1 Administrator, 1 Academic Officer, 2 Students
- 1 department, 1 programme, 3 levels, 1 academic session, 2 semesters
- 6 courses, a programme course structure (compulsory + elective), one
  prerequisite, and an elective/credit-load rule
- One student has a completed prerequisite course on record; the other
  does not, so the verification engine's prerequisite check is
  exercised both ways out of the box

**Development credentials** (development only -- change before any
production use):

| Role | Email | Password |
|---|---|---|
| Administrator | admin@crvs.local | ChangeMe123! |
| Academic Officer | officer@crvs.local | ChangeMe123! |
| Student | student1@crvs.local | ChangeMe123! |
| Student | student2@crvs.local | ChangeMe123! |

## Running the Application

```bash
streamlit run app.py
```

## Testing

Each test module opens its own throwaway SQLite database. Because the
SQLAlchemy engine is a module-level singleton (correct for a single
running Streamlit process), running multiple test modules that each
need a different database is done via subprocesses:

```bash
python3 tests/run_all.py
```

Or run an individual module directly:

```bash
python -m unittest tests.test_foundation -v
python -m unittest tests.test_auth_and_structure -v
python -m unittest tests.test_registration_and_verification -v
```

35 tests cover: configuration and imports; password hashing and login
(valid/invalid/inactive); academic structure constraints; course
uniqueness; registration workflow (duplicate prevention, empty
submission, post-submit immutability); the verification engine (missing
compulsory courses, unmet prerequisites, a full pass with zero issues,
duplicate-course database constraint, reverification history
preservation); and the approval workflow (blocked with unresolved
errors, succeeds when passed).

## Deployment

`.streamlit/config.toml` sets a professional institutional theme and
`showErrorDetails = false` so raw tracebacks are never shown to end
users. SQLite remains the default; the SQLAlchemy architecture is
migration-ready for PostgreSQL by changing `CRVS_DATABASE_URL` alone.

## Security Notes

- Passwords are hashed with bcrypt; nothing plain-text is stored,
  logged, or returned to the UI.
- Every sensitive page is protected by `require_role` at the page level,
  and the underlying service functions (registration, verification,
  approval) are independent of the UI and re-checked in their own right
  -- navigation visibility is a convenience, not the security boundary.
- Approval is impossible while unresolved verification errors exist,
  enforced in `approval_service`, not just hidden in the UI.
- Audit events are recorded for login/logout, user/student/course/
  structure changes, registration lifecycle, verification runs, and
  approval decisions -- passwords and secrets are never included.
- `showErrorDetails` is disabled; technical details go to
  `logs/crvs.log` instead of the browser.

## Known Limitations

- `CompletedCourse` is a minimal record used only to support honest
  prerequisite verification; it is not a full academic transcript
  system.
- Notifications and audit logs are viewed in-app only; no email/SMS
  delivery is implemented.
- PDF report export is not implemented (CSV is); the reporting service
  is structured so PDF can be added without touching the report data
  logic.

## Future Improvements

- Academic transcript / GPA module.
- Email/SMS notification delivery.
- PDF report generation.
- PostgreSQL deployment guide and connection pooling configuration.
