"""Pure-function tests for the eval metrics."""
from __future__ import annotations

import pytest

from rag.eval.metrics import (
    citation_recall,
    entity_coverage,
    must_mention_coverage,
    score,
)


class TestCitationRecall:
    def test_full_match(self):
        retrieved = [("a.pdf", 1), ("a.pdf", 2), ("b.pdf", 5)]
        expected = {"a.pdf": [1, 2], "b.pdf": [5]}
        assert citation_recall(retrieved, expected) == 1.0

    def test_partial_match(self):
        retrieved = [("a.pdf", 1)]
        expected = {"a.pdf": [1, 2], "b.pdf": [5]}
        # 1 of 3 expected pairs retrieved
        assert citation_recall(retrieved, expected) == pytest.approx(1 / 3)

    def test_no_match(self):
        assert citation_recall([("z.pdf", 99)], {"a.pdf": [1]}) == 0.0

    def test_empty_expected_returns_one(self):
        assert citation_recall([], {}) == 1.0

    def test_extra_retrieved_does_not_penalise(self):
        # Recall, not precision.
        retrieved = [("a.pdf", 1), ("a.pdf", 99), ("b.pdf", 5)]
        expected = {"a.pdf": [1], "b.pdf": [5]}
        assert citation_recall(retrieved, expected) == 1.0


class TestEntityCoverage:
    def test_full_match(self):
        assert entity_coverage(["Tiomos", "Grass"], ["Tiomos", "Grass"]) == 1.0

    def test_partial_match(self):
        assert entity_coverage(["Tiomos"], ["Tiomos", "Grass"]) == 0.5

    def test_case_insensitive(self):
        # Both normalise to "Tiomos" via .strip().title().
        assert entity_coverage(["tiomos"], ["TIOMOS"]) == 1.0

    def test_empty_expected_returns_one(self):
        assert entity_coverage([], []) == 1.0


class TestMustMentionCoverage:
    def test_all_terms_present(self):
        assert must_mention_coverage("Tiomos hinges from Grass", ["tiomos", "grass"]) == 1.0

    def test_case_insensitive(self):
        assert must_mention_coverage("Tiomos HINGES", ["tiomos", "hinges"]) == 1.0

    def test_partial(self):
        assert must_mention_coverage("Tiomos hinges", ["tiomos", "blum"]) == 0.5

    def test_empty_returns_one(self):
        assert must_mention_coverage("any answer", []) == 1.0


class TestScore:
    def test_skips_entity_metrics_when_no_entities_provided(self):
        m = score(
            retrieved_pages=[("a.pdf", 1)],
            expected_pages={"a.pdf": [1]},
        )
        assert m == {"citation_recall": 1.0}

    def test_includes_entity_metric_when_provided(self):
        m = score(
            retrieved_pages=[],
            expected_pages={},
            retrieved_entities=["Tiomos"],
            expected_entities=["Tiomos"],
        )
        assert m["entity_coverage"] == 1.0

    def test_includes_answer_metric_only_when_answer_present(self):
        m = score(
            retrieved_pages=[],
            expected_pages={},
            answer="Tiomos hinges",
            must_mention=["tiomos"],
        )
        assert m["must_mention_coverage"] == 1.0
        m2 = score(
            retrieved_pages=[],
            expected_pages={},
            must_mention=["tiomos"],  # no answer → metric skipped
        )
        assert "must_mention_coverage" not in m2
