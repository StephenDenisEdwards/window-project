"""Pins behaviour of `rag.pipeline.normalize`, including the numeric-mismatch
fix that prevents fuzzy-merging entities like '+45° Angle' / '-45° Angle'.
"""
from __future__ import annotations

import pytest

from rag.pipeline.normalize import (
    DEFAULT_ENTITY_TYPE,
    DEFAULT_RELATION_TYPE,
    apply_merges,
    build_merge_map,
    clean,
    filter_noise,
    normalize_types,
    _numeric_signature,
)


def _ext(*names: str, type: str = "product") -> list[dict]:
    """Build a minimal extractions list where each name is its own chunk."""
    return [{"entities": [{"name": n, "type": type}], "relationships": []} for n in names]


# ---------------------------------------------------------------- numeric signature

class TestNumericSignature:
    @pytest.mark.parametrize("name,expected", [
        ("+45° Angle",                    ("+45",)),
        ("-45° Angle",                    ("-45",)),
        ("105° Opening Angle",            ("105",)),
        ("1/2 Inch Inset Recess",         ("1/2",)),
        ("#40 Euro Hinge Insertion Ram",  ("40",)),
        ("110V Single Phase Pneumatic",   ("110",)),
        ("Soft Close",                    ()),
        ("Tiomos",                        ()),
        ("42/45Mm Pattern",               ("42/45",)),
    ])
    def test_extracts_expected_tokens(self, name: str, expected: tuple[str, ...]):
        assert _numeric_signature(name) == expected


# ---------------------------------------------------------------- dedupe blocking (the fix)

class TestNumericMismatchBlocking:
    """These are the bad merges the original code produced. Each must NOT happen."""

    def test_opposite_signs_not_merged(self):
        assert build_merge_map(_ext("+45° Angle", "-45° Angle")) == {}

    def test_different_angles_not_merged(self):
        assert build_merge_map(_ext("105° Opening Angle", "120° Opening Angle")) == {}

    def test_different_voltages_not_merged(self):
        assert build_merge_map(
            _ext("110V Single Phase Pneumatic", "220V Single Phase Pneumatic")
        ) == {}

    def test_different_part_numbers_not_merged(self):
        assert build_merge_map(
            _ext("#40 Euro Hinge Insertion Ram", "#18 Euro Hinge Insertion Ram")
        ) == {}

    def test_different_fractions_not_merged(self):
        assert build_merge_map(_ext("1/2 Inch Inset Recess", "1 Inch Inset Recess")) == {}

    def test_can_be_disabled_for_explicit_use_cases(self):
        # Belt-and-braces: opt-out exists if downstream wants the old behaviour.
        merge_map = build_merge_map(
            _ext("+45° Angle", "-45° Angle"),
            block_numeric_mismatch=False,
        )
        assert merge_map != {}


# ---------------------------------------------------------------- dedupe positive cases

class TestMergePositiveCases:
    """Real merges that should still happen — guard against over-correcting."""

    def test_plural_singular_still_merges(self):
        # "Concealed Hinges" appears twice, "Concealed Hinge" once → plural wins.
        extractions = _ext("Concealed Hinge") + _ext("Concealed Hinges") + _ext("Concealed Hinges")
        merge_map = build_merge_map(extractions)
        assert merge_map.get("Concealed Hinge") == "Concealed Hinges"

    def test_hyphen_space_equivalence_still_merges(self):
        # Normalised forms match exactly — exact-match path, not fuzzy.
        extractions = _ext("Soft-Close") + _ext("Soft Close")
        merge_map = build_merge_map(extractions)
        assert "Soft-Close" in merge_map or "Soft Close" in merge_map

    def test_pure_typo_still_merges_when_no_numerics(self):
        # Names close enough to clear the fuzzy threshold, both numeric-free.
        # 'Tiomos Hinges' vs 'Tiamos Hinges' — 1 letter different out of 13.
        extractions = _ext("Tiomos Hinges") + _ext("Tiamos Hinges")
        merge_map = build_merge_map(extractions)
        assert merge_map != {}


# ---------------------------------------------------------------- type normalisation

