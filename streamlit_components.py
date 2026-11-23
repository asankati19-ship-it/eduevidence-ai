"""Presentation components for one EduEvidence browser session."""

import streamlit as st


def getting_started(indexed, questions):
    if questions:
        return
    destination = "Knowledge Assistant" if indexed else "Document Library"
    with st.container(key="start_card"):
        st.subheader("Ask your first question" if indexed else "Add your first course PDF")
        st.write("Choose a course PDF, ask about its contents, and follow the citation to the original page."
                 if indexed else "Upload a searchable PDF to make its pages available in the Knowledge Assistant.")
        st.button(f"Open {destination}", type="primary", on_click=_navigate, args=(destination,))


def _navigate(destination):
    st.session_state.workspace_page = destination


def document_table(documents):
    st.dataframe([{
        "Filename": d["original_filename"], "Title": d["title"], "Course": d["course_code"],
        "Chunks": d["chunk_count"], "Pages": d["page_count"], "Size (bytes)": d["size_bytes"],
        "Uploaded (UTC)": d["created_at"], "Status": d["status"].capitalize(),
    } for d in documents], hide_index=True)


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
            render_page(c["document_id"], c["page_number"])


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
