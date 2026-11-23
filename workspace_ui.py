"""Shared UI helpers for the session-local course workspace."""

import httpx
import streamlit as st

QUESTION_LIMIT = 1200
PAGE_SIZE = 20
LABELS = {
    "answered": "Answered",
    "abstained": "Abstained",
    "provider_error": "Provider error",
    "validation_error": "Validation error",
    "processing_error": "Processing error",
    "processing": "Processing",
    "indexed": "Indexed",
    "error": "Indexing error",
}


def request(path, method="GET", **kwargs):
    try:
        result = st.session_state.workspace.request(method, path, **kwargs)
    except httpx.HTTPError:
        st.error("The workspace could not complete the request. Try again.")
        st.stop()
    if not result.is_success:
        try:
            error = result.json().get("error", {})
        except ValueError:
            error = {}
        message = error.get("message", "The workspace could not complete the request.")
        issues = error.get("issues", [])
        st.error(issues[0]["message"] if issues else message)
        if error.get("request_id"):
            st.caption(f"Request ID {error['request_id']}")
        st.stop()
    if method != "GET" and path.startswith("/documents/"):
        st.session_state.pop("last_question", None)
    return result


def get(path, **params):
    return request(path, params={key: value for key, value in params.items() if value not in (None, "")}).json()


def flash(message, kind="success"):
    st.session_state.notice = (kind, message)
    st.rerun()


def course_select(courses, *, label="Course", key=None, all_courses=False):
    names = {course["id"]: f"{course['code']} · {course['title']}" for course in courses}
    if all_courses:
        names = {None: "All courses", **names}
    return st.selectbox(label, list(names), format_func=names.__getitem__, key=key)


def document_select(documents, *, key, all_documents=False):
    names = {doc["id"]: f"{doc['title']} ({doc['original_filename']})" for doc in documents}
    if all_documents:
        names = {None: "All documents", **names}
    return st.selectbox("Document", list(names), format_func=names.__getitem__, key=key)


def render_page(document_id, page_number, *, key="library"):
    image = request(f"/documents/{document_id}/pages/{page_number}").content
    st.download_button("Download PDF page as PNG", image, f"document-{document_id}-page-{page_number}.png",
                       "image/png", key=f"png_{key}_{document_id}_{page_number}", on_click="ignore")
    st.image(image, caption=f"Original PDF · Page {page_number}")


def page_number(key):
    return int(st.number_input("Result page", min_value=1, value=1, step=1, key=key))
