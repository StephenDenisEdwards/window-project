"""Community detection + LLM summarisation over the knowledge graph.

Uses NetworkX's built-in Louvain implementation (`nx.community.louvain_communities`).
The summariser sends one prompt per community to whichever provider/model is configured.
"""
from __future__ import annotations

import networkx as nx

from rag.pipeline.llm import llm_chat

SUMMARY_PROMPT = """You are summarizing a cluster of related entities from hardware product catalogs.

Given the following entities and their relationships, write a concise summary (2-4 sentences)
describing what this group represents, the key products/features, and how they relate.

ENTITIES:
{entities}

RELATIONSHIPS:
{relationships}

SUMMARY:"""


def detect_communities(G: nx.Graph, *, seed: int = 42) -> list[set[str]]:
    """Run Louvain on `G`, tag each node with its `community` attribute, return communities.

    Returns a list of node-name sets, one per community. The list ordering
    matches the assigned `community` integer attribute on nodes.
    """
    communities = nx.community.louvain_communities(G, seed=seed)
    for community_id, community_nodes in enumerate(communities):
        for node in community_nodes:
            G.nodes[node]["community"] = community_id
    return communities


def summarize_community(
    community_nodes: set[str],
    G: nx.Graph,
    *,
    provider: str,
    model: str,
    max_entities: int = 20,
    max_relationships: int = 30,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    """Generate a natural-language summary for one community via the configured LLM."""
    sorted_nodes = sorted(
        community_nodes, key=lambda n: G.nodes[n].get("mentions", 0), reverse=True
    )[:max_entities]

    entity_strs = [
        f"- {n} (type: {G.nodes[n].get('type', '?')}, mentions: {G.nodes[n].get('mentions', 0)})"
        for n in sorted_nodes
    ]
    rel_strs = []
    for src, tgt, data in G.edges(data=True):
        if src in community_nodes and tgt in community_nodes:
            relations = ", ".join(data.get("relations", set()))
            rel_strs.append(f"- {src} --[{relations}]--> {tgt}")
            if len(rel_strs) >= max_relationships:
                break

    if not entity_strs:
        return "Empty community."

    prompt = SUMMARY_PROMPT.format(
        entities="\n".join(entity_strs),
        relationships="\n".join(rel_strs) or "No relationships found.",
    )
    return llm_chat(
        prompt,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def summarize_top_communities(
    communities: list[set[str]],
    G: nx.Graph,
    *,
    provider: str,
    model: str,
    top_n: int = 10,
    min_size: int = 3,
    top_entities_per_summary: int = 5,
    verbose: bool = True,
) -> dict[int, dict]:
    """Summarise the largest communities, skipping any below `min_size` members.

    Returns ``{community_id: {"summary": str, "size": int, "top_entities": list[str]}}``
    keyed by the same integer IDs assigned to nodes by `detect_communities`.
    """
    sorted_communities = sorted(
        enumerate(communities), key=lambda x: len(x[1]), reverse=True
    )

    summaries: dict[int, dict] = {}
    if verbose:
        print(f"Generating summaries for top {top_n} communities ({provider} / {model})...")

    for community_id, members in sorted_communities[:top_n]:
        if len(members) < min_size:
            continue
        summary = summarize_community(members, G, provider=provider, model=model)
        top_entities = sorted(
            members, key=lambda n: G.nodes[n].get("mentions", 0), reverse=True
        )[:top_entities_per_summary]
        summaries[community_id] = {
            "summary": summary,
            "size": len(members),
            "top_entities": top_entities,
        }
        if verbose:
            print(f"\nCommunity {community_id} ({len(members)} entities):")
            print(f"  Key entities: {', '.join(top_entities)}")
            print(f"  Summary: {summary}")

    return summaries
