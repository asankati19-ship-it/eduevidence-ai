from contextlib import closing

from backend.app.core.config import Settings
from backend.app.streamlit_workspace import Workspace
from backend.tests.fixtures import FixtureProvider, PYTHON_QUESTION
from scripts.seed_data import SAMPLE_DOCS


def test_streamlit_workspace_reuses_real_routes_and_isolates_conversation_state():
    with closing(Workspace(Settings(), provider=FixtureProvider())) as first, closing(Workspace(Settings())) as second:
        assert first.request("GET", "/health").json()["database"] == "reachable"
        assert first.request("GET", "/documents").json()["total"] == 3
        assert not second.request("GET", "/system/status").json()["provider"]["configured"]

        known = first.request("POST", "/questions", json={"question": PYTHON_QUESTION, "document_id": 1})
        assert known.status_code == 201
        trace = known.json()
        assert trace["status"] == "answered" and trace["answer"]["verification_passed"]
        citation, = trace["citations"]
        assert citation["page_number"] == 4
        page = first.request("GET", "/documents/1/pages/4")
        assert page.headers["content-type"] == "image/png"
        assert page.content.startswith(b"\x89PNG\r\n\x1a\n")

        answer_id = trace["answer"]["id"]
        feedback = first.request("POST", f"/answers/{answer_id}/feedback", json={"rating": "helpful"})
        feedback.raise_for_status()
        saved = first.request("GET", f"/questions/{trace['id']}").json()
        assert saved["answer"]["rating"] == "helpful"
        assert second.request("GET", "/questions/history").json()["total"] == 0

        unknown = second.request("POST", "/questions", json={"question": "What is the cafeteria menu on Tuesday?"})
        assert unknown.json()["status"] == "abstained" and unknown.json()["citations"] == []


def test_streamlit_upload_and_reindex_preserve_page_identity():
    with closing(Workspace(Settings())) as workspace:
        original = (SAMPLE_DOCS / "Python Programming Course Handbook.pdf").read_bytes()
        upload = workspace.request(
            "POST", "/documents/upload",
            data={"course_id": "1"},
            files={"file": ("synthetic-upload.pdf", original + b"\n% Streamlit upload fixture\n", "application/pdf")},
        )
        assert upload.status_code == 202
        document_id = upload.json()["id"]
        path = f"/documents/{document_id}"
        indexed = workspace.request("GET", path).json()
        assert (indexed["status"], indexed["page_count"], indexed["active_revision"]) == ("indexed", 4, 1)
        assert workspace.request("GET", path + "/pages/4").status_code == 200
        assert workspace.request("POST", path + "/reindex").status_code == 202
        assert workspace.request("GET", path).json()["active_revision"] == 1
        assert workspace.request("DELETE", path).status_code == 204
        assert workspace.request("GET", "/documents").json()["total"] == 3
