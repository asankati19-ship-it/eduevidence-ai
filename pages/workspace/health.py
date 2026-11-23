import streamlit as st

from workspace_ui import get


def system_health():
    status = get("/system/status")
    st.metric("SQLite", status["database"]["status"].capitalize())
    st.text(f"Schema version {status['database']['schema_version']}")
    provider = status["provider"]
    st.text(f"Provider: {provider['name']} · Model: {provider['model']}")
    if provider["configured"]:
        st.success("The AI provider is configured.")
    else:
        st.warning("Live answers require an OpenAI key in the app's deployment secrets.")
    st.subheader("Retrieval and upload limits")
    st.json({"retrieval": status["retrieval"], "upload": status["upload"]})


system_health()
