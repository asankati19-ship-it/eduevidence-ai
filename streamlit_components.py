"""Presentation components for one EduEvidence browser session."""

import csv
from html import escape
from io import StringIO
from pathlib import Path

import streamlit as st


def apply_workspace_styles():
    css = Path(__file__).with_name("workspace.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


NAV_ICONS = {
    "Overview": "space_dashboard", "Document Library": "library_books",
    "Knowledge Assistant": "forum", "Question History": "history",
    "Feedback & Analytics": "bar_chart", "Audit Logs": "list_alt",
    "System Health": "monitor_heart",
}


PAGE_FILES = {
    "Overview": "pages/workspace/overview.py", "Document Library": "pages/workspace/library.py",
    "Knowledge Assistant": "pages/workspace/assistant.py", "Question History": "pages/workspace/history.py",
    "Feedback & Analytics": "pages/workspace/analytics.py", "Audit Logs": "pages/workspace/audit.py",
    "System Health": "pages/workspace/health.py",
}


def download_rows(rows, filename):
    if not rows:
        return
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0])
    writer.writeheader()
    for row in rows:
        fields = {}
        for key, value in row.items():
            if isinstance(value, list):
                value = ", ".join(map(str, value))
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            fields[key] = value
        writer.writerow(fields)
    st.download_button("Download CSV", output.getvalue(), file_name=filename, mime="text/csv",
                       key=f"export_{filename}", on_click="ignore")


def getting_started(indexed, questions):
    destination = "Knowledge Assistant" if indexed else "Document Library"
    with st.container(key="start_card"):
        copy, illustration = st.columns([3, 2], vertical_alignment="center")
        with copy:
            st.subheader("Ask your course library." if indexed else "Start your course library.")
            st.markdown("**How to use**\n1. Choose a sample PDF or upload yours.\n2. Ask the Knowledge Assistant a question.\n3. Open the citation to check the page.")
            label = "Continue in Knowledge Assistant" if indexed and questions else f"Open {destination}"
            st.button(label, icon=":material/arrow_forward:", type="primary",
                      on_click=_navigate, args=(destination,), width="stretch")
            st.button("Try a free PDF example", key="run_example", width="stretch",
                      on_click=lambda: st.session_state.update(show_example=True))
        with illustration:
            st.html('<div class="ee-illustration" aria-hidden="true"><div class="ee-paper">'
                    '<i></i><i></i><i></i><i></i></div><div class="ee-lens"></div></div>')


def course_shelf(documents):
    if not documents:
        st.info("Your bookshelf is empty. Upload a searchable PDF in Document Library.")
        return
    st.subheader("On your bookshelf")
    cols = st.columns(len(documents))
    for i, (column, doc) in enumerate(zip(cols, documents)):
        with column, st.container(key=f"shelf_card_{i}", border=True, height="stretch"):
            st.html(f'<div class="ee-course"><span>{escape(doc["course_code"])}</span>'
                    f'<h3>{escape(doc["title"])}</h3></div>')
            st.caption(f'{doc["page_count"]} pages · {doc["chunk_count"]} indexed passages')
            st.button("Ask", icon=":material/chat_bubble_outline:", help=f'Ask about {doc["title"]}',
                      key=f'shelf_ask_{doc["id"]}', width="stretch", on_click=_open_document,
                      args=(doc["course_id"], doc["id"]))


def _open_document(course_id, document_id):
    st.session_state.ask_course = course_id
    st.session_state.ask_doc = document_id
    _navigate("Knowledge Assistant")


def _navigate(destination):
    st.session_state.next_page = destination


def stats(result):
    metrics = (("Indexed documents", result["documents"]["indexed"]),
               ("Questions asked", result["questions"]["total"]),
               ("Verified answers", result["questions"]["verified"]),
               ("Helpful ratings", result["feedback"]["helpful"]))
    cells = "".join(f"<div><dt>{label}</dt><dd>{int(value):,}</dd></div>"
                    for label, value in metrics)
    st.html(f'<dl class="ee-stats">{cells}</dl>')
    latest = next(iter(result["activity"]), {})
    st.caption(f'Source: this session’s SQLite records · Last activity: {latest.get("created_at", "none yet")} (UTC)')
    download_rows([dict(metrics)], "workspace-activity.csv")


def document_table(documents):
    rows = [{
        "Filename": d["original_filename"], "Title": d["title"], "Course": d["course_code"],
        "Chunks": d["chunk_count"], "Pages": d["page_count"], "Size (bytes)": d["size_bytes"],
        "Uploaded (UTC)": d["created_at"], "Updated (UTC)": d["updated_at"], "Status": d["status"].capitalize(),
    } for d in documents]
    st.dataframe(rows, hide_index=True)
    download_rows(rows, "documents.csv")


def citation_chips(citations, answer_id, namespace, render_page):
    if not citations:
        return
    sources = {c["chunk_id"]: c for c in citations}

    def label(chunk_id):
        c = sources[chunk_id]
        return f"{c['original_filename']} · p. {c['page_number']} · chunk {c['chunk_number']}"

    chunk_id = st.pills("Sources", list(sources), format_func=label,
                        key=f"{namespace}_sources_{answer_id}")
    if chunk_id is None:
        return
    c = sources[chunk_id]
    with st.container(border=True):
        st.text(c["document_title"])
        st.caption(f"Page {c['page_number']} · Chunk ID {chunk_id} · Revision {c['revision']}")
        st.text(c["evidence_quote"])
        with st.expander("Full indexed chunk"):
            st.text(c["content"])
        if st.checkbox("Show original PDF page", key=f"{namespace}_page_{answer_id}_{chunk_id}"):
            render_page(c["document_id"], c["page_number"], key=f"{namespace}_{answer_id}_{chunk_id}")


def audit_table(events, get_record):
    if not events:
        st.info("No matching audit events.")
        return
    colors = {
        "indexed": "green", "answered": "green", "supported": "green", "processing": "orange",
        "accepted": "blue", "error": "red", "rejected": "red", "failed": "red",
        "validation_error": "red", "provider_error": "red", "processing_error": "red",
        "insufficient": "orange", "abstained": "orange",
    }
    rows = []
    palette = {}
    # A running Cloud session can retain the previous API response shape during rollout.
    records = {}
    def lookup(path):
        if path not in records:
            records[path] = get_record(path)
        return records[path]

    for e in events:
        question = {}
        if "question_text" not in e and e["question_id"]:
            question = lookup(f"/questions/{e['question_id']}")
        filename = e.get("document_filename")
        doc_id = e["document_id"] or question.get("document_id")
        if "document_filename" not in e and doc_id:
            filename = lookup(f"/documents/{doc_id}")["original_filename"]
        outcome = e["outcome"]
        status = outcome.replace("_", " ").capitalize()
        if e["event_type"] in {"document.upload", "document.reindex"} and outcome == "accepted":
            status = "Processing (accepted)"
            outcome = "processing"
        palette[status] = colors.get(outcome, "gray")
        rows.append({
            "Time (UTC)": e["created_at"], "Action": e["event_type"].replace(".", " ").capitalize(),
            "Request": e.get("question_text") or question.get("question_text") or filename or e["event_type"].replace(".", " "),
            "Status": [status], "Document": filename, "Detail": e["detail"],
            "Request ID": e["request_id"], "Document ID": e["document_id"], "Question ID": e["question_id"],
        })
    st.dataframe(rows, hide_index=True, column_config={
        "Status": st.column_config.MultiselectColumn(options=list(palette), color=list(palette.values())),
    })
    download_rows(rows, "audit.csv")
