"""Knowledge graph construction from cleaned extractions.

Builds a NetworkX graph where:
  - Nodes are entities. Attributes:
      type            (majority-vote across mentions)
      mentions        (int count across chunks)
      sources         (set[str]   source PDFs)
      chunk_ids       (set[str]   chunks the entity appears in)
      type_votes      (dict[str, int]   running tally for `type`)
      community       (int, set later by `communities.detect_communities`)
  - Edges are relationships. Attributes:
      weight          (int co-occurrence count)
      relations       (set[str]   relation types observed)
"""
from __future__ import annotations

from typing import Any

import networkx as nx


def normalize_name(name: Any) -> str:
    """Trim and Title-Case an entity name; coerce non-str defensively."""
    if not isinstance(name, str):
        name = str(name) if name is not None else ""
    return name.strip().title()


def build_graph(extractions: list[dict], *, min_name_len: int = 2) -> nx.Graph:
    """Construct a `networkx.Graph` from a list of extraction dicts.

    Each extraction must have keys ``entities``, ``relationships``, ``source``,
    ``page``, ``chunk_id``. Entities and relationship endpoints shorter than
    ``min_name_len`` characters are skipped.
    """
    G: nx.Graph = nx.Graph()

    for extraction in extractions:
        source_file = extraction["source"]
        chunk_id = extraction["chunk_id"]

        for entity in extraction.get("entities", []):
            name = normalize_name(entity.get("name", ""))
            etype = entity.get("type", "unknown")
            if not name or len(name) < min_name_len:
                continue
            _add_or_bump_node(G, name, etype, source_file, chunk_id)

        for rel in extraction.get("relationships", []):
            src = normalize_name(rel.get("source", ""))
            tgt = normalize_name(rel.get("target", ""))
            relation = rel.get("relation", "has_feature")
            if not src or not tgt or len(src) < min_name_len or len(tgt) < min_name_len:
                continue

            for node_name in (src, tgt):
                if not G.has_node(node_name):
                    # Endpoint never appeared as a standalone entity — assume product.
                    _add_or_bump_node(G, node_name, "product", source_file, chunk_id)

            if G.has_edge(src, tgt):
                G.edges[src, tgt]["weight"] = G.edges[src, tgt].get("weight", 1) + 1
                G.edges[src, tgt]["relations"].add(relation)
            else:
                G.add_edge(src, tgt, weight=1, relations={relation})

    return G


def _add_or_bump_node(G: nx.Graph, name: str, etype: str, source: str, chunk_id: str) -> None:
    if G.has_node(name):
        node = G.nodes[name]
        node["mentions"] = node.get("mentions", 1) + 1
        node["sources"].add(source)
        node["chunk_ids"].add(chunk_id)
        node["type_votes"][etype] = node["type_votes"].get(etype, 0) + 1
        node["type"] = max(node["type_votes"], key=node["type_votes"].get)
    else:
        G.add_node(
            name,
            type=etype,
            mentions=1,
            sources={source},
            chunk_ids={chunk_id},
            type_votes={etype: 1},
        )


def graph_stats(G: nx.Graph) -> dict:
    """Return a structured summary of the graph for logging / reporting."""
    from collections import Counter

    type_dist: Counter[str] = Counter(d.get("type", "?") for _, d in G.nodes(data=True))
    rel_dist: Counter[str] = Counter()
    for _, _, data in G.edges(data=True):
        for r in data.get("relations", set()):
            rel_dist[r] += 1

    n = G.number_of_nodes()
    avg_degree = (sum(d for _, d in G.degree()) / n) if n else 0.0

    top_entities = sorted(
        G.nodes(data=True), key=lambda x: x[1].get("mentions", 0), reverse=True
    )[:15]

    return {
        "nodes": n,
        "edges": G.number_of_edges(),
        "connected_components": nx.number_connected_components(G),
        "average_degree": avg_degree,
        "density": nx.density(G),
        "entity_types": dict(type_dist.most_common()),
        "relationship_types": dict(rel_dist.most_common()),
        "top_entities": [
            {
                "name": name,
                "type": data.get("type", "?"),
                "mentions": data.get("mentions", 0),
                "sources": len(data.get("sources", set())),
            }
            for name, data in top_entities
        ],
    }


def print_graph_stats(G: nx.Graph) -> None:
    """Human-readable dump of `graph_stats(G)` — what the notebook prints."""
    stats = graph_stats(G)
    print("Knowledge Graph:")
    print(f"  Nodes (entities): {stats['nodes']}")
    print(f"  Edges (relationships): {stats['edges']}")
    print(f"  Connected components: {stats['connected_components']}")
    print(f"  Average degree: {stats['average_degree']:.1f}")
    print(f"  Density: {stats['density']:.4f}")
    print(f"\nEntity types: {stats['entity_types']}")
    print(f"Relationship types: {stats['relationship_types']}")
    print("\nTop 15 entities:")
    for e in stats["top_entities"]:
        print(f"  {e['name']} ({e['type']}): {e['mentions']} mentions, {e['sources']} sources")
