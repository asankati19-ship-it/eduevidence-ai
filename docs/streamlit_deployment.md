# Streamlit deployment

The Streamlit entrypoint uses the same FastAPI routes, PDF parser, retrieval, OpenAI provider, citation validation, and SQLite schema as the local React workspace. Each Streamlit browser session starts with its own copy of the three synthetic PDFs. Uploads, conversation history, and feedback belong to that session. Community Cloud storage should be treated as temporary. [Streamlit storage behavior](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data)

## Run locally

Use Python 3.12 and a dedicated virtual environment. Streamlit's Pillow constraint differs from the existing local backend lock.

```powershell
py -3.12 -m venv .venv-streamlit
.\.venv-streamlit\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-streamlit\Scripts\python.exe -m streamlit run streamlit_app.py
```

The backend reads `OPENAI_API_KEY` from the process environment or the ignored local `.env`. With a blank key the app still supports document browsing, retrieval, and pre-provider abstention. A supported question records a missing-credentials outcome.

## Deploy on Streamlit Community Cloud

1. Connect your GitHub account and select a repository you administer.
2. Set the branch to `main` and the entrypoint to `streamlit_app.py`.
3. Select Python 3.12 in **Advanced settings**. Community Cloud installs the root `requirements.txt`.
4. Set your deployment key as the top-level secret `OPENAI_API_KEY`. Store it in Streamlit's secrets settings. The repository ignores the local secrets file.
5. Deploy. Verify that Overview reports three indexed PDFs. In Knowledge Assistant, select the Python Programming Course Handbook and ask “What are the Python Programming course completion requirements?” Confirm the answer contains four graded labs, at least 70% overall, and a capstone Pass. Open the page 4 citation and verify the quoted evidence and PDF page.

[Deploy on Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [Configure Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
