"""Streamlit Community Cloud frontend for the existing EduEvidence API."""

import uuid

import httpx
from pydantic import SecretStr
import streamlit as st

from streamlit_components import audit_table, citation_chips, document_table, getting_started
from backend.app.core.config import Settings
from backend.app.streamlit_workspace import Workspace


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
PAGES = (
    "Overview", "Document Library", "Knowledge Assistant", "Question History",
    "Feedback & Analytics", "Audit Logs", "System Health",
)


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
        st.error("Request failed")
        st.text(issues[0]["message"] if issues else message)
        if error.get("request_id"):
            st.caption(f"Request ID {error['request_id']}")
        st.stop()
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


def render_page(document_id, page_number):
    image = request(f"/documents/{document_id}/pages/{page_number}").content
    st.image(image, caption=f"Original PDF · Page {page_number}")


def stats(result):
    documents, questions, feedback = (result[key] for key in ("documents", "questions", "feedback"))
    for column, label, value in zip(
        st.columns(4),
        ("Indexed documents", "Questions asked", "Verified answers", "Helpful ratings"),
        (documents["indexed"], questions["total"], questions["verified"], feedback["helpful"]),
    ):
        column.metric(label, value, border=True)


def overview():
    result = get("/analytics/overview")
    stats(result)
    getting_started(result["documents"]["indexed"], result["questions"]["total"])
    st.subheader("Recent activity")
    audit_table(result["activity"], get)


def library():
    courses = get("/courses")
    with st.expander("Upload a course PDF"):
        with st.form("upload_pdf", clear_on_submit=True):
            course_id = course_select(courses)
            title = st.text_input("Display title", max_chars=180)
            uploaded = st.file_uploader("PDF file", type=["pdf"])
            submit = st.form_submit_button("Upload and index")
        if submit:
            if uploaded is None:
                st.warning("Choose a PDF to upload.")
            else:
                with st.spinner("Uploading and indexing…"):
                    accepted = request(
                        "/documents/upload", "POST", data={"course_id": course_id, "title": title},
                        files={"file": (uploaded.name, uploaded, "application/pdf")},
                    ).json()
                    doc = get(f"/documents/{accepted['id']}")
                if doc["status"] == "indexed":
                    flash("PDF uploaded and indexed.")
                if doc["status"] == "error":
                    flash(doc["error_message"] or "The uploaded PDF could not be indexed.", "error")
                flash("PDF uploaded. Indexing is in progress.", "info")

    filters = st.columns(2)
    with filters[0]:
        course_id = course_select(courses, key="library_course", all_courses=True)
    with filters[1]:
        search = st.text_input("Search documents", max_chars=150)
    result = get("/documents", course_id=course_id, search=search, limit=100)
    documents = result["items"]
    st.caption(f"{len(documents)} of {result['total']} documents")
    if not documents:
        st.info("No matching documents.")
        return
    document_table(documents)
    doc_id = document_select(documents, key="library_document")
    doc = get(f"/documents/{doc_id}")
    st.text(doc["original_filename"])
    st.caption(
        f"{LABELS.get(doc['status'], doc['status'])} · {doc['page_count']} pages · "
        f"{doc['chunk_count']} chunks · Revision {doc['active_revision']}"
    )
    if doc["error_message"]:
        st.text(doc["error_message"])
    actions = st.columns(2)
    if actions[0].button("Reindex", key=f"reindex_{doc_id}", disabled=doc["status"] == "processing"):
        with st.spinner("Reindexing…"):
            request(f"/documents/{doc_id}/reindex", "POST")
            refreshed = get(f"/documents/{doc_id}")
        if refreshed["status"] == "indexed":
            flash("Reindexing complete.")
        if refreshed["status"] == "error":
            flash(refreshed["error_message"] or "The PDF could not be reindexed.", "error")
        flash("Reindexing is in progress.", "info")
    with actions[1].expander("Retire document"):
        st.write("Retirement removes this PDF from new searches. Existing citations remain available.")
        confirm = st.checkbox("Confirm retirement", key=f"confirm_retire_{doc_id}")
        if st.button("Retire PDF", key=f"retire_{doc_id}", disabled=not confirm or doc["status"] == "processing"):
            request(f"/documents/{doc_id}", "DELETE")
            flash("PDF retired.")
    if doc["page_count"]:
        page = st.number_input("PDF page", min_value=1, max_value=doc["page_count"], key=f"page_{doc_id}")
        if st.checkbox("Preview original PDF page", key=f"library_preview_{doc_id}"):
            render_page(doc_id, page)


def show_answer(question, *, namespace=""):
    answer = question["answer"]
    if not answer:
        st.info("This question is still processing.")
        return
    status = question["status"]
    verified = status == "answered" and answer["verification_passed"]
    label = "Verified answer" if verified else LABELS.get(status, status)
    color = "green" if verified else "red" if status.endswith("_error") else "gray"
    st.badge(label, color=color)
    if verified and answer["body"]:
        st.text(answer["body"])
        citation_chips(question["citations"], answer["id"], namespace, render_page)
    elif answer["reason"]:
        if status.endswith("_error"):
            st.error(answer["reason"])
        else:
            st.info(answer["reason"])
    elif answer["body"]:
        st.info("This earlier answer has no verification record.")
    with st.expander("Answer details"):
        st.json({key: answer[key] for key in (
            "provider", "model", "api_outcome", "provider_response_id", "verification_passed", "error_code"
        )} | {"request_id": question["request_id"], "question_id": question["id"], "answer_id": answer["id"]})
    if namespace == "assistant" and answer["retryable"]:
        if st.button("Retry question", key=f"retry_{question['id']}"):
            submit_question(question["question_text"], question["course_id"], question["document_id"])
            st.rerun()
    if question["status"] == "answered" and answer["verification_passed"]:
        if answer["rating"]:
            st.caption("Your feedback: " + answer["rating"].replace("_", " ").capitalize())
        left, right = st.columns(2)
        for column, rating, label in ((left, "helpful", "Helpful"), (right, "not_helpful", "Not helpful")):
            if column.button(label, key=f"{namespace}_{answer['id']}_{rating}", disabled=answer["rating"] == rating):
                request(f"/answers/{answer['id']}/feedback", "POST", json={"rating": rating})
                flash("Feedback saved.")


