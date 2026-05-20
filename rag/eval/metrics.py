"""Pure metric functions for scoring a retrieval/answer against expected criteria.

All functions take plain inputs (lists/sets/strings) so they're trivially
testable without spinning up Chroma or the LLM.
"""
from __future__ import annotations


def citation_recall(
    retrieved_pages: list[tuple[str, int]],
    expected_pages: dict[str, list[int]],
) -> float:
    """Fraction of expected (source, page) pairs that appear in retrieval.

    Returns 1.0 if `expected_pages` is empty (vacuously true).
    """
    expected_pairs: set[tuple[str, int]] = {
        (src, page) for src, pages in expected_pages.items() for page in pages
    }
    if not expected_pairs:
        return 1.0
    retrieved = set(retrieved_pages)
    return len(expected_pairs & retrieved) / len(expected_pairs)


def entity_coverage(
    retrieved_entities: list[str],
    expected_entities: list[str],
) -> float:
    """Fraction of expected entities that appear among retrieved ones.

    Comparison is case-insensitive on title-cased names. Returns 1.0 for
    empty expectations.
    """
    if not expected_entities:
        return 1.0
    retrieved_norm = {e.strip().title() for e in retrieved_entities}
    expected_norm = {e.strip().title() for e in expected_entities}
    return len(expected_norm & retrieved_norm) / len(expected_norm)


def must_mention_coverage(answer: str, must_mention: list[str]) -> float:
    """Fraction of `must_mention` substrings present in `answer` (case-insensitive).

    Returns 1.0 if `must_mention` is empty.
    """
    if not must_mention:
        return 1.0
    ans = answer.lower()
    hits = sum(1 for term in must_mention if term.lower() in ans)
    return hits / len(must_mention)


def score(
    *,
    retrieved_pages: list[tuple[str, int]],
    expected_pages: dict[str, list[int]],
    retrieved_entities: list[str] | None = None,
    expected_entities: list[str] | None = None,
    answer: str | None = None,
    must_mention: list[str] | None = None,
) -> dict[str, float]:
    """Compute every metric we can, given whatever inputs the caller provides.

    Skips entity metrics if `retrieved_entities` is None (vanilla RAG run);
    skips answer metrics if `answer` is None (retrieval-only run).
    """
    metrics: dict[str, float] = {
        "citation_recall": citation_recall(retrieved_pages, expected_pages),
    }
    if retrieved_entities is not None and expected_entities is not None:
        metrics["entity_coverage"] = entity_coverage(retrieved_entities, expected_entities)
    if answer is not None and must_mention is not None:
        metrics["must_mention_coverage"] = must_mention_coverage(answer, must_mention)
    return metrics
