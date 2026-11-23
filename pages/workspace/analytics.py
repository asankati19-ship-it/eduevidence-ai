import streamlit as st

from workspace_ui import LABELS, get
from streamlit_components import download_rows, stats


def analytics():
    result = get("/analytics/overview")
    stats(result)
    st.subheader("Question outcomes")
    rows = [{"Outcome": LABELS[key], "Questions": result["questions"][count]} for key, count in (
            ("answered", "answered"), ("abstained", "abstained"), ("provider_error", "provider_errors"),
            ("validation_error", "validation_errors"), ("processing_error", "processing_errors"),
        )]
    st.dataframe(rows, hide_index=True)
    download_rows(rows, "question-outcomes.csv")
    st.subheader("Feedback")
    st.caption(f"{result['feedback']['helpful']} helpful · {result['feedback']['not_helpful']} not helpful")


analytics()
