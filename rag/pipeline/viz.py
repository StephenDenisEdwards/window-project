"""Interactive HTML visualisation of the knowledge graph via pyvis."""
from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

# Community colours; community_id % len(COLORS) picks one.
DEFAULT_COLORS = (
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#dcbeff", "#9A6324", "#800000", "#aaffc3", "#808000",
)


def write_interactive_html(
    G: nx.Graph,
    out_path: Path,
    *,
    min_mentions: int = 3,
    height: str = "700px",
    width: str = "100%",
    colors: tuple[str, ...] = DEFAULT_COLORS,
    verbose: bool = True,
) -> Path:
    """Render a pyvis HTML visualisation of `G`, filtered to entities with at
    least `min_mentions` mentions. Writes to `out_path` (UTF-8) and returns it.

    Nodes are coloured by their `community` attribute (set by
    `communities.detect_communities`). Sized by mention count.
    """
    notable = [n for n, d in G.nodes(data=True) if d.get("mentions", 0) >= min_mentions]
    sub = G.subgraph(notable)
    if verbose:
        print(f"Visualizing subgraph: {sub.number_of_nodes()} nodes, {sub.number_of_edges()} edges")
        print(f"(Entities with >= {min_mentions} mentions)")

    net = Network(height=height, width=width, notebook=True, cdn_resources="in_line")
    net.barnes_hut(gravity=-5000, spring_length=200)

    for node in sub.nodes():
        data = G.nodes[node]
        community_id = data.get("community", 0)
        color = colors[community_id % len(colors)]
        size = min(10 + data.get("mentions", 1) * 3, 50)
        title = (
            f"{node}\nType: {data.get('type', '?')}\n"
            f"Mentions: {data.get('mentions', 0)}\nCommunity: {community_id}"
        )
        net.add_node(node, label=node, color=color, size=size, title=title)

    for src, tgt, data in sub.edges(data=True):
        relations = ", ".join(data.get("relations", set()))
        net.add_edge(src, tgt, title=relations, width=min(data.get("weight", 1), 5))

    # Explicit UTF-8 to work around pyvis defaulting to cp1252 on Windows.
    net.generate_html()
    out_path.write_text(net.html, encoding="utf-8")
    if verbose:
        print(f"Graph saved to {out_path.resolve()}")
    return out_path
