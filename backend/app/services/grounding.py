import re

from pydantic import ValidationError

from backend.app.core.errors import ProviderError
from backend.app.models.schemas import ModelAnswer, ModelVerification
from backend.app.services.retrieval import PARAGRAPH_BREAK, SAMPLE_HEADER, content_terms, normalize


SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
CLAUSE_BREAK = re.compile(r";\s*|,\s+(?:and|but|whereas|while)\s+", re.I)
DIRECTIVE = re.compile(
    r"\b(?:ignore|disregard|override|forget)\s+"
    r"(?:(?:all|any|the|your|these|previous|prior|earlier|original|system|developer|above)\s+){1,5}"
    r"(?:instructions?|rules?|prompts?)\b",
    re.I,
)
NEGATION = re.compile(r"\b(?:not|never|cannot|prohibited|ineligible)\b|\w+n['’]t\b", re.I)
NUMBER_WORDS = {
    word: str(number) for number, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve".split()
    )
}
QUANTITY_WORDS = NUMBER_WORDS | {"half": "0.5", "quarter": "0.25"}
QUANTITY = re.compile(
    r"\b(?P<value>\d+(?:[.,]\d+)*|" + "|".join(QUANTITY_WORDS) + r")\b"
    r"(?:[\s-]*(?P<unit>%|percentage points?\b|percent\b|working days?\b|days?\b|hours?\b|weeks?\b))?",
    re.I,
)
BOUNDS = {
    "at least": "minimum", "a minimum of": "minimum", "no less than": "minimum",
    "at most": "maximum", "up to": "maximum", "no more than": "maximum", "a maximum of": "maximum",
    "more than": "greater", "less than": "less", "fewer than": "less",
}
COMPARATOR = re.compile(r"\b(" + "|".join(re.escape(word) for word in BOUNDS) + r")\s*$", re.I)
GENERAL_QUESTION_TERMS = {"course", "material", "document", "guide", "handbook", "listed", "list"}
TOPIC_FORMS = {
    "completion": "complete", "completing": "complete",
    "introductory": "foundation", "beginner": "foundation",
    "replay": "recording", "replaying": "recording", "recorded": "recording",
    "resubmissions": "resubmit", "resubmission": "resubmit",
    "weighting": "weight", "worth": "weight", "account": "weight",
    "programming": "program", "practical": "practice",
}
DURATION_QUESTION = re.compile(r"\b(?:how long|how many weeks|duration)\b", re.I)
PARENTHETICAL = re.compile(r"\(([^()]*)\)")
RESTRICTED_ELIGIBILITY = re.compile(
    r"\b(?P<subject>[\w-]+)\s+(?:marked|classified|designated|identified|deemed)\s+(?:as\s+)?eligible\b",
    re.I,
)
ELIGIBILITY = re.compile(r"\b(?:eligib\w*|qualif\w*)\b", re.I)
POLAR_QUESTION = re.compile(
    r"^(?:(?P<condition>(?:if|when)\b[^?]*?),\s*)?"
    r"(?:am|is|are|was|were|do|does|did|can|could|may|must|should|has|have|will|would)\b",
    re.I,
)
REFERENCE = re.compile(r"\bthe same (area|location|slot|category|form|channel|section)\b", re.I)
EVIDENCE_ABSENCE = re.compile(
    r"\b(?:do(?:es)? not|did not|don['’]t|doesn['’]t|didn['’]t)\s+"
    r"(?:mention|specify|state|address|establish|confirm)\b"
    r"|\b(?:not|never)\s+(?:mentioned|specified|stated|established|addressed)\b"
    r"|\bno\s+(?:evidence|mention|information)\s+(?:of|about|on|regarding)\b",
    re.I,
)


def evidence_units(text):
    """Split normalized visual paragraphs into the complete text units available to cite."""
    return [
        unit for block in PARAGRAPH_BREAK.split(text)
        for unit in SENTENCE_BREAK.split(normalize(block)) if unit
    ]


def has_directive(text):
    return bool(DIRECTIVE.search(normalize(text)))


def excerpt_span(chunk, quote):
    units = evidence_units(chunk)
    cursor = 0
    starts = set()
    ends = set()
    for unit in units:
        starts.add(cursor)
        cursor += len(unit)
        ends.add(cursor)
        cursor += 1
    plain = " ".join(units)
    for occurrence in re.finditer(re.escape(quote), plain):
        start, end = occurrence.span()
        if end not in ends:
            continue
        if start in starts:
            return start, end
        # Older synthetic revisions flattened their page headings into the first sentence.
        prefix = plain[:start]
        if (
            "\n" not in chunk and SAMPLE_HEADER.match(prefix) and start < len(units[0])
            and prefix.endswith(" ") and quote[0].isupper() and len(prefix.split()) <= 28
            and not re.search(r"\b(?:if|unless|only|eligible|except|when)\b|[,;]", prefix, re.I)
        ):
            return start, end
    return None


