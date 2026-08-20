"""
Password hashing and verification.

Uses bcrypt, an established password-hashing library. No custom
cryptography is implemented. Plain-text passwords are never stored,
logged, or returned to the UI.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password for storage. Never log or persist the plain value."""
    if not plain_password:
        raise ValueError("Password must not be empty.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    if not plain_password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
