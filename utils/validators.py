"""General-purpose input validation helpers used throughout the application."""

from __future__ import annotations

import re

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    """Return True if the value looks like a well-formed email address."""
    if not value:
        return False
    return bool(_EMAIL_PATTERN.match(value.strip()))


def is_non_empty(value: str | None) -> bool:
    """Return True if value is a non-empty, non-whitespace-only string."""
    return bool(value and value.strip())


def is_positive_number(value) -> bool:
    """Return True if value can be interpreted as a positive number."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False
