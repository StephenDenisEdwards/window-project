"""Hand-curated evaluation query set for the catalog GraphRAG pipeline.

Each `QueryCase` describes:
  - `id`              short slug for filenames/logs
  - `query`           the natural-language question
  - `expected_pages`  catalog pages where the answer should be grounded
  - `must_have_entities` graph nodes that ought to be seeded for this query
  - `must_mention`    substrings the final answer should contain (case-insensitive)
  - `notes`           freeform context for the human reviewer

Expected pages and entities were chosen by inspecting the cached
extractions and the executed-notebook outputs — i.e. ground truth is
"what a good run of this pipeline actually returned, when it worked".
Treat them as regression anchors, not gold standard.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class QueryCase:
    id: str
    query: str
    expected_pages: dict[str, list[int]] = field(default_factory=dict)
    must_have_entities: list[str] = field(default_factory=list)
    must_mention: list[str] = field(default_factory=list)
    notes: str = ""


QUERIES: list[QueryCase] = [
    QueryCase(
        id="soft-close-tiomos",
        query="What soft-close hinge options are available from Grass Tiomos?",
        expected_pages={
            "grass-tiomos-catalog.pdf": [3, 4],
            "wurth-baer-section-b-concealed-hinges.pdf": [45, 46],
        },
        must_have_entities=["Tiomos", "Grass", "Soft-Close"],
        must_mention=["tiomos", "soft-close", "grass"],
        notes="Direct named-product query. Should seed multiple entities by text match.",
    ),
    QueryCase(
        id="nexis-vs-tiomos",
        query="Compare Grass Nexis and Tiomos hinge systems.",
        expected_pages={
            "grass-nexis-catalog.pdf": [2, 3],
            "grass-tiomos-catalog.pdf": [3, 4],
        },
        must_have_entities=["Nexis", "Tiomos"],
        must_mention=["nexis", "tiomos"],
        notes="Cross-product comparison. Tests retrieval breadth.",
    ),
    QueryCase(
        id="opening-angle-spec",
        query="What is the maximum opening angle available for concealed hinges?",
        expected_pages={
            "grass-nexis-catalog.pdf": [2],
            "wurth-baer-section-b-concealed-hinges.pdf": [45, 46, 47],
        },
        must_have_entities=["Concealed Hinges"],
        must_mention=["170", "opening angle"],
        notes="Specific-fact query. Tests whether GraphRAG vs vanilla RAG diverge.",
    ),
    QueryCase(
        id="mounting-plate-compatibility",
        query="What mounting plates are compatible with Tiomos hinges?",
        expected_pages={
            "grass-tiomos-catalog.pdf": [4, 5],
            "wurth-baer-section-b-concealed-hinges.pdf": [45],
        },
        must_have_entities=["Tiomos", "Base Plate"],
        must_mention=["tiomos", "base plate"],
        notes="Multi-hop query (product -> compatible plate). GraphRAG should shine here.",
    ),
    QueryCase(
        id="product-categories",
        query="What are the main product categories across all catalogs?",
        expected_pages={
            "Wurth_Baer_Section_C.pdf": [1],
            "wurth-baer-section-b-concealed-hinges.pdf": [1],
        },
        must_have_entities=["Concealed Hinges"],
        must_mention=["hinges"],
        notes="Broad/thematic query. Community summaries should help.",
    ),
]