def merge_excerpts(chunk, first, second):
    """Return one continuous excerpt of the original text covering both citations."""
    first_span = excerpt_span(chunk, first)
    second_span = excerpt_span(chunk, second)
    if first_span is None or second_span is None:
        raise ProviderError("incomplete_evidence_quote", "A cited quotation omitted part of the source statement.", True)
    start = min(first_span[0], second_span[0])
    end = max(first_span[1], second_span[1])
    return " ".join(evidence_units(chunk))[start:end]


def with_reference_context(chunk, quote):
    """Attach the explicit antecedent from the same passage to a relative quote."""
    reference = REFERENCE.search(quote)
    if reference is None:
        return quote
    label = reference[1]
    named_location = re.compile(
        r"\b(?:in|via|within|through|using)\s+(?:the\s+)?(?:[\w-]+\s+){1,6}"
        + re.escape(label) + r"\b", re.I,
    )
    if named_location.search(quote[:reference.start()]):
        return quote
    units = evidence_units(chunk)
    plain = " ".join(units)
    offset = 0
    for index, unit in enumerate(units):
        if plain.startswith(quote, offset):
            for previous in range(index - 1, -1, -1):
                if named_location.search(units[previous]):
                    return " ".join([*units[previous:index], quote])
            break
        offset += len(unit) + 1
    raise ProviderError("incomplete_evidence_quote", "A cited reference did not identify the source it referred to.", True)


def answer_cites_absence(parsed):
    """Treat an answer that relies on stated absence of evidence as an abstention."""
    quotes = " ".join(citation.evidence_quote.casefold() for citation in parsed.citations)
    return any(match.group().casefold() not in quotes for match in EVIDENCE_ABSENCE.finditer(parsed.answer or ""))


def topic_terms(text):
    terms = content_terms(text.replace("-", " "))
    return {TOPIC_FORMS.get(term, term) for term in terms if term not in GENERAL_QUESTION_TERMS}


def polar_question_lacks_evidence(question, quotes):
    question = normalize(question)
    match = POLAR_QUESTION.match(question)
    if not match:
        return False
    # Keep any conditional premise and ignore the auxiliary and generic words for policy.
    topic = topic_terms(f"{match['condition'] or ''} {question[match.end():]}") - {"rule", "policy", "requirement"}
    covered = topic & topic_terms(" ".join(quotes))
    # A related passage may share the policy name while saying nothing about the outcome.
    return len(topic - covered) >= 2 and len(covered) * 3 < len(topic) * 2


def insufficient_evidence():
    return ModelAnswer(
        status="abstained", answer=None, citations=[],
        abstention_reason="The retrieved materials do not establish an answer to that question.",
    )


def relevant_to_question(question, quotes, titles):
    # Strip named source context from the question so a title match alone cannot authorize an answer.
    question_terms = topic_terms(question)
    title_terms = set().union(*(topic_terms(title) for title in titles))
    specific = question_terms - title_terms
    provided = topic_terms(" ".join(quotes))
    if DURATION_QUESTION.search(question) and provided.intersection({"day", "hour", "week", "month", "year"}):
        return True
    return not specific or bool(specific & provided)


def quantities(text):
    values = set()
    for match in QUANTITY.finditer(text):
        value = match["value"].casefold()
        unit = (match["unit"] or "").casefold()
        if value in NUMBER_WORDS and not unit:
            continue
        unit = "%" if unit == "percent" else unit.rstrip("s")
        bound_match = COMPARATOR.search(text[max(0, match.start() - 30):match.start()])
        bound = BOUNDS[bound_match[1].casefold()] if bound_match else None
        values.add((QUANTITY_WORDS.get(value, value), unit, bound))
    return values


def quantity_supported(claim, candidates):
    value, unit, bound = claim
    return any(
        value == source_value and (not unit or unit == source_unit) and (not bound or bound == source_bound)
        for source_value, source_unit, source_bound in candidates
    )


def unsupported_claim(answer, sentences, titles):
    units = [(sentence, topic_terms(sentence), quantities(sentence)) for sentence in sentences]
    all_quantities = set().union(*(numbers for _, _, numbers in units))
    evidence_terms = set().union(*(terms for _, terms, _ in units))
    scope = {"weight", "mark", "final", "overall"}.union(*(topic_terms(title) for title in titles))
    for note in PARENTHETICAL.findall(answer):
        terms = topic_terms(note)
        if len(terms - evidence_terms) >= 2 and len(terms & evidence_terms) * 3 < len(terms) * 2:
            return True
    claims = (clause for sentence in evidence_units(answer) for clause in CLAUSE_BREAK.split(sentence))
    for claim in claims:
        terms = topic_terms(claim)
        if not terms:
            continue
        scores = [len(terms & candidate) for _, candidate, _ in units]
        top_score = max(scores, default=0)
        if not top_score:
            # A sentence carrying facts still needs an evidentiary link. Ignore a brief yes/no lead-in.
            return True
        best = [unit for score, unit in zip(scores, units, strict=True) if score == top_score]
        numbers = quantities(claim)
        if any(not quantity_supported(number, all_quantities) for number in numbers):
            return True
        if not ELIGIBILITY.search(claim) and not NEGATION.search(claim):
            for sentence, source_terms, source_numbers in units:
                condition = RESTRICTED_ELIGIBILITY.search(sentence)
                if condition and len(terms & source_terms) >= 2:
                    if terms & topic_terms(condition["subject"]) or numbers & source_numbers:
                        return True
        if len(numbers) == 1:
            # Use the item being measured, excluding course names and the proposed number.
            specific = {term for term in terms - scope if not term[0].isdigit() and term not in QUANTITY_WORDS}
            matches = [(len(specific & candidate), values) for _, candidate, values in units]
            strongest = max((score for score, _ in matches), default=0)
            number = next(iter(numbers))
            if strongest >= 2 and not any(
                quantity_supported(number, values) for score, values in matches if score == strongest
            ):
                return True
        # Preserve a directly cited prohibition. A negative conclusion from positive rules
        # (for example, "a pass alone is insufficient") is checked by the separate verifier.
        if (
            top_score >= 3 and top_score * 2 >= len(terms)
            and all(NEGATION.search(sentence) for sentence, _, _ in best)
            and not NEGATION.search(claim)
        ):
            return True
    return False


