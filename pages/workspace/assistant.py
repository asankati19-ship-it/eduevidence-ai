import streamlit as st

import uuid
from workspace_ui import PAGE_SIZE, QUESTION_LIMIT, course_select, document_select, get
from workspace_answers import SESSION_LIMIT, show_answer, submit_question


def assistant():
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    st.caption("Choose the sources to search. Open a citation under a verified answer to inspect its evidence.")
    st.caption(f"Live AI uses up to two OpenAI requests per submission. Session limit: {st.session_state.get('live_submissions', 0)} of {SESSION_LIMIT} submissions used.")
    scope = st.columns(2)
    with scope[0]:
        course_id = course_select(get("/courses"), key="ask_course", all_courses=True)
    with scope[1]:
        documents = get("/documents", course_id=course_id, status="indexed", limit=100)["items"]
        doc_id = document_select(documents, key="ask_doc", all_documents=True)
    with st.form("ask_question", clear_on_submit=True):
        text = st.text_area("Your question", max_chars=QUESTION_LIMIT,
                            placeholder="What would you like to find in your course material?")
        ask = st.form_submit_button("Ask", icon=":material/arrow_upward:", type="primary", width="stretch")
    if ask:
        if len(text.strip()) < 3 or not any(char.isalnum() for char in text):
            st.warning("Enter a question with at least three characters and a letter or number.")
        else:
            submit_question(text, course_id, doc_id)
    history = get("/questions/history", conversation_id=st.session_state.conversation_id, limit=PAGE_SIZE)
    if not history["total"]:
        st.info("No questions in this conversation yet.")
    if history["total"]:
        heading, action = st.columns([3, 2])
        heading.subheader("Latest questions")
        if action.button("New conversation", icon=":material/add:"):
            st.session_state.conversation_id = str(uuid.uuid4())
            st.rerun()
    if history["total"] > PAGE_SIZE:
        st.caption(f"Latest {PAGE_SIZE} turns. Earlier questions are in Question History.")
    for item in history["items"]:
        with st.chat_message("user"):
            st.text(item["question_text"])
        with st.chat_message("assistant"):
            show_answer(item, namespace="assistant")


assistant()
