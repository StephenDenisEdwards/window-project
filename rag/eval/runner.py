"""Eval orchestrator.

Builds the graph + opens the store, runs each query case through each
configured retriever, computes metrics, and returns/persists structured
results.

Two modes:
  - `retrieval_only=True` (default for quick checks) — no LLM calls.
  - `retrieval_only=False` — also calls the configured answer LLM and
    scores `must_mention_coverage`.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import networkx as nx

from rag.eval import metrics
from rag.eval.queries import QUERIES, QueryCase
from rag.pipeline.answer import build_graph_rag_prompt, build_standard_rag_prompt
from rag.pipeline.config import RagConfig
from rag.pipeline.llm import llm_chat
from rag.pipeline.retrieve import (
    Retrieval,
    graph_retrieve,
    standard_rag_retrieve,
)
from rag.pipeline.store import Store


@dataclass(slots=True)
class RunResult:
    query_id: str
    config: str  # "vector_only" | "graph_rag"
    pages_retrieved: list[tuple[str, int]]
    n_chunks: int
    n_graph_entities: int  # 0 for vector_only
    graph_entities_sample: list[str]
    answer: str | None
    metrics: dict[str, float] = field(default_factory=dict)


def _pages_from_chunks(chunks) -> list[tuple[str, int]]:
    return [(c.metadata.get("source", "?"), int(c.metadata.get("page", -1))) for c in chunks]


def evaluate_query_graph_rag(
    case: QueryCase,
    G: nx.Graph,
    store: Store,
    cfg: RagConfig,
    *,
    retrieval_only: bool,
    n_chunks: int = 5,
    n_communities: int = 2,
    hop_depth: int = 1,
) -> RunResult:
    retrieval: Retrieval = graph_retrieve(
        case.query, G, store,
        n_chunks=n_chunks, n_communities=n_communities, hop_depth=hop_depth,
    )
    answer: str | None = None
    if not retrieval_only:
        prompt = build_graph_rag_prompt(case.query, retrieval)
        answer = llm_chat(
            prompt, provider=cfg.answer_provider, model=cfg.answer_model,
            temperature=0.3, max_tokens=1024,
        )

    pages = _pages_from_chunks(retrieval.chunks)
    m = metrics.score(
        retrieved_pages=pages,
        expected_pages=case.expected_pages,
        retrieved_entities=retrieval.graph_entities,
        expected_entities=case.must_have_entities,
        answer=answer,
        must_mention=case.must_mention if answer else None,
    )
    return RunResult(
        query_id=case.id,
        config="graph_rag",
        pages_retrieved=pages,
        n_chunks=len(retrieval.chunks),
        n_graph_entities=len(retrieval.graph_entities),
        graph_entities_sample=retrieval.graph_entities[:10],
        answer=answer,
        metrics=m,
    )


def evaluate_query_vector_only(
    case: QueryCase,
    store: Store,
    cfg: RagConfig,
    *,
    retrieval_only: bool,
    n_chunks: int = 5,
) -> RunResult:
    chunks = standard_rag_retrieve(case.query, store, n=n_chunks)
    answer: str | None = None
    if not retrieval_only:
        prompt = build_standard_rag_prompt(case.query, chunks)
        answer = llm_chat(
            prompt, provider=cfg.answer_provider, model=cfg.answer_model,
            temperature=0.3, max_tokens=1024,
        )

    pages = _pages_from_chunks(chunks)
    m = metrics.score(
        retrieved_pages=pages,
        expected_pages=case.expected_pages,
        answer=answer,
        must_mention=case.must_mention if answer else None,
    )
    return RunResult(
        query_id=case.id,
        config="vector_only",
        pages_retrieved=pages,
        n_chunks=len(chunks),
        n_graph_entities=0,
        graph_entities_sample=[],
        answer=answer,
        metrics=m,
    )


def run_eval(
    G: nx.Graph,
    store: Store,
    cfg: RagConfig,
    *,
    configs: list[str] | None = None,
    cases: list[QueryCase] | None = None,
    retrieval_only: bool = True,
    verbose: bool = True,
) -> list[RunResult]:
    if configs is None:
        configs = ["vector_only", "graph_rag"]
    if cases is None:
        cases = QUERIES

    results: list[RunResult] = []
    for case in cases:
        if verbose:
            print(f"\n=== {case.id}: {case.query!r} ===")
        if "vector_only" in configs:
            r = evaluate_query_vector_only(case, store, cfg, retrieval_only=retrieval_only)
            results.append(r)
            if verbose:
                _print_result(r)
        if "graph_rag" in configs:
            r = evaluate_query_graph_rag(case, G, store, cfg, retrieval_only=retrieval_only)
            results.append(r)
            if verbose:
                _print_result(r)
    return results


def _print_result(r: RunResult) -> None:
    parts = [f"  [{r.config:12s}] chunks={r.n_chunks}"]
    if r.n_graph_entities:
        parts.append(f"entities={r.n_graph_entities}")
    parts.append(", ".join(f"{k}={v:.2f}" for k, v in r.metrics.items()))
    print(" ".join(parts))


def write_results(results: list[RunResult], out_dir: Path) -> Path:
    """Persist results to a timestamped JSON file under `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"eval_{stamp}.json"
    out_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2, default=str),
        encoding="utf-8",
    )
    return out_path
