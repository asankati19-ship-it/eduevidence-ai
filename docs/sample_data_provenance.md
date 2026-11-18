# Sample data provenance

The repository includes three original synthetic course documents written for this assignment. They represent fictional policies and course structures. Samples contain no copied LMS material and no real learner records. The single local identity is Demo Learner.

| PDF | Course | Pages | Evidence examples |
|---|---|---:|---|
| Python Programming Course Handbook | PY-101 | 4 | Page 3 lab submission and page 4 completion criteria |
| AI and Machine Learning Course Guide | AI-201 | 3 | Page 3 capstone report contents and grading |
| LMS Assessment and Attendance Policy | LMS-001 | 3 | Page 1 late work, page 2 attendance, page 3 reviews |

`scripts/sample_content.py` holds the authored text. `scripts.generate_sample_pdfs` reproducibly typesets it with ReportLab. `data/expected_answers.json` takes page and fact expectations directly from the authored policies. It is independent of ranking output and model responses.

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_sample_pdfs
.\.venv\Scripts\python.exe -m scripts.seed_data --build-sample-db
```

Generated PDFs were opened with PyMuPDF and all ten pages were rendered with Poppler for visual inspection.

