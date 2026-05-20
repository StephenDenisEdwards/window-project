"""Retrieval strategies: standard vector RAG and GraphRAG.

The GraphRAG pipeline composes four pure pieces (each independently testable):

  1. `vector_retrieve_chunks`     — vector hit list for the query
  2. `find_entities_in_chunks`    — graph nodes whose chunk_ids intersect those hits
  3. `find_entities_in_query`     — graph nodes whose name appears in the query
  4. `expand_via_hops`            — neighbourhood expansion of seed entities
  5. `render_graph_context`       — text block for the prompt
  6. `vector_retrieve_communities` — community-summary hit list

`graph_retrieve` is the orchestration that glues them together.

Pinning the bug from the original notebook: seeding entities was done ONLY
from chunk-membership. Because chunk IDs in the Chroma store didn't match
the chunk_ids stored on graph nodes, the intersection was always empty
("Graph entities found: 0"). Step 1 above is fixed by consistent IDs;
step 3 (`find_entities_in_query`) is added so query-string hits also seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import networkx as nx


@dataclass(slots=True)
class ChunkHit:
    id: str
    text: str
    metadata: dict
    distance: float


@dataclass(slots=True)
class CommunityHit:
    id: str
    summary: str
    metadata: dict
    distance: float


@dataclass(slots=True)
class Retrieval:
    chunks: list[ChunkHit] = field(default_factory=list)
    graph_entities: list[str] = field(default_factory=list)
    graph_context: str = ""
    communities: list[CommunityHit] = field(default_factory=list)


class _Queryable(Protocol):
    """Minimal protocol for a Chroma collection (or test stub)."""

    def query(self, *, query_texts: list[str], n_results: int) -> dict: ...


# === Pure pieces ====================================================

def find_entities_in_chunks(G: nx.Graph, chunk_ids: set[str]) -> set[str]:
    """Graph nodes whose `chunk_ids` attribute intersects `chunk_ids`."""
    if not chunk_ids:
        return set()
    hits: set[str] = set()
    for node, data in G.nodes(data=True):
        if data.get("chunk_ids", set()) & chunk_ids:
            hits.add(node)
    return hits


def find_entities_in_query(
    G: nx.Graph,
    query: str,
    *,
    min_name_chars: int = 4,
) -> set[str]:
    """Graph nodes whose normalised name appears as a substring of `query`.

    Names shorter than `min_name_chars` after normalisation are skipped
    (avoids matching on tokens like 'mm' or 'is').
    """
    q = query.lower()
    hits: set[str] = set()
    for node in G.nodes():
        norm = node.lower().replace("-", " ").replace("_", " ").strip()
        if len(norm) >= min_name_chars and norm in q:
            hits.add(node)
    return hits


def expand_via_hops(G: nx.Graph, seeds: set[str], *, hop_depth: int = 1) -> set[str]:
    """BFS from `seeds` out to `hop_depth` hops. Includes the seeds themselves."""
    if not seeds:
        return set()
    visited = set(seeds)
    frontier = {s for s in seeds if G.has_node(s)}
    for _ in range(hop_depth):
        next_frontier: set[str] = set()
        for node in frontier:
            next_frontier.update(G.neighbors(node))
        next_frontier -= visited
        if not next_frontier:
            break
        visited |= next_frontier
        frontier = next_frontier
    return visited


def render_graph_context(
    G: nx.Graph,
    entities: set[str],
    *,
    max_entities: int = 15,
    max_edges_per_entity: int = 5,
) -> str:
    """Format entities + their within-set edges as a text block for the prompt."""
    parts: list[str] = []
    ordered = sorted(entities, key=lambda n: G.nodes[n].get("mentions", 0), reverse=True)
    for entity in ordered[:max_entities]:
        if not G.has_node(entity):
            continue
        node_data = G.nodes[entity]
        edges: list[str] = []
        for _, neighbor, edge_data in G.edges(entity, data=True):
            if neighbor in entities:
                rels = ", ".join(edge_data.get("relations", set()))
                edges.append(f"{entity} --[{rels}]--> {neighbor}")
                if len(edges) >= max_edges_per_entity:
                    break
        if edges:
            parts.append(
                f"{entity} ({node_data.get('type', '?')}, "
                f"{node_data.get('mentions', 0)} mentions):\n"
                + "\n".join(f"  {e}" for e in edges)
            )
    return "\n\n".join(parts)


# === Vector hits ====================================================

def vector_retrieve_chunks(collection: _Queryable, query: str, n: int = 5) -> list[ChunkHit]:
    res = collection.query(query_texts=[query], n_results=n)
    return [
        ChunkHit(
            id=res["ids"][0][i],
            text=res["documents"][0][i],
            metadata=res["metadatas"][0][i],
            distance=res["distances"][0][i],
        )
        for i in range(len(res["ids"][0]))
    ]


def vector_retrieve_communities(collection: _Queryable, query: str, n: int = 2) -> list[CommunityHit]:
    res = collection.query(query_texts=[query], n_results=n)
    return [
        CommunityHit(
            id=res["ids"][0][i],
            summary=res["documents"][0][i],
            metadata=res["metadatas"][0][i],
            distance=res["distances"][0][i],
        )
        for i in range(len(res["ids"][0]))
    ]


# === Orchestration ====================================================

def graph_retrieve(
    query: str,
    G: nx.Graph,
    store,  # rag.pipeline.store.Store; runtime duck-typed to avoid cyclical import
    *,
    n_chunks: int = 5,
    n_communities: int = 2,
    hop_depth: int = 1,
    max_graph_entities: int = 15,
) -> Retrieval:
    """Full GraphRAG retrieval: vector + entity-name match + graph traversal + communities."""
    chunks = vector_retrieve_chunks(store.chunks, query, n=n_chunks)
    chunk_ids = {c.id for c in chunks}

    seeds = find_entities_in_chunks(G, chunk_ids) | find_entities_in_query(G, query)
    entities = expand_via_hops(G, seeds, hop_depth=hop_depth)
    graph_context = render_graph_context(G, entities, max_entities=max_graph_entities)

    communities = vector_retrieve_communities(store.communities, query, n=n_communities)

    ordered_entities = sorted(
        entities, key=lambda n: G.nodes[n].get("mentions", 0) if G.has_node(n) else 0, reverse=True
    )
    return Retrieval(
        chunks=chunks,
        graph_entities=ordered_entities,
        graph_context=graph_context,
        communities=communities,
    )


def standard_rag_retrieve(query: str, store, *, n: int = 5) -> list[ChunkHit]:
    """Vanilla vector retrieval — for the comparison baseline."""
    return vector_retrieve_chunks(store.chunks, query, n=n)
