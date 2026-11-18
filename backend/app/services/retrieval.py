import re
import unicodedata

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TOKEN = re.compile(r"(?u)\b[\w]+(?:[.-][\w]+)*\b")
QUESTION_FILLER = {"tell", "give", "please", "information", "explain", "know", "need", "want", "help"}
PARAGRAPH_BREAK = re.compile(r"\n(?:[ \t]*\n)+")
SAMPLE_HEADER = re.compile(r"^\S+ / SYNTHETIC COURSE LIBRARY\s+")
SAMPLE_FOOTER = re.compile(r"\s*EduEvidence AI / Synthetic demonstration material(?: Page \d+ of \d+)?$")
WEIGHT_PHRASE = re.compile(r"\baccounts? for\b")
WEIGHT_TERMS = {"weighted", "weighting", "weight", "weights", "worth", "contribute", "contributes"}


def normalize(text: str) -> str:
    clean = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    clean = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", clean)
    return " ".join(clean.split())


def normalized_terms(text: str) -> list[str]:
    terms = []
    for word in TOKEN.findall(WEIGHT_PHRASE.sub("weight", text.casefold())):
        if word in ENGLISH_STOP_WORDS or word in QUESTION_FILLER:
            continue
        if len(word) > 5 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us")):
            word = word[:-1]
        terms.append("weight" if word in WEIGHT_TERMS else word)
    return terms


def content_terms(text: str) -> set[str]:
    return set(normalized_terms(text))


def page_chunks(text: str, size: int, overlap: int):
    paragraphs = [normalize(block) for block in PARAGRAPH_BREAK.split(text)]
    content = "\n\n".join(block for block in paragraphs if block)
    words = list(re.finditer(r"\S+", content))
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        if end < len(words):
            lower = max(start + (size * 3 // 4), start + overlap + 1)
            for boundary in range(end - 1, lower - 1, -1):
                if words[boundary].group().endswith((".", "!", "?", ";")):
                    end = boundary + 1
                    break
        yield content[words[start].start():words[end - 1].end()]
        if end == len(words):
            break
        start = end - overlap


def build_index(passages: list[str]):
    vectorizer = TfidfVectorizer(
        tokenizer=normalized_terms,
        token_pattern=None,
        lowercase=False,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(passages)
    return vectorizer, matrix


def scoring_text(row):
    text = SAMPLE_FOOTER.sub("", SAMPLE_HEADER.sub("", normalize(row["content"])))
    title = normalize(row["document_title"])
    # Repeated headings identify the document but should not rank each page as equally relevant.
    if text.startswith(title + " "):
        return text[len(title):].strip() or row["content"]
    return text or row["content"]


def rank_passages(question, rows, settings):
    terms = content_terms(question)
    if len(terms) < settings.min_query_terms:
        return [], "Ask a more specific question about the selected course materials."
    if not rows:
        return [], "There are no indexed passages in the selected course or document."
    texts = [scoring_text(row) for row in rows]
    if not any(content_terms(text) for text in texts):
        return [], "The selected documents do not contain enough matching evidence for this question."
    vectorizer, matrix = build_index(texts)
    query = vectorizer.transform([question])
    if query.nnz == 0:
        return [], "The selected documents do not contain enough matching evidence for this question."
    scores = cosine_similarity(query, matrix).ravel()
    ordered = sorted(range(len(rows)), key=lambda index: (-scores[index], rows[index]["chunk_id"]))
    # Retain a lower threshold for secondary passages so that multi-part queries can use several pages.
    floor = min(settings.min_retrieval_score, max(settings.min_retrieval_score / 2, float(scores.max()) / 4))
    eligible = [
        index for index in ordered
        if scores[index] >= floor and len(terms & content_terms(texts[index])) >= settings.min_query_overlap
    ]
    ranked = [
        {**rows[index], "score": round(float(scores[index]), 8), "rank": rank}
        for rank, index in enumerate(eligible[:settings.retrieval_top_k], 1)
    ]
    supported = any(
        scores[index] >= settings.min_retrieval_score for index in eligible[:settings.retrieval_top_k]
    )
    reason = None if supported else "The selected documents do not contain enough matching evidence for this question."
    return ranked, reason

