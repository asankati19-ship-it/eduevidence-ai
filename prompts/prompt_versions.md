# Prompt versions

| Version | Behavior |
|---|---|
| 1.0.0 | Evidence-only instructions, JSON-delimited untrusted passages, strict response contract, and verbatim supporting quotes. |
| 2.0.0 | Direct, qualified answers with complete source quotations. A separate structured verification request checks relevance, factual support, and conflicts before saving an answer as successful. |
| 2.1.0 | Converts answers that rely on an explicit evidence omission to abstentions and attaches the source context for relative references such as “the same area.” |
| 2.2.0 | Checks whether citations cover the topic of a focused yes-or-no question before accepting a conclusion. |
| 2.2.1 | Validates each repeated citation and consolidates valid excerpts from the same chunk into one continuous quote. |
| 2.3.0 | Checks quantities by clause, recognizes common written fractions, and sends only validated quotations to the verifier. |
| 2.4.0 | Preserves explicit eligibility, checks parenthetical claims, and matches quantities to the measured item in cross-course answers. Checks returned evidence for focused yes-or-no questions before validating the proposed quotations. |

The provider reads the generation and verification prompts and both checked-in schemas. Examples explain the contract and are excluded from runtime prompts. Update the persisted version in [the provider module](../backend/app/services/provider.py) and rerun the evidence acceptance cases when changing these files. [Version 2.4.0 audit](../docs/functional_accuracy_report.md)

