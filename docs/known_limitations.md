# Known limitations

- The application is a loopback-only sandbox for a single synthetic learner. The UI has no production authentication, authorization, tenant isolation, or live LMS access. Run one backend worker.
- Indexing requires extractable text. Image-only documents are reported with a clear error. Mixed PDFs can index their text pages, and the library shows the text-page count. OCR and semantic table interpretation are outside the scope.
- TF-IDF ranks by term overlap. New vocabulary, short questions, and low-frequency phrasing can lower recall. Similarity scores cannot be interpreted as answer confidence.
- The assistant uses question text, current scope and retrieved passages for each generation. Conversations retain turns for review. Questions that rely on pronouns or facts from a previous turn should be restated.
- Local evidence checks validate retrieved identity, page lineage, exact quotations, scope and selected numeric and logical qualifications. A second structured provider response checks material claims before a new answer is accepted. Both methods can reject legitimate paraphrases or miss subtle contradictions and unsupported inferences. The same model can repeat its own error. Conflict detection depends on retrieving the applicable sources.
- The benchmark covers three synthetic, searchable PDFs and one OpenAI model snapshot. Its results do not measure performance on a larger library, scanned documents, obfuscated document instructions, or another model.
- Upload and index work run in the local process. Interrupted work is recorded on restart. A valid upload may consume memory proportional to its PDF and extracted text, and each question fits a scoped index. This design targets modest local corpora.
- Retired PDFs, old revisions, and historical traces consume local disk. Keep the SQLite file and upload folder together to preserve page previews.
- Real answering depends on the configured OpenAI project's access, quota and connectivity. Generation sends the learner question and ranked source text with citation metadata. Verification sends the question, candidate answer and validated quotations. Verifiable answers therefore incur additional provider latency and token use. The evidence dialog displays the original page and supporting excerpt.

