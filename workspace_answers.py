import streamlit as st

from workspace_ui import LABELS, flash, get, render_page, request
from streamlit_components import citation_chips


SESSION_LIMIT = 5
SETUP_MESSAGE = "Live AI needs an owner-configured OPENAI_API_KEY in App settings → Secrets. The free PDF example on Overview is available now."


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
        st.caption(f'AI-generated · {answer["provider"]} · {answer["model"]}')
        st.text(answer["body"])
        citation_chips(question["citations"], answer["id"], namespace, render_page)
    elif answer["error_code"] == "missing_credentials":
        st.info(SETUP_MESSAGE)
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
            submit_question(question["question_text"], question["course_id"], question["document_id"], retry=True)
            st.rerun()
    if question["status"] == "answered" and answer["verification_passed"]:
        if answer["rating"]:
            st.caption("Your feedback: " + answer["rating"].replace("_", " ").capitalize())
        left, right = st.columns(2)
        for column, rating, label in ((left, "helpful", "Helpful"), (right, "not_helpful", "Not helpful")):
            if column.button(label, key=f"{namespace}_{answer['id']}_{rating}", disabled=answer["rating"] == rating):
                request(f"/answers/{answer['id']}/feedback", "POST", json={"rating": rating})
                flash("Feedback saved.")


def submit_question(text, course_id, doc_id, *, retry=False):
    signature = (st.session_state.conversation_id, text.strip(), course_id, doc_id)
    if not retry and st.session_state.get("last_question") == signature:
        st.info("This question is already in the conversation.")
        return
    if get("/system/status")["provider"]["configured"]:
        used = st.session_state.get("live_submissions", 0)
        if used >= SESSION_LIMIT:
            st.warning("This session has reached its five live submissions. Your sources and previous answers remain available.")
            return
        st.session_state.live_submissions = used + 1

    with st.spinner("Searching course material and checking the answer…"):
        result = request("/questions", "POST", json={
            "question": text, "course_id": course_id, "document_id": doc_id,
            "conversation_id": st.session_state.conversation_id,
        }).json()
    st.session_state.last_question = signature
    if (result.get("answer") or {}).get("error_code") == "missing_credentials":
        st.info(SETUP_MESSAGE)
        st.stop()
