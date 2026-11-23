"""Streamlit Community Cloud entry point for EduEvidence AI."""
import sqlite3

import streamlit as st

st.set_page_config(page_title="EduEvidence AI", page_icon="📚", layout="wide", initial_sidebar_state="auto")

from streamlit_components import PAGE_FILES, NAV_ICONS, apply_workspace_styles


def create_workspace():
    from backend.app.core.config import Settings
    from backend.app.streamlit_workspace import Workspace
    from pydantic import SecretStr

    settings = Settings.from_environment()
    try:
        key = st.secrets.get("OPENAI_API_KEY")
    except FileNotFoundError:
        key = None
    if key is not None:
        if not isinstance(key, str):
            raise ValueError("Invalid key configuration")
        settings.openai_api_key = SecretStr(key.strip())
    settings.openai_max_retries = 0
    return Workspace(settings)


apply_workspace_styles()
page = st.navigation([
    st.Page(path, title=name, icon=f":material/{NAV_ICONS[name]}:", default=name == "Overview")
    for name, path in PAGE_FILES.items()
], position="top")
destination = st.session_state.pop("next_page", None)
if destination:
    st.switch_page(PAGE_FILES[destination])

st.title("EduEvidence AI" if page.title == "Overview" else page.title)
if page.title == "Overview":
    st.write("For learners and instructors: ask questions about course PDFs and check each answer against the original page.")
    st.caption("This browser session has its own temporary uploads, questions, and feedback.")
if "workspace" not in st.session_state:
    with st.spinner("Preparing your private workspace and indexing three sample course PDFs…"):
        try:
            st.session_state.workspace = create_workspace()
        except (ImportError, OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            if isinstance(exc, ImportError):
                st.error("A Python dependency could not load. Install it with: python -m pip install -r requirements.txt")
            else:
                st.error("The workspace could not start. The owner can check the deployment configuration and bundled PDFs, then restart the app.")
            st.stop()

notice = st.session_state.pop("notice", None)
if notice:
    kind, message = notice
    getattr(st, kind)(message)
page.run()
