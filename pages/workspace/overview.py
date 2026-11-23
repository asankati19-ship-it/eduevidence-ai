from pathlib import Path

import streamlit as st

from workspace_ui import get
from streamlit_components import audit_table, course_shelf, getting_started, stats


SAMPLE_FILE = Path(__file__).resolve().parents[2] / "data/sample_documents/Python Programming Course Handbook.pdf"


@st.cache_data(ttl=3600, max_entries=1, show_spinner=False)
def sample_page(file_version):
    # Only the bundled public PDF can enter this cache. Never pass an upload here.
    from backend.app.services.pdf import PDF_WORKER, extract_pages, render_page

    data = SAMPLE_FILE.read_bytes()
    pages = dict(PDF_WORKER.submit(extract_pages, data).result())
    text = pages[4].strip()
    if not text:
        raise ValueError("Empty sample page")
    return text, PDF_WORKER.submit(render_page, data, 4).result()


def overview():
    result = get("/analytics/overview")
    getting_started(result["documents"]["indexed"], result["questions"]["total"])
    if st.session_state.get("show_example"):
        st.subheader("What are the Python Programming completion requirements?")
        st.caption("Source preview · Bundled synthetic Python Programming Course Handbook, page 4 · No AI call")
        try:
            with st.spinner("Reading the sample PDF…"):
                text, image = sample_page(SAMPLE_FILE.stat().st_mtime_ns)
            st.text(text)
            with st.expander("See the original page"):
                st.image(image, caption="Python Programming Course Handbook · Page 4")
                st.download_button("Download page 4", image, "python-handbook-page-4.png", "image/png", on_click="ignore")
        except (OSError, RuntimeError, ValueError, KeyError):
            st.warning("The sample page is unavailable. Choose another PDF from the bookshelf.")
    course_shelf(get("/documents", status="indexed", limit=3)["items"])
    st.subheader("Workspace activity")
    stats(result)
    with st.expander("Recent audit events"):
        audit_table(result["activity"], get)


overview()
