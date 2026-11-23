"""Exercise the Streamlit UI against a fresh workspace with a deterministic test provider."""

from contextlib import closing

from streamlit.testing.v1 import AppTest

from backend.app.core.config import ROOT, Settings
from backend.app.streamlit_workspace import Workspace
from backend.tests.fixtures import FixtureProvider, PYTHON_QUESTION, PYTHON_QUOTE
from streamlit_components import PAGE_FILES


def run():
    provider = FixtureProvider()
    with closing(Workspace(Settings(), provider=provider)) as workspace:
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=45)
        app.session_state["workspace"] = workspace

        def refresh():
            app.run()
            assert not app.exception, [error.message for error in app.exception]

        def navigate(page):
            app.switch_page(PAGE_FILES[page])
            refresh()

        refresh()
        featured = workspace.request("GET", "/documents", params={"status": "indexed", "limit": 3}).json()["items"][0]
        app.button(key=f"shelf_ask_{featured['id']}").click()
        refresh()
        assert app.title[0].value == "Knowledge Assistant"
        assert app.selectbox(key="ask_course").value == featured["course_id"]
        assert app.selectbox(key="ask_doc").value == featured["id"]
        navigate("Overview")
        next(b for b in app.button if b.label == "Open Knowledge Assistant").click()
        refresh()
        assert app.title[0].value == "Knowledge Assistant"
        navigate("Knowledge Assistant")
        app.text_area[0].input(PYTHON_QUESTION)
        next(b for b in app.button if b.label == "Ask").click()
        refresh()
        trace = workspace.request("GET", "/questions/history").json()["items"][0]
        assert trace["answer"]["verification_passed"]
        calls = len(provider.calls)
        assert calls == 1
        app.text_area[0].input(PYTHON_QUESTION)
        next(b for b in app.button if b.label == "Ask").click()
        refresh()
        assert len(provider.calls) == calls
        assert workspace.request("GET", "/questions/history").json()["total"] == 1
        citation, = trace["citations"]
        app.pills[0].set_value(citation["chunk_id"])
        refresh()
        assert PYTHON_QUOTE in [node.value for node in app.text]
        assert citation["content"] in [node.value for node in app.text]
        app.checkbox[0].check()
        refresh()
        assert len(app.get("imgs")) or len(app.get("image"))

        navigate("Overview")
        assert all(b.label != "Open Knowledge Assistant" for b in app.button)
        navigate("Document Library")
        table = app.dataframe[0].value
        assert len(table) == 3 and table["Chunks"].min() > 0 and table["Size (bytes)"].min() > 0
        assert all(table["Uploaded (UTC)"])
        app.selectbox(key="library_document").set_value(citation["document_id"])
        refresh()
        app.button(key=f"reindex_{citation['document_id']}").click()
        refresh()
        assert any(item.value == "Reindexing complete." for item in app.success)
        app.checkbox(key=f"confirm_retire_{citation['document_id']}").check()
        refresh()
        app.button(key=f"retire_{citation['document_id']}").click()
        refresh()
        assert citation["original_filename"] not in app.dataframe[0].value["Filename"].values
        navigate("Question History")
        app.pills[0].set_value(citation["chunk_id"])
        refresh()
        assert citation["content"] in [node.value for node in app.text]
        navigate("Audit Logs")
        events = app.dataframe[0].value
        assert PYTHON_QUESTION in events["Request"].values
        assert citation["original_filename"] in events["Document"].values
        assert "Indexed" in {status[0] for status in events["Status"]}
        print("Overview CTA, verified citation chip, PDF preview, library metadata and audit labels passed.")


def public_visit():
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    app.secrets["OPENAI_API_KEY"] = ""
    app.run()
    assert not app.exception and app.title[0].value == "EduEvidence AI"
    assert any("learners and instructors" in node.value for node in app.markdown)
    app.button(key="run_example").click().run()
    assert not app.exception
    page_text = " ".join(" ".join(node.value.split()) for node in app.text)
    assert all(part in page_text for part in ("four graded labs", "70% overall", "Pass on the capstone"))
    assert any(b.label == "Download page 4" for b in app.get("download_button"))
    for name, path in PAGE_FILES.items():
        app.switch_page(path).run()
        assert not app.exception, name
    app.switch_page(PAGE_FILES["Document Library"]).run()
    app.file_uploader[0].upload("broken.pdf", b"just text", "application/pdf")
    next(b for b in app.button if b.label == "Upload and index").click().run()
    assert not app.exception and any("valid PDF" in w.value for w in app.warning)
    assert len(app.dataframe[0].value) == 3
    app.switch_page(PAGE_FILES["Knowledge Assistant"]).run()
    app.text_area[0].input(PYTHON_QUESTION)
    next(b for b in app.button if b.label == "Ask").click().run()
    assert not app.exception and sum("OPENAI_API_KEY" in msg.value for msg in app.info) == 1
    app.switch_page(PAGE_FILES["Overview"]).run()
    assert not app.exception and app.button(key="run_example")
    app.session_state["workspace"].close()
    print("All seven pages, first visit, free example, bad upload recovery and missing-secret handling passed.")


if __name__ == "__main__":
    run()
    public_visit()
