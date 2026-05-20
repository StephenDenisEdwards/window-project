"""Post-processing of extractions: type normalisation, fuzzy dedupe, noise filtering.

The dedupe step (`build_merge_map`) is where the existing notebook silently
corrupts the knowledge graph. Two protections are added here:

  1. Numeric mismatch blocking — refuse to fuzzy-merge two names whose
     signed numeric tokens differ. Without this, names like '+45° Angle'
     and '-45° Angle', or '105° Opening Angle' and '120° Opening Angle',
     get collapsed at the default 0.92 SequenceMatcher threshold.
  2. The fuzzy threshold and the numeric-block are now both parameters,
     so callers can tune them and tests can pin behaviour.
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

# === Type maps ====================================================

ENTITY_TYPE_MAP: dict[str, str] = {
    "product": "product", "product_model": "product", "product_variant": "product",
    "product_code": "product", "product_id": "product", "product_series": "product",
    "product_line": "product", "product_component": "product", "component": "product",
    "accessory": "product", "accessory_item": "product", "part": "product",
    "variant": "product", "hinge_style": "product", "tool": "product",
    "item_number": "product",
    "manufacturer": "manufacturer", "company": "manufacturer", "brand": "manufacturer",
    "supplier": "manufacturer",
    "feature": "feature", "product_feature": "feature", "function": "feature",
    "technology": "feature", "action": "feature", "property": "feature",
    "attribute": "feature", "description": "feature",
    "specification": "specification", "product_specification": "specification",
    "dimension": "specification", "weight": "specification", "size": "specification",
    "value": "specification", "quantity": "specification", "unit_of_measurement": "specification",
    "unit_of_measure": "specification", "pattern": "specification",
    "drill_pattern": "specification", "drilling_pattern": "specification",
    "fixing_method": "specification", "number": "specification",
    "material": "material",
    "certification": "certification", "standard": "certification",
    "category": "category", "section": "category", "application": "category",
    "product_application": "category", "usage": "category", "cabinetry": "category",
    "context": "category", "location": "category", "document": "category",
}

RELATION_TYPE_MAP: dict[str, str] = {
    "has_feature": "has_feature", "includes_feature": "has_feature",
    "includes": "has_feature", "has_close_type": "has_feature",
    "includes_technology": "has_feature", "has_opening": "has_feature",
    "has_position": "has_feature", "provides": "has_feature",
    "enables": "has_feature", "controls": "has_feature",
    "integrated_with": "has_feature", "has_power_factor_range": "has_feature",
    "offers": "has_feature",
    "has_specification": "has_specification", "has_dimension": "has_specification",
    "has_weight": "has_specification", "has_pattern": "has_specification",
    "has_fixing": "has_specification", "has_unit_of_measure": "has_specification",
    "has_description": "has_specification", "has_cabinet_height_range": "has_specification",
    "is_unit_of": "has_specification", "has": "has_specification",
    "has_number": "has_specification",
    "part_of": "part_of", "is_part_of": "part_of", "contains": "part_of",
    "consists_of": "part_of", "belongs_to": "part_of",
    "compatible_with": "compatible_with", "suitable_for": "compatible_with",
    "suited_for": "compatible_with", "applies_to": "compatible_with",
    "applicable_to": "compatible_with", "used_for": "compatible_with",
    "recommended_for": "compatible_with", "recommends": "compatible_with",
    "attaches_to": "compatible_with", "found_on": "compatible_with",
    "for": "compatible_with",
    "manufactured_by": "manufactured_by",
    "variant_of": "variant_of", "is_variant_of": "variant_of",
    "made_of": "has_specification",
}

STOP_ENTITIES: frozenset[str] = frozenset({
    "N/A", "None", "Unknown", "Other", "Yes", "No", "See", "Page",
    "Table", "Figure", "Note", "Section", "Mm", "Kg", "Lbs", "Item #",
    "Contents", "Index", "Catalog", "Overview",
})

DEFAULT_ENTITY_TYPE = "feature"
DEFAULT_RELATION_TYPE = "has_feature"


# === Operations ====================================================

def normalize_types(extractions: list[dict]) -> list[dict]:
    """Map raw LLM-emitted type/relation strings to the canonical set, in place.

    Unknown entity types collapse to ``DEFAULT_ENTITY_TYPE``; unknown
    relation types collapse to ``DEFAULT_RELATION_TYPE``. Relationships
    with missing/non-string ``source`` or ``target`` are dropped.
    """
    for extraction in extractions:
        for entity in extraction.get("entities", []):
            raw = str(entity.get("type", "unknown")).lower().strip()
            entity["type"] = ENTITY_TYPE_MAP.get(raw, DEFAULT_ENTITY_TYPE)

        for rel in extraction.get("relationships", []):
            raw_rel = rel.get("relation", "related_to")
            if raw_rel:
                raw_rel = str(raw_rel).lower().strip()
            rel["relation"] = RELATION_TYPE_MAP.get(raw_rel, DEFAULT_RELATION_TYPE)

        extraction["relationships"] = [
            r for r in extraction.get("relationships", [])
            if isinstance(r.get("source"), str) and isinstance(r.get("target"), str)
            and r["source"] and r["target"]
        ]
    return extractions


_NUMERIC_TOKEN_RE = re.compile(r"[+\-]?\d+(?:[./]\d+)?")


def _numeric_signature(name: str) -> tuple[str, ...]:
    """Extract signed/unsigned numeric tokens from a name.

    Used to block fuzzy-merging entities that differ only in numbers
    (sizes, angles, signs, voltages, part numbers, fractions).

    Examples:
        '+45° Angle'                    -> ('+45',)
        '-45° Angle'                    -> ('-45',)
        '105° Opening Angle'            -> ('105',)
        '1/2 Inch Inset Recess'         -> ('1/2',)
        '#40 Euro Hinge Insertion Ram'  -> ('40',)
        '110V Single Phase Pneumatic'   -> ('110',)
        'Soft Close'                    -> ()
    """
    return tuple(_NUMERIC_TOKEN_RE.findall(name))


def build_merge_map(
    extractions: list[dict],
    *,
    fuzzy_threshold: float = 0.92,
    block_numeric_mismatch: bool = True,
    max_compared_len: int = 30,
    min_compared_len: int = 4,
) -> dict[str, str]:
    """Build a ``{variant_name: canonical_name}`` map for entity deduplication.

    Two passes are run on the alphabetically-sorted unique names:

    * Exact match after case- and separator-normalisation
      (``-``/``_``  → space, then ``.lower()``).
    * Fuzzy match at ``fuzzy_threshold`` (default 0.92) on normalised forms,
      restricted to short-ish names to keep cost bounded.

    For each merge, the more-frequently-mentioned name wins; ties go to the
    alphabetically-first name (stable).

    When ``block_numeric_mismatch=True`` (default), fuzzy merges are skipped
    if the two names have different signed numeric tokens.
    """
    # Count occurrences across both entities and relationship endpoints
    name_counts: Counter[str] = Counter()
    for ex in extractions:
        for e in ex.get("entities", []):
            name = str(e.get("name", "")).strip().title()
            if name:
                name_counts[name] += 1
        for r in ex.get("relationships", []):
            for key in ("source", "target"):
                val = r.get(key)
                if val and isinstance(val, str):
                    name_counts[val.strip().title()] += 1

    names = sorted(name_counts)
    merge_map: dict[str, str] = {}

    for i, name_a in enumerate(names):
        if name_a in merge_map:
            continue
        a_norm = name_a.lower().replace("-", " ").replace("_", " ").strip()
        a_sig = _numeric_signature(name_a) if block_numeric_mismatch else None

        for name_b in names[i + 1:]:
            if name_b in merge_map:
                continue
            b_norm = name_b.lower().replace("-", " ").replace("_", " ").strip()

            if a_norm == b_norm:
                canonical, variant = _pick_canonical(name_a, name_b, name_counts)
                merge_map[variant] = canonical
                continue

            if not (min_compared_len <= len(a_norm) <= max_compared_len and
                    min_compared_len <= len(b_norm) <= max_compared_len):
                continue

            if SequenceMatcher(None, a_norm, b_norm).ratio() < fuzzy_threshold:
                continue

            if block_numeric_mismatch and a_sig != _numeric_signature(name_b):
                continue

            canonical, variant = _pick_canonical(name_a, name_b, name_counts)
            merge_map[variant] = canonical

    return merge_map


def _pick_canonical(a: str, b: str, counts: Counter[str]) -> tuple[str, str]:
    """Return ``(canonical, variant)``. More-mentioned wins; ties go to ``a``."""
    if counts[a] >= counts[b]:
        return a, b
    return b, a


def apply_merges(extractions: list[dict], merge_map: dict[str, str]) -> list[dict]:
    """Rewrite entity and relationship names using ``merge_map``, in place."""
    for ex in extractions:
        for e in ex.get("entities", []):
            name = str(e.get("name", "")).strip().title()
            e["name"] = merge_map.get(name, name)
        for r in ex.get("relationships", []):
            for key in ("source", "target"):
                val = r.get(key)
                if val and isinstance(val, str):
                    name = val.strip().title()
                    r[key] = merge_map.get(name, name)
    return extractions


def filter_noise(
    extractions: list[dict],
    *,
    stop: frozenset[str] = STOP_ENTITIES,
    min_name_len: int = 3,
) -> list[dict]:
    """Drop stop-word entities, names shorter than ``min_name_len``,
    and pure-punctuation/numeric names. In place.
    """
    def is_pure_numeric(name: str) -> bool:
        return name.replace(".", "").replace(",", "").replace("/", "") \
                   .replace("-", "").replace(" ", "").isdigit()

    for ex in extractions:
        ex["entities"] = [
            e for e in ex.get("entities", [])
            if isinstance(e.get("name"), str)
            and len(e["name"].strip()) >= min_name_len
            and e["name"].strip().title() not in stop
            and not is_pure_numeric(e["name"].strip())
        ]
        ex["relationships"] = [
            r for r in ex.get("relationships", [])
            if isinstance(r.get("source"), str) and len(r["source"].strip()) >= min_name_len
            and isinstance(r.get("target"), str) and len(r["target"].strip()) >= min_name_len
        ]
    return extractions


def clean(extractions: list[dict]) -> list[dict]:
    """Full post-processing pipeline: normalise types → dedupe → filter noise."""
    normalize_types(extractions)
    apply_merges(extractions, build_merge_map(extractions))
    filter_noise(extractions)
    return extractions
