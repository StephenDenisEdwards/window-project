"""Prompt assembly + final LLM call.

`build_*_prompt` functions are pure (testable without network).
`*_answer` functions glue retrieval + prompt + `llm_chat` together.
"""
from __future__ import annotations

import networkx as nx

from rag.pipeline.llm import llm_chat
from rag.pipeline.retrieve import (
    ChunkHit,
    Retrieval,
    graph_retrieve,
    standard_rag_retrieve,
)

GRAPH_RAG_SYSTEM = """You are a knowledgeable hardware product specialist. Answer the user's question
using ALL the provided context. You have three sources of information:

1. CATALOG TEXT — direct excerpts from product catalogs
2. KNOWLEDGE GRAPH — extracted entity relationships showing how products, features, and specs connect
3. THEMATIC SUMMARIES — high-level summaries of product clusters

Use all three to give a comprehensive answer. Cite source catalogs and page numbers when possible.
If the context doesn't contain enough information, say so clearly."""

STANDARD_RAG_SYSTEM = """You are a knowledgeable hardware product specialist. Answer the user's question
based ONLY on the provided catalog context. If the context doesn't contain enough
information to fully answer the question, say so clearly.

When referencing specific products or specifications, cite the source catalog and page number."""


def _format_chunks(chunks: list[ChunkHit]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        src = c.metadata.get("source", "?")
        page = c.metadata.get("page", "?")
        parts.append(f"[Source {i}: {src}, Page {page}]\n{c.text}")
    return "\n\n---\n\n".join(parts)


def build_graph_rag_prompt(query: str, retrieval: Retrieval) -> str:
    chunk_context = _format_chunks(retrieval.chunks)
    graph_context = retrieval.graph_context or "No graph relationships found."
    community_context = "\n".join(f"- {c.summary}" for c in retrieval.communities) \
        or "No community summaries available."

    return f"""{GRAPH_RAG_SYSTEM}

=== CATALOG TEXT ===
{chunk_context}

=== KNOWLEDGE GRAPH (entity relationships) ===
{graph_context}

=== THEMATIC SUMMARIES ===
{community_context}

USER QUESTION: {query}

ANSWER:"""


def build_standard_rag_prompt(query: str, chunks: list[ChunkHit]) -> str:
    context = _format_chunks(chunks)
    return f"""{STANDARD_RAG_SYSTEM}

CONTEXT FROM PRODUCT CATALOGS:
{context}

USER QUESTION: {query}

ANSWER:"""


def graph_rag_answer(
    query: str,
    G: nx.Graph,
    store,
    *,
    provider: str,
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    n_chunks: int = 5,
    n_communities: int = 2,
    hop_depth: int = 1,
) -> tuple[str, Retrieval]:
    """Full GraphRAG: retrieve, prompt, call LLM. Returns (answer, retrieval) so
    callers can inspect which sources were used.
    """
    retrieval = graph_retrieve(
        query, G, store,
        n_chunks=n_chunks, n_communities=n_communities, hop_depth=hop_depth,
    )
    prompt = build_graph_rag_prompt(query, retrieval)
    answer = llm_chat(prompt, provider=provider, model=model, temperature=temperature, max_tokens=max_tokens)
    return answer, retrieval


def standard_rag_answer(
    query: str,
    store,
    *,
    provider: str,
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    n: int = 5,
) -> tuple[str, list[ChunkHit]]:
    """Vanilla vector RAG baseline. Returns (answer, chunks_used)."""
    chunks = standard_rag_retrieve(query, store, n=n)
    prompt = build_standard_rag_prompt(query, chunks)
    answer = llm_chat(prompt, provider=provider, model=model, temperature=temperature, max_tokens=max_tokens)
    return answer, chunks
