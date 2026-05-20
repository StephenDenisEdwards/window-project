"""Command-line entry point for the eval.

Usage:
    python -m rag.eval                          # retrieval-only across both configs
    python -m rag.eval --with-llm               # include LLM answer + must_mention scoring
    python -m rag.eval --configs graph_rag      # subset of configs
    python -m rag.eval --query soft-close-tiomos    # subset of queries by id
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from rag.eval import metrics as metrics_module
from rag.eval.queries import QUERIES
from rag.eval.runner import run_eval, write_results
from rag.pipeline.config import load_config
from rag.pipeline.graph import build_graph
from rag.pipeline.normalize import clean
from rag.pipeline.store import open_store


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the RAG eval harness.")
    p.add_argument(
        "--configs", nargs="+", default=["vector_only", "graph_rag"],
        choices=["vector_only", "graph_rag"],
        help="Which retriever configs to evaluate (default: both).",
    )
    p.add_argument(
        "--query", action="append", default=None, dest="query_ids",
        help="Restrict to one or more query IDs (can be passed multiple times).",
    )
    p.add_argument(
        "--with-llm", action="store_true",
        help="Also call the answer LLM and score must_mention_coverage. "
             "Default is retrieval-only (no API cost).",
    )
    p.add_argument(
        "--out-dir", default="rag/eval/results", type=Path,
        help="Where to write the timestamped JSON results.",
    )
    p.add_argument(
        "--summary-only", action="store_true",
        help="Print the per-config aggregate at the end and exit; don't write JSON.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    cfg = load_config()

    if not cfg.extractions_path.exists():
        print(f"error: {cfg.extractions_path} missing — run `python -m rag.scripts.run_extraction` first.")
        return 2
    if not cfg.chroma_persist_dir.exists():
        print(f"error: {cfg.chroma_persist_dir} missing — build the store first.")
        return 2

    print("Loading extractions, building graph, opening store...")
    extractions = json.loads(cfg.extractions_path.read_text(encoding="utf-8"))
    clean(extractions)
    G = build_graph(extractions)
    store = open_store(cfg.chroma_persist_dir, embed_model=cfg.embed_model,
                       ollama_base_url=cfg.ollama_base_url)
    print(f"  graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"  store: {store.chunks.count()} chunks, {store.communities.count()} summaries")

    cases = QUERIES
    if args.query_ids:
        wanted = set(args.query_ids)
        cases = [c for c in QUERIES if c.id in wanted]
        missing = wanted - {c.id for c in QUERIES}
        if missing:
            print(f"error: unknown query IDs: {sorted(missing)}")
            return 2

    results = run_eval(
        G, store, cfg,
        configs=args.configs,
        cases=cases,
        retrieval_only=not args.with_llm,
        verbose=True,
    )

    _print_summary(results)

    if not args.summary_only:
        out_path = write_results(results, args.out_dir)
        print(f"\nResults written to {out_path}")

    return 0


def _print_summary(results: list[dict]) -> None:
    """Aggregate per-config metric means across all queries."""
    from collections import defaultdict
    sums: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        for k, v in r.metrics.items():
            sums[r.config][k] += v
            counts[r.config][k] += 1

    print("\n=== Summary (mean across queries) ===")
    for config in sorted(sums):
        items = ", ".join(f"{k}={sums[config][k] / counts[config][k]:.2f}" for k in sums[config])
        print(f"  {config:12s}  {items}")


if __name__ == "__main__":
    sys.exit(main())
