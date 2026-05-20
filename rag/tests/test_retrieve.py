"""Pins behaviour of `rag.pipeline.retrieve`, especially the bug that made
GraphRAG silently degrade to vector-only RAG ('Graph entities found: 0').
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import pytest

from rag.pipeline.retrieve import (
    ChunkHit,
    Retrieval,
    expand_via_hops,
    find_entities_in_chunks,
    find_entities_in_query,
    graph_retrieve,
    render_graph_context,
    vector_retrieve_chunks,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def small_graph() -> nx.Graph:
    """Tiny graph mirroring the real catalog structure."""
    G = nx.Graph()
    G.add_node("Tiomos", type="product", mentions=66,
               chunk_ids={"grass-tiomos-catalog_p3_c0", "grass-tiomos-catalog_p4_c0"})
    G.add_node("Grass", type="manufacturer", mentions=119,
               chunk_ids={"grass-tiomos-catalog_p1_c0", "grass-tiomos-catalog_p3_c0"})
    G.add_node("Soft-Close", type="feature", mentions=54,
               chunk_ids={"grass-tiomos-catalog_p4_c0"})
    G.add_node("Base Plate", type="product", mentions=74,
               chunk_ids={"grass-nexis-catalog_p5_c0"})
    G.add_node("Nexis", type="product", mentions=33,
               chunk_ids={"grass-nexis-catalog_p2_c0"})
    G.add_edge("Tiomos", "Grass", weight=2, relations={"manufactured_by"})
    G.add_edge("Tiomos", "Soft-Close", weight=1, relations={"has_feature"})
    G.add_edge("Tiomos", "Base Plate", weight=1, relations={"compatible_with"})
    G.add_edge("Base Plate", "Nexis", weight=1, relations={"compatible_with"})
    return G


@dataclass
class _FakeCollection:
    """Minimal Chroma-collection stand-in: returns canned hits."""
    hits: list[tuple[str, str, dict, float]]

    def query(self, *, query_texts: list[str], n_results: int) -> dict:
        rows = self.hits[:n_results]
        return {
            "ids": [[r[0] for r in rows]],
            "documents": [[r[1] for r in rows]],
            "metadatas": [[r[2] for r in rows]],
            "distances": [[r[3] for r in rows]],
        }


@dataclass
class _FakeStore:
    chunks: _FakeCollection
    communities: _FakeCollection


# ---------------------------------------------------------------- entity seeding

class TestFindEntitiesInChunks:
    """The original bug: this intersection produced 0 hits."""

    def test_finds_entities_for_intersecting_chunk_ids(self, small_graph):
        hits = find_entities_in_chunks(small_graph, {"grass-tiomos-catalog_p4_c0"})
        assert hits == {"Tiomos", "Soft-Close"}

    def test_returns_empty_for_unknown_chunk_ids(self, small_graph):
        # This is what the original broken pipeline kept seeing: store IDs
        # like `chunk_42` never matched graph chunk_ids like `..._p4_c0`.
        hits = find_entities_in_chunks(small_graph, {"chunk_42", "chunk_43"})
        assert hits == set()

    def test_returns_empty_for_no_chunk_ids(self, small_graph):
        assert find_entities_in_chunks(small_graph, set()) == set()


class TestFindEntitiesInQuery:
    """The new behaviour: query-text seeds entities directly."""

    def test_direct_mention(self, small_graph):
        assert find_entities_in_query(small_graph, "Tell me about Tiomos hinges") == {"Tiomos"}

    def test_normalises_hyphen(self, small_graph):
        # 'Soft-Close' → 'soft close' should match 'soft close' in query.
        assert "Soft-Close" in find_entities_in_query(small_graph, "I need soft close functionality")

    def test_skips_tokens_shorter_than_threshold(self, small_graph):
        # No node names should match generic words.
        assert find_entities_in_query(small_graph, "what is the answer") == set()

    def test_case_insensitive(self, small_graph):
        assert "Grass" in find_entities_in_query(small_graph, "tell me about grass products")


# ---------------------------------------------------------------- traversal

class TestExpandViaHops:
    def test_zero_hops_returns_only_seeds(self, small_graph):
        assert expand_via_hops(small_graph, {"Tiomos"}, hop_depth=0) == {"Tiomos"}

    def test_one_hop(self, small_graph):
        out = expand_via_hops(small_graph, {"Tiomos"}, hop_depth=1)
        assert out == {"Tiomos", "Grass", "Soft-Close", "Base Plate"}

    def test_two_hops_reaches_indirect_neighbours(self, small_graph):
        out = expand_via_hops(small_graph, {"Tiomos"}, hop_depth=2)
        assert "Nexis" in out  # Tiomos -> Base Plate -> Nexis

    def test_empty_seeds_returns_empty(self, small_graph):
        assert expand_via_hops(small_graph, set(), hop_depth=3) == set()

    def test_unknown_seed_is_ignored(self, small_graph):
        # Seed not in graph — no crash, returns just the seed.
        assert expand_via_hops(small_graph, {"GhostNode"}, hop_depth=1) == {"GhostNode"}


# ---------------------------------------------------------------- rendering

class TestRenderGraphContext:
    def test_includes_edges_between_entities_in_set(self, small_graph):
        ctx = render_graph_context(small_graph, {"Tiomos", "Grass"})
        assert "Tiomos" in ctx
        assert "manufactured_by" in ctx
        assert "Grass" in ctx

    def test_excludes_edges_outside_the_set(self, small_graph):
        # Only Tiomos selected — Soft-Close, Grass etc. not in entities set.
        ctx = render_graph_context(small_graph, {"Tiomos"})
        # render_graph_context only emits an entry if there ARE edges inside the set.
        assert ctx == ""


# ---------------------------------------------------------------- orchestration regression

class TestGraphRetrieveRegression:
    """Pins the 'Graph entities found: 0' bug from the executed notebook.

    With consistent chunk IDs and the new query-text matcher, a typical
    catalog query MUST return non-zero seed entities.
    """

    def test_returns_nonzero_entities_when_chunk_ids_align(self, small_graph):
        store = _FakeStore(
            chunks=_FakeCollection(hits=[
                ("grass-tiomos-catalog_p4_c0", "Tiomos soft-close hinge spec ...",
                 {"source": "grass-tiomos-catalog.pdf", "page": 4}, 0.21),
            ]),
            communities=_FakeCollection(hits=[
                ("community_0", "Grass cabinet hinge systems ...",
                 {"community_id": 0, "size": 300}, 0.18),
            ]),
        )
        result = graph_retrieve("What soft-close hinge options are available?", small_graph, store)
        assert len(result.chunks) == 1
        assert len(result.graph_entities) >= 2  # the bug: was always 0
        # Both the chunk-membership seeds (Tiomos, Soft-Close) and the
        # query-text seed (Soft-Close direct mention) should contribute.
        assert "Tiomos" in result.graph_entities
        assert "Soft-Close" in result.graph_entities

    def test_query_text_match_seeds_even_when_chunks_dont_intersect(self, small_graph):
        """Even with mismatched chunk IDs (the original failure mode),
        query-text matching still recovers entities.
        """
        store = _FakeStore(
            chunks=_FakeCollection(hits=[
                # ID intentionally doesn't match anything in the graph
                ("chunk_999", "Some hinge text ...",
                 {"source": "x.pdf", "page": 1}, 0.5),
            ]),
            communities=_FakeCollection(hits=[]),
        )
        result = graph_retrieve("Tell me about Tiomos and Grass products", small_graph, store)
        # Graph found 0 entities from chunk-membership, but query-text matched 2.
        assert "Tiomos" in result.graph_entities
        assert "Grass" in result.graph_entities

    def test_retrieval_includes_communities(self, small_graph):
        store = _FakeStore(
            chunks=_FakeCollection(hits=[]),
            communities=_FakeCollection(hits=[
                ("community_0", "Grass cabinet hinge systems",
                 {"community_id": 0, "size": 300}, 0.18),
                ("community_1", "Concealed hinges family",
                 {"community_id": 1, "size": 200}, 0.22),
            ]),
        )
        result = graph_retrieve("What hinges?", small_graph, store, n_communities=2)
        assert len(result.communities) == 2
        assert result.communities[0].id == "community_0"


# ---------------------------------------------------------------- vector retrieve

class TestVectorRetrieveChunks:
    def test_unpacks_chroma_shape(self, small_graph):
        coll = _FakeCollection(hits=[
            ("a", "alpha", {"source": "x", "page": 1}, 0.1),
            ("b", "beta",  {"source": "y", "page": 2}, 0.2),
        ])
        hits = vector_retrieve_chunks(coll, "q", n=5)
        assert [h.id for h in hits] == ["a", "b"]
        assert hits[0].distance == 0.1
        assert hits[1].metadata == {"source": "y", "page": 2}
