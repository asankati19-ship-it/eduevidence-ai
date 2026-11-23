import streamlit as st

from workspace_ui import LABELS, course_select, document_select, flash, get, render_page, request
from streamlit_components import document_table


def library():
    courses = get("/courses")
    max_mb = get("/system/status")["upload"]["max_mb"]
    with st.expander("Upload a course PDF"):
        with st.form("upload_pdf", clear_on_submit=True):
            course_id = course_select(courses)
            title = st.text_input("Display title", max_chars=180)
            uploaded = st.file_uploader("PDF file", type=["pdf"], max_upload_size=max_mb)
            submit = st.form_submit_button("Upload and index")
        if submit:
            if uploaded is None:
                st.warning("Choose a PDF to upload.")
            elif (not uploaded.name.lower().endswith(".pdf") or uploaded.size > max_mb * 1024 * 1024
                  or b"%PDF-" not in uploaded.getbuffer()[:1024].tobytes()):
                st.warning(f"Choose a valid PDF file up to {max_mb} MB.")
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


library()
