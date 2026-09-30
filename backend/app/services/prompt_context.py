"""What is added to a question before the LLM sees it.

Three things raise accuracy without touching the model: verified question/SQL
pairs the user bookmarked (few-shot examples), the business terms a question
uses, and — when generated SQL fails — the database's own error so the model
can correct itself. Pure functions, so the rules can be tested on their own.
"""
import re
from typing import Any, Dict, List, Mapping, Sequence

MAX_ERROR_CHARS = 600
# Below this similarity a bookmark is noise, not guidance.
MIN_SIMILARITY = 0.12


def _grams(text: str) -> set:
    """Character bigrams: works for Korean, which has no spaces to split on."""
    compact = re.sub(r"\s+", "", text.lower())
    return {compact[i:i + 2] for i in range(len(compact) - 1)}


def _similarity(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def pick_examples(
    question: str,
    bookmarks: Sequence[Mapping[str, Any]],
    k: int = 3,
) -> List[Mapping[str, Any]]:
    """The k bookmarked question/SQL pairs most like `question`, best first."""
    seen = set()
    scored = []
    for b in bookmarks:
        q = (b.get("question") or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        score = _similarity(question, q)
        if score >= MIN_SIMILARITY:
            scored.append((score, b))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [b for _, b in scored[:k]]


def pick_terms(question: str, terms: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """The glossary terms the question mentions, ignoring spaces."""
    compact = re.sub(r"\s+", "", question.lower())
    return [
        t for t in terms
        if re.sub(r"\s+", "", (t.get("term") or "").lower()) and
        re.sub(r"\s+", "", t["term"].lower()) in compact
    ]


def build_context(
    user_context: str,
    examples: Sequence[Mapping[str, Any]],
    terms: Sequence[Mapping[str, Any]],
) -> str:
    """The CONTEXT block of the prompt."""
    parts: List[str] = []
    if user_context.strip():
        parts.append(user_context.strip())
    if terms:
        lines = "\n".join(f"- {t['term']}: {t['definition']}" for t in terms)
        parts.append(f"BUSINESS TERMS (use these definitions):\n{lines}")
    if examples:
        shown = "\n\n".join(f"Q: {e['question']}\nSQL: {e['sql']}" for e in examples)
        parts.append(f"VERIFIED EXAMPLES (same database, known to be correct):\n{shown}")
    return "\n\n".join(parts)


def retry_context(failed_sql: str, error: str) -> str:
    """Tell the model what it wrote and what the database said about it."""
    return (
        "YOUR PREVIOUS SQL FAILED. Fix it and return only the corrected SQL.\n"
        f"Failed SQL:\n{failed_sql}\n"
        f"Database error: {error.strip()[:MAX_ERROR_CHARS]}"
    )