class TestTypeNormalization:
    def test_product_synonyms_map_to_product(self):
        extractions = [{
            "entities": [
                {"name": "Tiomos", "type": "product_model"},
                {"name": "Nexis",  "type": "Product_Variant"},
                {"name": "Plate",  "type": "component"},
            ],
            "relationships": [],
        }]
        normalize_types(extractions)
        assert [e["type"] for e in extractions[0]["entities"]] == ["product", "product", "product"]

    def test_unknown_entity_type_defaults(self):
        extractions = [{
            "entities": [{"name": "Thing", "type": "totally_invented"}],
            "relationships": [],
        }]
        normalize_types(extractions)
        assert extractions[0]["entities"][0]["type"] == DEFAULT_ENTITY_TYPE

    def test_unknown_relation_type_defaults(self):
        extractions = [{
            "entities": [],
            "relationships": [{"source": "A", "target": "B", "relation": "obscure_rel"}],
        }]
        normalize_types(extractions)
        assert extractions[0]["relationships"][0]["relation"] == DEFAULT_RELATION_TYPE

    def test_relationship_with_missing_source_is_dropped(self):
        extractions = [{
            "entities": [],
            "relationships": [
                {"source": None, "target": "B", "relation": "has_feature"},
                {"source": "A", "target": "B", "relation": "has_feature"},
            ],
        }]
        normalize_types(extractions)
        assert len(extractions[0]["relationships"]) == 1
        assert extractions[0]["relationships"][0]["source"] == "A"


# ---------------------------------------------------------------- filter_noise

class TestFilterNoise:
    def test_stop_word_entity_removed(self):
        ext = [{"entities": [{"name": "Mm", "type": "specification"},
                              {"name": "Tiomos", "type": "product"}],
                "relationships": []}]
        filter_noise(ext)
        assert [e["name"] for e in ext[0]["entities"]] == ["Tiomos"]

    def test_too_short_name_removed(self):
        ext = [{"entities": [{"name": "X", "type": "product"},
                              {"name": "Tiomos", "type": "product"}],
                "relationships": []}]
        filter_noise(ext)
        assert "X" not in [e["name"] for e in ext[0]["entities"]]

    def test_pure_numeric_name_removed(self):
        ext = [{"entities": [{"name": "42", "type": "specification"},
                              {"name": "42/45", "type": "specification"},
                              {"name": "Tiomos", "type": "product"}],
                "relationships": []}]
        filter_noise(ext)
        names = [e["name"] for e in ext[0]["entities"]]
        assert "42" not in names
        assert "42/45" not in names
        assert "Tiomos" in names

    def test_short_relationship_endpoints_dropped(self):
        ext = [{"entities": [], "relationships": [
            {"source": "A",      "target": "Tiomos", "relation": "has_feature"},
            {"source": "Tiomos", "target": "Grass",  "relation": "manufactured_by"},
        ]}]
        filter_noise(ext)
        # First relationship has too-short source ("A") — dropped.
        assert len(ext[0]["relationships"]) == 1


# ---------------------------------------------------------------- composition

class TestCleanPipeline:
    def test_clean_runs_all_steps(self):
        ext = [{
            "entities": [
                {"name": "Tiomos",         "type": "product_model"},
                {"name": "Concealed Hinge",  "type": "category"},
                {"name": "Concealed Hinges", "type": "category"},
                {"name": "Mm",             "type": "specification"},  # stop-word, filtered
                {"name": "+45° Angle",     "type": "specification"},
                {"name": "-45° Angle",     "type": "specification"},
            ],
            "relationships": [
                {"source": "Tiomos", "target": "Grass", "relation": "manufactured_by"},
            ],
        }]
        clean(ext)
        names = [e["name"] for e in ext[0]["entities"]]
        assert "Mm" not in names                # filtered as stop-word
        assert "Tiomos" in names                # survives
        assert "+45° Angle" in names            # NOT merged into -45°
        assert "-45° Angle" in names
        # Type normalisation applied
        assert all(e["type"] in {"product", "specification", "category", "feature",
                                  "material", "manufacturer", "certification"}
                   for e in ext[0]["entities"])
