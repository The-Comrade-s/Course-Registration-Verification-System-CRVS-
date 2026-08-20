"""
Reusable Streamlit UI components.

Every page in the application should build its interface from these
functions rather than writing bespoke markup, so the look and feel stays
consistent as the system grows across CRVS-002 through CRVS-005. No
emojis are used anywhere in this module.
"""

from __future__ import annotations

from typing import Iterable

import streamlit as st

from config import settings


def page_header(title: str, subtitle: str | None = None) -> None:
    """Render a consistent page header."""
    st.markdown(f'<div class="crvs-page-header"><h1>{title}</h1></div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="crvs-page-subtitle">{subtitle}</p>', unsafe_allow_html=True)


def section_header(title: str) -> None:
    """Render a consistent section header within a page."""
    st.markdown(f'<div class="crvs-section-header">{title}</div>', unsafe_allow_html=True)


def metric_card(label: str, value: str, footnote: str | None = None) -> None:
    """Render a single metric card. Use inside st.columns for a metric row."""
    footnote_html = f'<div class="crvs-metric-footnote">{footnote}</div>' if footnote else ""
    st.markdown(
        f"""
        <div class="crvs-metric-card">
            <div class="crvs-metric-label">{label}</div>
            <div class="crvs-metric-value">{value}</div>
            {footnote_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_row(metrics: Iterable[tuple[str, str]]) -> None:
    """Render a row of metric cards from (label, value) pairs."""
    metrics = list(metrics)
    columns = st.columns(len(metrics)) if metrics else []
    for column, (label, value) in zip(columns, metrics):
        with column:
            metric_card(label, value)


def info_card(title: str, body: str) -> None:
    """Render a general-purpose information card."""
    st.markdown(
        f"""
        <div class="crvs-info-card">
            <div class="crvs-info-card-title">{title}</div>
            <div class="crvs-info-card-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(label: str, status: str = "neutral") -> str:
    """
    Return HTML for a status badge. status is one of:
    'success', 'warning', 'error', 'neutral'.
    """
    return f'<span class="crvs-badge crvs-badge-{status}">{label}</span>'


def empty_state(message: str) -> None:
    """Render a consistent, professional empty state (no fabricated data)."""
    st.markdown(f'<div class="crvs-empty-state">{message}</div>', unsafe_allow_html=True)


def success_message(message: str) -> None:
    st.markdown(f'<div class="crvs-alert crvs-alert-success">{message}</div>', unsafe_allow_html=True)


def warning_message(message: str) -> None:
    st.markdown(f'<div class="crvs-alert crvs-alert-warning">{message}</div>', unsafe_allow_html=True)


def error_message(message: str) -> None:
    st.markdown(f'<div class="crvs-alert crvs-alert-error">{message}</div>', unsafe_allow_html=True)


def form_container_start(title: str | None = None) -> None:
    """Open a consistently styled form container. Pair with a matching close in the page."""
    if title:
        section_header(title)


def render_footer_identity() -> None:
    """Render the small institutional identity line used in the sidebar."""
    st.sidebar.markdown(
        f'<div class="crvs-sidebar-identity">{settings.app.app_name} '
        f'&middot; v{settings.app.app_version}</div>',
        unsafe_allow_html=True,
    )


def data_table(rows) -> None:
    """
    Render tabular data as theme-aware HTML.

    st.dataframe renders through a canvas-based grid that follows
    Streamlit's own built-in theme rather than the CSS variables this
    application injects, so its text stays dark regardless of the
    light/dark toggle here. This renders a plain HTML table styled from
    the same var(--crvs-*) variables as everything else, so it always
    matches the selected theme.

    Accepts either a list of dicts (as used throughout the pages) or a
    pandas DataFrame (as returned by the report service).
    """
    try:
        import pandas as pd

        if isinstance(rows, pd.DataFrame):
            if rows.empty:
                return
            records = rows.to_dict("records")
            columns = list(rows.columns)
        else:
            records = list(rows)
            columns = list(records[0].keys()) if records else []
    except ImportError:
        records = list(rows)
        columns = list(records[0].keys()) if records else []

    if not records:
        return

    header_html = "".join(f"<th>{col}</th>" for col in columns)
    body_html = ""
    for record in records:
        cells = "".join(f"<td>{'' if record.get(col) is None else record.get(col)}</td>" for col in columns)
        body_html += f"<tr>{cells}</tr>"

    st.markdown(
        f"""
        <div class="crvs-table-wrapper">
            <table class="crvs-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{body_html}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
