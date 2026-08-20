"""
Internal notification service.

Notifications are database-backed and plain professional text -- no
emojis. Students and staff each have their own visibility into their own
notifications only.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import Notification, Staff, Student
from utils.logging_config import get_logger

logger = get_logger("services.notification_service")


def notify_student(session: Session, student_id: int, notification_type: str, message: str) -> None:
    student = session.get(Student, student_id)
    if student is None:
        return
    session.add(Notification(user_id=student.user_id, notification_type=notification_type, message=message))


def notify_department_staff(session: Session, department_id: int, notification_type: str, message: str) -> None:
    staff_members = session.query(Staff).filter(Staff.department_id == department_id, Staff.is_active.is_(True)).all()
    for staff in staff_members:
        session.add(Notification(user_id=staff.user_id, notification_type=notification_type, message=message))


def get_notifications_for_user(session: Session, user_id: int, unread_only: bool = False) -> list[Notification]:
    query = session.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).all()


def mark_as_read(session: Session, notification_id: int, user_id: int) -> None:
    notification = session.get(Notification, notification_id)
    if notification is not None and notification.user_id == user_id:
        notification.is_read = True
