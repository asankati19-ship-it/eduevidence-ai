import streamlit as st

from workspace_ui import PAGE_SIZE, get, page_number
from streamlit_components import audit_table


def audit():
    request_id = st.text_input("Filter by request ID", max_chars=36)
    offset = (page_number("audit_offset") - 1) * PAGE_SIZE
    result = get("/audit/events", request_id=request_id, limit=PAGE_SIZE, offset=offset)
    st.caption(f"{result['total']} matching events")
    audit_table(result["items"], get)


audit()
