"""Exercise the Streamlit UI against a fresh workspace with a deterministic test provider."""

from contextlib import closing

from streamlit.testing.v1 import AppTest

from backend.app.core.config import ROOT, Settings
from backend.app.streamlit_workspace import Workspace
from backend.tests.fixtures import FixtureProvider, PYTHON_QUESTION, PYTHON_QUOTE


def run():
    with closing(Workspace(Settings(), provider=FixtureProvider())) as workspace:
        app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=45)
        app.session_state["workspace"] = workspace

        def refresh():
            app.run()
            assert not app.exception, [error.message for error in app.exception]

        def navigate(page):
            app.radio(key="workspace_page").set_value(page)
            refresh()

        refresh()
        next(b for b in app.button if b.label == "Open Knowledge Assistant").click()
        refresh()
        assert app.title[0].value == "Knowledge Assistant"
        app.text_area[0].input(PYTHON_QUESTION)
        next(b for b in app.button if b.label == "Ask").click()
        refresh()
        trace = workspace.request("GET", "/questions/history").json()["items"][0]
        assert trace["answer"]["verification_passed"]
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


if __name__ == "__main__":
    run()
