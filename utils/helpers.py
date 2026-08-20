"""Small, generally useful helper functions with no other natural home."""

from __future__ import annotations

import datetime


def format_datetime(value: datetime.datetime | None) -> str:
    """Format a datetime for consistent display across the application."""
    if value is None:
        return "-"
    return value.strftime("%d %b %Y, %H:%M")


def format_date(value: datetime.date | None) -> str:
    """Format a date for consistent display across the application."""
    if value is None:
        return "-"
    return value.strftime("%d %b %Y")
