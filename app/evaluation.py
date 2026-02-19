import argparse
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.rag import RAGService


_UUID_PREFIX_RE = re.compile(r"^[0-9a-fA-F]{32}_")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


def _tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 1 and token not in _STOPWORDS}


def _normalize_source(source: str) -> str:
    source_name = Path(str(source)).name.strip().lower()
    return _UUID_PREFIX_RE.sub("", source_name)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _answer_overlap(expected_answer: str, predicted_answer: str) -> float | None:
    expected_tokens = _tokens(expected_answer)
    if not expected_tokens:
        return None
    predicted_tokens = _tokens(predicted_answer)
    return len(expected_tokens.intersection(predicted_tokens)) / len(expected_tokens)


def _answer_f1(expected_answer: str, predicted_answer: str) -> float | None:
    expected_tokens = _tokens(expected_answer)
    if not expected_tokens:
        return None
    predicted_tokens = _tokens(predicted_answer)
    if not predicted_tokens:
        return 0.0
    intersection = len(expected_tokens.intersection(predicted_tokens))
    if intersection == 0:
        return 0.0
    precision = intersection / len(predicted_tokens)
    recall = intersection / len(expected_tokens)
    return (2 * precision * recall) / (precision + recall)


def _required_term_coverage(required_terms: list[str], answer: str) -> float | None:
    normalized_terms = [term.strip().lower() for term in required_terms if str(term).strip()]
    if not normalized_terms:
        return None
    answer_lc = answer.lower()
    matches = sum(1 for term in normalized_terms if term in answer_lc)
    return matches / len(normalized_terms)


def _forbidden_term_violation(forbidden_terms: list[str], answer: str) -> float | None:
    normalized_terms = [term.strip().lower() for term in forbidden_terms if str(term).strip()]
    if not normalized_terms:
        return None
    answer_lc = answer.lower()
    violated = any(term in answer_lc for term in normalized_terms)
    return 1.0 if violated else 0.0


def _source_scores(expected_sources: list[str], cited_sources: set[str]) -> tuple[float | None, float | None, float | None]:
    normalized_expected = {
        _normalize_source(source) for source in expected_sources if str(source).strip()
    }
    if not normalized_expected:
        return None, None, None

    if not cited_sources:
        return 0.0, 0.0, 0.0

    intersection = normalized_expected.intersection(cited_sources)
    hit = 1.0 if intersection else 0.0
    recall = len(intersection) / len(normalized_expected)
    precision = len(intersection) / len(cited_sources)
    return hit, recall, precision


def evaluate_cases(service: "RAGService", cases: list[dict[str, Any]]) -> dict[str, float]:
    if not cases:
        return {
            "answer_overlap": 0.0,
            "answer_f1": 0.0,
            "retrieval_hit_rate": 0.0,
            "source_recall": 0.0,
            "source_precision": 0.0,
            "groundedness": 0.0,
            "required_term_coverage": 0.0,
            "forbidden_term_violation_rate": 0.0,
            "valid_case_rate": 0.0,
            "success_rate": 0.0,
        }

    overlap_scores: list[float] = []
    f1_scores: list[float] = []
    retrieval_hits: list[int] = []
    source_recalls: list[float] = []
    source_precisions: list[float] = []
    groundedness_scores: list[float] = []
    required_term_scores: list[float] = []
    forbidden_term_violations: list[float] = []
    valid_cases = 0
    successful_cases = 0

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue

        question = str(case.get("question", "")).strip()
        if not question:
            continue
        valid_cases += 1

        try:
            response = service.answer(question, session_id=f"evaluation-{idx}")
        except Exception:
            continue
        successful_cases += 1

        answer_text = response.answer or ""
        overlap = _answer_overlap(str(case.get("expected_answer", "")), answer_text)
        if overlap is not None:
            overlap_scores.append(overlap)

        f1_score = _answer_f1(str(case.get("expected_answer", "")), answer_text)
        if f1_score is not None:
            f1_scores.append(f1_score)

        expected_sources = case.get("expected_sources", [])
        if isinstance(expected_sources, list):
            cited_sources = {_normalize_source(c.source) for c in response.citations}
            hit, source_recall, source_precision = _source_scores(expected_sources, cited_sources)
            if hit is not None:
                retrieval_hits.append(int(hit))
            if source_recall is not None:
                source_recalls.append(source_recall)
            if source_precision is not None:
                source_precisions.append(source_precision)

        required_terms = case.get("required_terms", [])
        if isinstance(required_terms, list):
            required_coverage = _required_term_coverage(required_terms, answer_text)
            if required_coverage is not None:
                required_term_scores.append(required_coverage)

        forbidden_terms = case.get("forbidden_terms", [])
        if isinstance(forbidden_terms, list):
            violation = _forbidden_term_violation(forbidden_terms, answer_text)
            if violation is not None:
                forbidden_term_violations.append(violation)

        answer_tokens = _tokens(answer_text)
        context_tokens = _tokens(" ".join(response.retrieved_contexts))
        groundedness = 0.0
        if answer_tokens:
            groundedness = len(answer_tokens.intersection(context_tokens)) / len(answer_tokens)
        groundedness_scores.append(groundedness)

    total_cases = len(cases)
    return {
        "answer_overlap": round(_mean(overlap_scores), 4),
        "answer_f1": round(_mean(f1_scores), 4),
        "retrieval_hit_rate": round(_mean([float(v) for v in retrieval_hits]), 4),
        "source_recall": round(_mean(source_recalls), 4),
        "source_precision": round(_mean(source_precisions), 4),
        "groundedness": round(_mean(groundedness_scores), 4),
        "required_term_coverage": round(_mean(required_term_scores), 4),
        "forbidden_term_violation_rate": round(_mean(forbidden_term_violations), 4),
        "valid_case_rate": round((valid_cases / total_cases) if total_cases else 0.0, 4),
        "success_rate": round((successful_cases / valid_cases) if valid_cases else 0.0, 4),
    }


def main() -> None:
    from app.config import get_settings
    from app.rag import RAGService

    parser = argparse.ArgumentParser(description="Evaluate Smart Contract Assistant retrieval and answer quality.")
    parser.add_argument("--cases", default="data/eval_cases.json", help="Path to evaluation test case JSON file.")
    args = parser.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        raise FileNotFoundError(f"Evaluation cases file not found: {cases_path}")

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    service = RAGService(get_settings())
    metrics = evaluate_cases(service, cases)

    print("Evaluation Metrics")
    for key, value in metrics.items():
        print(f"- {key}: {value}")

if __name__ == "__main__":
    main()
