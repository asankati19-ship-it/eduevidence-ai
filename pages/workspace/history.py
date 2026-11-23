import streamlit as st

from workspace_ui import LABELS, PAGE_SIZE, get, page_number
from workspace_answers import show_answer


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


history()