def submit_question(text, course_id, doc_id):
    with st.spinner("Searching course material and checking the answer…"):
        request("/questions", "POST", json={
            "question": text, "course_id": course_id, "document_id": doc_id,
            "conversation_id": st.session_state.conversation_id,
        })


def assistant():
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    if st.button("New conversation"):
        st.session_state.conversation_id = str(uuid.uuid4())
        st.rerun()
    scope = st.columns(2)
    with scope[0]:
        course_id = course_select(get("/courses"), key="ask_course", all_courses=True)
    with scope[1]:
        documents = get("/documents", course_id=course_id, status="indexed", limit=100)["items"]
        doc_id = document_select(documents, key="ask_doc", all_documents=True)
    with st.form("ask_question", clear_on_submit=True):
        text = st.text_area("Your question", max_chars=QUESTION_LIMIT)
        ask = st.form_submit_button("Ask", type="primary")
    if ask:
        if len(text.strip()) < 3 or not any(char.isalnum() for char in text):
            st.warning("Enter a question with at least three characters and a letter or number.")
        else:
            submit_question(text, course_id, doc_id)
    history = get("/questions/history", conversation_id=st.session_state.conversation_id, limit=PAGE_SIZE)
    if history["total"] > PAGE_SIZE:
        st.caption(f"Latest {PAGE_SIZE} turns. Earlier questions are in Question History.")
    for item in reversed(history["items"]):
        with st.chat_message("user"):
            st.text(item["question_text"])
        with st.chat_message("assistant"):
            show_answer(item, namespace="assistant")


def page_number(key):
    return int(st.number_input("Result page", min_value=1, value=1, step=1, key=key))


def history():
    query = st.text_input("Search questions", max_chars=150)
    statuses = {"": "All outcomes", **{key: label for key, label in LABELS.items() if key not in {"indexed", "error"}}}
    status = st.selectbox("Outcome", list(statuses), format_func=statuses.__getitem__)
    offset = (page_number("history_offset") - 1) * PAGE_SIZE
    result = get("/questions/history", search=query, status=status, limit=PAGE_SIZE, offset=offset)
    st.caption(f"{result['total']} matching questions")
    if not result["items"]:
        st.info("No questions on this result page.")
        return
    questions = {item["id"]: item["question_text"] for item in result["items"]}
    question_id = st.selectbox("Question", list(questions), format_func=questions.__getitem__)
    show_answer(get(f"/questions/{question_id}"), namespace="history")


def analytics():
    result = get("/analytics/overview")
    stats(result)
    st.subheader("Question outcomes")
    st.dataframe(
        [{"Outcome": LABELS[key], "Questions": result["questions"][count]} for key, count in (
            ("answered", "answered"), ("abstained", "abstained"), ("provider_error", "provider_errors"),
            ("validation_error", "validation_errors"), ("processing_error", "processing_errors"),
        )],
        hide_index=True,
    )
    st.subheader("Feedback")
    st.caption(f"{result['feedback']['helpful']} helpful · {result['feedback']['not_helpful']} not helpful")


def audit():
    request_id = st.text_input("Filter by request ID", max_chars=36)
    offset = (page_number("audit_offset") - 1) * PAGE_SIZE
    result = get("/audit/events", request_id=request_id, limit=PAGE_SIZE, offset=offset)
    st.caption(f"{result['total']} matching events")
    audit_table(result["items"], get)


def system_health():
    status = get("/system/status")
    st.metric("SQLite", status["database"]["status"].capitalize())
    st.text(f"Schema version {status['database']['schema_version']}")
    provider = status["provider"]
    st.text(f"Provider: {provider['name']} · Model: {provider['model']}")
    if provider["configured"]:
        st.success("The AI provider is configured.")
    else:
        st.warning("Live answers require an OpenAI key in the app's deployment secrets.")
    st.subheader("Retrieval and upload limits")
    st.json({"retrieval": status["retrieval"], "upload": status["upload"]})


def create_workspace():
    try:
        key = st.secrets.get("OPENAI_API_KEY")
    except FileNotFoundError:
        key = None
    if isinstance(key, str):
        settings = Settings.from_environment().model_copy(update={"openai_api_key": SecretStr(key)})
        return Workspace(settings)
    return Workspace()


def main():
    st.set_page_config(page_title="EduEvidence AI", page_icon="📚", layout="wide")
    st.sidebar.title("EduEvidence AI")
    st.sidebar.caption("Synthetic course workspace")
    page = st.sidebar.radio("Workspace page", PAGES, key="workspace_page",
                            help="Browse course PDFs, ask questions, or review saved activity.")
    st.sidebar.caption("Uploads and history are temporary and belong to this browser session.")
    st.title(page)
    if "workspace" not in st.session_state:
        with st.spinner("Starting your course workspace…"):
            st.session_state.workspace = create_workspace()
    notice = st.session_state.pop("notice", None)
    if notice:
        kind, message = notice
        if kind == "success":
            st.success(message)
        else:
            st.error("Indexing failed") if kind == "error" else st.info("Indexing in progress")
            st.text(message)
    views = (overview, library, assistant, history, analytics, audit, system_health)
    views[PAGES.index(page)]()


if __name__ == "__main__":
    main()

