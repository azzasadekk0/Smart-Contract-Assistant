import re
from collections.abc import Iterable


_BLOCKED_PATTERNS = [
    re.compile(r"\b(ignore|bypass|disable)\b.{0,30}\b(safety|guardrail|restriction)\b", re.IGNORECASE),
    re.compile(r"\b(leak|exfiltrate|steal)\b", re.IGNORECASE),
    re.compile(r"\b(system prompt|developer message)\b", re.IGNORECASE),
]


def check_query_safety(query: str, max_chars: int) -> tuple[bool, str | None]:
    if not query.strip():
        return False, "Question is empty."
    if len(query) > max_chars:
        return False, f"Question is too long (>{max_chars} chars)."
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(query):
            return False, "Query violates safety policy."
    return True, None


def grounding_ratio(answer: str, contexts: Iterable[str]) -> float:
    answer_tokens = set(re.findall(r"[a-zA-Z0-9]+", answer.lower()))
    if not answer_tokens:
        return 0.0
    context_tokens: set[str] = set()
    for context in contexts:
        context_tokens.update(re.findall(r"[a-zA-Z0-9]+", context.lower()))
    if not context_tokens:
        return 0.0
    overlap = answer_tokens.intersection(context_tokens)
    return len(overlap) / len(answer_tokens)
