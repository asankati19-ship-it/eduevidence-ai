"""Check the locked evidence against the bundled PDFs using the separate pypdf extractor."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import unicodedata

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data/evaluation_ground_truth.json"
PDF_DIR = ROOT / "data/sample_documents"


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--capture", type=Path, help="Also verify the final displayed quotes from a saved benchmark run.")
    args = parser.parse_args()
    label_bytes = LABELS.read_bytes()
    truth = json.loads(label_bytes)
    pages = {}
    for key, document in truth["documents"].items():
        source = PDF_DIR / document["filename"]
        assert sha256(source.read_bytes()).hexdigest() == document["sha256"], source.name
        pages[key] = [normalize(page.extract_text()) for page in PdfReader(source).pages]
        assert len(pages[key]) == document["page_count"], source.name

    checks = []
    for case in truth["questions"]:
        for source in case["expected"]["evidence"]:
            original = pages[source["document"]][source["page"] - 1]
            for excerpt in source["excerpts"]:
                assert normalize(excerpt) in original, (case["id"], source, excerpt)
                checks.append({"id": case["id"], "document": source["document"], "page": source["page"], "excerpt": excerpt})
    result = {
        "source_checksums_verified": len(pages),
        "pdf_pages_read": sum(map(len, pages.values())),
        "tests_labeled": len(truth["questions"]),
        "evidence_checks": checks,
        "ground_truth_sha256": sha256(label_bytes).hexdigest(),
    }
    if args.capture:
        capture_bytes = args.capture.read_bytes()
        capture = json.loads(capture_bytes)
        assert capture["ground_truth_sha256"] == result["ground_truth_sha256"]
        actual_quotes = []
        for case in capture["cases"]:
            for citation in case["response"].get("citations", []):
                key, page, quote = citation["document_key"], citation["page_number"], citation["evidence_quote"]
                assert citation["original_filename"] == truth["documents"][key]["filename"], case["id"]
                assert normalize(quote) in pages[key][page - 1], (case["id"], key, page, quote)
                actual_quotes.append({"id": case["id"], "document": key, "page": page, "excerpt": quote})
        result["checked_capture_sha256"] = sha256(capture_bytes).hexdigest()
        result["displayed_evidence_checks"] = actual_quotes
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Verified {len(checks)} exact excerpts on {result['pdf_pages_read']} pages across {len(pages)} unchanged PDFs.")
    if args.capture:
        print(f"Verified {len(result['displayed_evidence_checks'])} displayed quotations against their original pages.")


if __name__ == "__main__":
    main()