def conflicting_evidence(question, ranked):
    """Detect close numeric contradictions for the same policy in the same course."""
    seen = {}
    asked = topic_terms(question)
    for source in ranked:
        for sentence in evidence_units(source["content"]):
            terms = topic_terms(sentence)
            numbers = quantities(sentence)
            if len(terms) < 4 or len(asked & terms) < 2 or not numbers:
                continue
            pattern = QUANTITY.sub(lambda match: "#" + (match["unit"] or ""), sentence.casefold())
            signature = (source["course_id"], pattern)
            previous = seen.get(signature)
            if previous and previous != numbers:
                return True
            seen[signature] = numbers
    return False


def validate_answer(raw, passages, question):
    try:
        parsed = ModelAnswer.model_validate_json(raw)
    except ValidationError:
        raise ProviderError("invalid_model_json", "The provider response did not match the answer schema.", True) from None

    if parsed.status == "abstained":
        if parsed.answer is not None or parsed.citations or not (parsed.abstention_reason or "").strip():
            raise ProviderError("invalid_abstention", "The provider returned an invalid abstention.", True)
        parsed.abstention_reason = normalize(parsed.abstention_reason)[:350]
        return parsed

    if not (parsed.answer or "").strip() or not parsed.citations or parsed.abstention_reason is not None:
        raise ProviderError("invalid_answer", "The provider did not supply an answer with supporting evidence.", True)
    parsed.answer = parsed.answer.strip()
    if len(parsed.answer) > 3500:
        raise ProviderError("invalid_answer", "The provider response exceeded the answer length limit.", True)

    if polar_question_lacks_evidence(question, [row["content"] for row in passages]):
        return insufficient_evidence()
    available = {row["chunk_id"]: row for row in passages}
    cited = {}
    titles = []
    for citation in parsed.citations:
        row = available.get(citation.chunk_id)
        if (
            row is None
            or row["document_id"] != citation.document_id
            or row["page_number"] != citation.page_number
        ):
            raise ProviderError("invalid_citation", "A citation could not be matched to the retrieved document and page.", True)
        quote = normalize(citation.evidence_quote)
        if len(quote) < 12 or quote not in normalize(row["content"]):
            raise ProviderError("invalid_evidence_quote", "A cited quotation could not be found in the retrieved passage.", True)
        if excerpt_span(row["content"], quote) is None:
            raise ProviderError("incomplete_evidence_quote", "A cited quotation omitted part of the source statement.", True)
        quote = with_reference_context(row["content"], quote)
        prior = cited.get(citation.chunk_id)
        if prior is not None:
            prior.evidence_quote = merge_excerpts(row["content"], prior.evidence_quote, quote)
        else:
            citation.evidence_quote = quote
            cited[citation.chunk_id] = citation
            titles.append(row["document_title"])

    parsed.citations = list(cited.values())
    quotes = [citation.evidence_quote for citation in parsed.citations]
    if answer_cites_absence(parsed) or polar_question_lacks_evidence(question, quotes):
        return insufficient_evidence()
    if not relevant_to_question(question, quotes, titles):
        raise ProviderError("question_mismatch", "The cited excerpts did not address the question asked.", True)
    sentences = [
        clause for quote in quotes for sentence in evidence_units(quote) for clause in CLAUSE_BREAK.split(sentence)
    ]
    if not content_terms(parsed.answer) or unsupported_claim(parsed.answer, sentences, titles):
        raise ProviderError("unsupported_answer", "The cited excerpts did not sufficiently support the proposed answer.", True)
    return parsed


def validate_verification(raw):
    try:
        verified = ModelVerification.model_validate_json(raw)
    except ValidationError:
        raise ProviderError(
            "invalid_verification_json", "The answer verification response did not match its schema.", True,
        ) from None
    if not verified.reason.strip():
        raise ProviderError("invalid_verification_json", "The answer verification response was incomplete.", True)
    return verified

