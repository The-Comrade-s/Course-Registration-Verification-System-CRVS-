"""
Theme loading and light/dark mode mechanism.

Rather than relying on toggling a DOM attribute (unreliable inside
Streamlit's rendering context), the selected theme's CSS variable values
are generated in Python and injected directly as a :root block, ahead of
the shared stylesheet which only ever references var(--crvs-*).
"""

from __future__ import annotations

import os

import streamlit as st

from auth.session import get_theme, set_theme

_STYLES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "styles.css")

_THEME_VARIABLES = {
    "light": {
        "--crvs-bg": "#f5f6f8",
        "--crvs-surface": "#ffffff",
        "--crvs-border": "#dde1e6",
        "--crvs-text-primary": "#1a1f2b",
        "--crvs-text-secondary": "#4d5566",
        "--crvs-primary": "#1f3a63",
        "--crvs-primary-hover": "#16294a",
        "--crvs-accent": "#2c5282",
        "--crvs-success-bg": "#eaf6ee",
        "--crvs-success-text": "#1e6b34",
        "--crvs-warning-bg": "#fdf3e3",
        "--crvs-warning-text": "#8a5a00",
        "--crvs-error-bg": "#fbeaea",
        "--crvs-error-text": "#9b2226",
        "--crvs-neutral-bg": "#eef0f3",
        "--crvs-neutral-text": "#4d5566",
    },
    "dark": {
        "--crvs-bg": "#0d1117",
        "--crvs-surface": "#151b23",
        "--crvs-border": "#2a323d",
        "--crvs-text-primary": "#eef1f5",
        "--crvs-text-secondary": "#a7b0bd",
        "--crvs-primary": "#3f6ea5",
        "--crvs-primary-hover": "#578bc9",
        "--crvs-accent": "#6f9bd1",
        "--crvs-success-bg": "#123521",
        "--crvs-success-text": "#6fd394",
        "--crvs-warning-bg": "#3a2c0f",
        "--crvs-warning-text": "#e3b04b",
        "--crvs-error-bg": "#3a1516",
        "--crvs-error-text": "#ef8a8c",
        "--crvs-neutral-bg": "#1b222c",
        "--crvs-neutral-text": "#a7b0bd",
    },
}


def _load_css() -> str:
    with open(_STYLES_PATH, "r", encoding="utf-8") as css_file:
        return css_file.read()


def _variables_block(theme: str) -> str:
    variables = _THEME_VARIABLES.get(theme, _THEME_VARIABLES["light"])
    declarations = "\n".join(f"    {name}: {value};" for name, value in variables.items())
    return f":root {{\n{declarations}\n}}"


def apply_theme() -> None:
    """Inject the current theme's variables and the shared stylesheet."""
    theme = get_theme()
    css = f"{_variables_block(theme)}\n\n{_load_css()}"
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def theme_toggle_control() -> None:
    """Render the sidebar theme control. Selection persists for the session."""
    current = get_theme()
    label = "Switch to dark mode" if current == "light" else "Switch to light mode"
    if st.sidebar.button(label, use_container_width=True):
        set_theme("dark" if current == "light" else "light")
        st.rerun()
