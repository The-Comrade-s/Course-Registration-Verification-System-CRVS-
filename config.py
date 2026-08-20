"""
Centralized configuration for the Course Registration Verification System (CRVS).

All configurable values are read from environment variables (or Streamlit
secrets, when available) with safe development defaults. No sensitive
configuration is hard-coded here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_setting(key: str, default: str | None = None) -> str | None:
    """
    Resolve a configuration value.

    Lookup order:
        1. Streamlit secrets (if a secrets.toml is present and Streamlit is
           running in a context where st.secrets is available).
        2. Environment variable.
        3. Provided default.
    """
    try:
        import streamlit as st  # imported lazily to avoid a hard dependency at import time

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        # st.secrets raises when no secrets.toml exists, or the module is
        # imported outside of a running Streamlit app (e.g. in tests).
        pass

    return os.environ.get(key, default)


@dataclass(frozen=True)
class AppConfig:
    """Application identity and general settings."""

    app_name: str = field(default_factory=lambda: _get_setting("CRVS_APP_NAME", "Course Registration Verification System"))
    app_abbreviation: str = field(default_factory=lambda: _get_setting("CRVS_APP_ABBREVIATION", "CRVS"))
    app_version: str = field(default_factory=lambda: _get_setting("CRVS_APP_VERSION", "0.1.0"))
    environment: str = field(default_factory=lambda: _get_setting("CRVS_ENVIRONMENT", "development"))


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connectivity settings."""

    database_url: str = field(
        default_factory=lambda: _get_setting(
            "CRVS_DATABASE_URL",
            "sqlite:///" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "crvs.db"),
        )
    )
    echo_sql: bool = field(default_factory=lambda: _get_setting("CRVS_DB_ECHO", "false").lower() == "true")


@dataclass(frozen=True)
class SessionConfig:
    """Session and authentication-related settings."""

    session_timeout_minutes: int = field(default_factory=lambda: int(_get_setting("CRVS_SESSION_TIMEOUT_MINUTES", "60")))
    min_password_length: int = field(default_factory=lambda: int(_get_setting("CRVS_MIN_PASSWORD_LENGTH", "8")))


@dataclass(frozen=True)
class SecurityConfig:
    """Security-related settings."""

    max_login_attempts: int = field(default_factory=lambda: int(_get_setting("CRVS_MAX_LOGIN_ATTEMPTS", "5")))


@dataclass(frozen=True)
class UIConfig:
    """UI presentation settings."""

    default_theme: str = field(default_factory=lambda: _get_setting("CRVS_DEFAULT_THEME", "light"))
    page_layout: str = field(default_factory=lambda: _get_setting("CRVS_PAGE_LAYOUT", "wide"))


@dataclass(frozen=True)
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ui: UIConfig = field(default_factory=UIConfig)


settings = Settings()
