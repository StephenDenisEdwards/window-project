"""Build the knowledge graph + community partition + interactive viz.

Usage:
    python -m rag.scripts.build_graph

Reads cached `extractions.json`, applies `clean()` (type normalisation,
dedupe with numeric-mismatch guard, noise filter), constructs the
NetworkX graph, runs Louvain community detection, writes the pyvis
HTML visualisation, and prints stats.

Pure compute step — no LLM or network calls.
"""
from __future__ import annotations

import json
import sys

from rag.pipeline.communities import detect_communities
from rag.pipeline.config import load_config
from rag.pipeline.graph import build_graph, print_graph_stats
from rag.pipeline.normalize import clean
from rag.pipeline.viz import write_interactive_html


def main() -> int:
    cfg = load_config()

    if not cfg.extractions_path.exists():
        print(
            f"error: {cfg.extractions_path} missing — run "
            "`python -m rag.scripts.run_extraction` first."
        )
        return 2

    print(f"Loading {cfg.extractions_path}...")
    extractions = json.loads(cfg.extractions_path.read_text(encoding="utf-8"))
    print(f"  {len(extractions)} chunks before clean")
    clean(extractions)
    total_e = sum(len(e.get("entities", [])) for e in extractions)
    total_r = sum(len(e.get("relationships", [])) for e in extractions)
    print(f"  after clean: {total_e} entities, {total_r} relationships")

    print("\nBuilding graph...")
    G = build_graph(extractions)
    print_graph_stats(G)

    print("\nDetecting communities (Louvain)...")
    communities = detect_communities(G, seed=42)
    print(f"  {len(communities)} communities")
    top = sorted(communities, key=len, reverse=True)[:5]
    for i, members in enumerate(top):
        head = sorted(members, key=lambda n: G.nodes[n].get("mentions", 0), reverse=True)[:6]
        tail = "..." if len(members) > 6 else ""
        print(f"  #{i}: {len(members)} entities - " + ", ".join(head) + tail)

    viz_path = cfg.graph_persist_path.parent / "knowledge_graph.html"
    print(f"\nWriting viz to {viz_path}...")
    write_interactive_html(G, viz_path, min_mentions=3)

    return 0


if __name__ == "__main__":
    sys.exit(main())
