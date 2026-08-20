"""
Application-level error handling.

Wraps page rendering so that unexpected exceptions never surface a raw
Python traceback to end users. Technical details are logged for
developers; users see a professional, plain-text message.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

import streamlit as st

from utils.logging_config import get_logger

logger = get_logger("error_handling")


def safe_page(page_render_fn: Callable) -> Callable:
    """Decorator that converts unhandled exceptions into a professional message."""

    @wraps(page_render_fn)
    def wrapper(*args, **kwargs):
        try:
            return page_render_fn(*args, **kwargs)
        except Exception:
            logger.exception("Unhandled error while rendering page '%s'.", page_render_fn.__name__)
            st.markdown(
                '<div class="crvs-alert crvs-alert-error">'
                "An unexpected error occurred while loading this page. "
                "The technical details have been logged. Please try again "
                "or contact your system administrator if the problem persists."
                "</div>",
                unsafe_allow_html=True,
            )
            return None

    return wrapper
