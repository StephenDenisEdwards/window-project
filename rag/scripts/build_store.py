"""Rebuild the ChromaDB store: chunks + community summaries.

Usage:
    python -m rag.scripts.build_store
    python -m rag.scripts.build_store --top-n 20      # summarise more communities
    python -m rag.scripts.build_store --no-summaries  # skip the LLM summary step

End-to-end:
    1. Load + clean cached `extractions.json`.
    2. Build the graph and detect communities.
    3. Build chunks from `catalogs/*.pdf`.
    4. (Unless --no-summaries) Summarise top-N communities via the configured LLM.
    5. Wipe and rebuild both Chroma collections via the Ollama embedder.

Requires Ollama running on `cfg.ollama_base_url` with the configured embed
model pulled. Step 4 also makes paid API calls for community summaries.
"""
from __future__ import annotations

import argparse
import json
import sys

import httpx

from rag.pipeline.communities import detect_communities, summarize_top_communities
from rag.pipeline.config import load_config
from rag.pipeline.extract import build_chunks
from rag.pipeline.graph import build_graph
from rag.pipeline.normalize import clean
from rag.pipeline.store import build_store


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rebuild the ChromaDB store (chunks + summaries).")
    p.add_argument("--top-n", type=int, default=10,
                   help="How many largest communities to summarise (default: 10).")
    p.add_argument("--no-summaries", action="store_true",
                   help="Skip community summarisation — useful for fast chunks-only rebuild.")
    return p.parse_args(argv)


def _check_ollama(base_url: str) -> bool:
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"error: Ollama unreachable at {base_url} — {type(e).__name__}: {e}")
        return False


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    cfg = load_config()

    if not cfg.extractions_path.exists():
        print(f"error: {cfg.extractions_path} missing — run "
              "`python -m rag.scripts.run_extraction` first.")
        return 2
    if not cfg.catalog_dir.exists():
        print(f"error: catalogs directory {cfg.catalog_dir} not found.")
        return 2
    if not _check_ollama(cfg.ollama_base_url):
        print("       Start Ollama and pull the embed model, e.g.:")
        print(f"           ollama pull {cfg.embed_model}")
        return 2

    print(f"Loading {cfg.extractions_path}...")
    extractions = json.loads(cfg.extractions_path.read_text(encoding="utf-8"))
    clean(extractions)

    print("Building graph...")
    G = build_graph(extractions)
    print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    print("Detecting communities...")
    communities = detect_communities(G, seed=42)
    print(f"  {len(communities)} communities")

    print(f"Building chunks from {cfg.catalog_dir}...")
    chunks = build_chunks(
        cfg.catalog_dir,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        max_pages_per_pdf=cfg.max_pages_per_pdf,
    )
    print(f"  {len(chunks)} chunks")

    if args.no_summaries:
        print("Skipping community summarisation (--no-summaries).")
        summaries: dict[int, dict] = {}
    else:
        print(f"Summarising top {args.top_n} communities "
              f"({cfg.summary_provider} / {cfg.summary_model})...")
        summaries = summarize_top_communities(
            communities, G,
            provider=cfg.summary_provider, model=cfg.summary_model,
            top_n=args.top_n, verbose=False,
        )
        print(f"  {len(summaries)} summaries generated")

    print(f"\nBuilding store at {cfg.chroma_persist_dir}...")
    store = build_store(
        chunks, summaries,
        persist_dir=cfg.chroma_persist_dir,
        embed_model=cfg.embed_model,
        ollama_base_url=cfg.ollama_base_url,
        verbose=True,
    )

    print(f"\nDone. {store.chunks.count()} chunks, {store.communities.count()} community summaries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
