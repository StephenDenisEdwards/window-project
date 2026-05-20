# Notebooks

Four notebooks live in this directory. They share the same source PDFs (`../../catalogs/*.pdf`) but differ in pipeline, intended role, and which LLM was used for community summaries.

## Overview

| Notebook | Role | Pipeline | Summary LLM |
|---|---|---|---|
| `rag_catalog_search.ipynb` | **Baseline** | Vector RAG only (PDF → chunks → embeddings → ChromaDB → retrieve top-k → LLM answer) | n/a — no community summaries |
| `graph_rag_catalog_search.ipynb` | **GraphRAG source/template** (unexecuted) | Vector + knowledge graph (NetworkX) + Louvain communities + community summaries + graph traversal at query time | configurable (Anthropic or Ollama) |
| `graph_rag_catalog_search_executed_mistral.ipynb` | **Run snapshot** of the GraphRAG template | Same as above | **Ollama `mistral:7b`** (local) |
| `graph_rag_catalog_search_executed_claude.ipynb` | **Run snapshot** of the GraphRAG template | Same as above | **Anthropic `claude-sonnet-4-20250514`** (cloud) |

## How they relate

- `rag_catalog_search.ipynb` is the comparison baseline — no graph, no communities, pure vector similarity.
- `graph_rag_catalog_search.ipynb` is the *editable* GraphRAG implementation. If you want to change pipeline behaviour, edit this one.
- `graph_rag_catalog_search_executed_mistral.ipynb` and `graph_rag_catalog_search_executed_claude.ipynb` are **the same notebook as `graph_rag_catalog_search.ipynb`** but with all cells already executed and outputs persisted, plus the `SUMMARY_MODEL` config differs. They exist so you can A/B compare summarisation quality between a small local model and Claude without rerunning anything.

## When to open which

- **Try GraphRAG interactively** → `graph_rag_catalog_search.ipynb`.
- **See what GraphRAG produced** without spending compute or API credits → `graph_rag_catalog_search_executed_mistral.ipynb` or `graph_rag_catalog_search_executed_claude.ipynb` (outputs are already there).
- **Compare GraphRAG vs plain RAG** for the same query → run `rag_catalog_search.ipynb` and `graph_rag_catalog_search.ipynb` side by side. The latter has a "Compare: Standard RAG vs GraphRAG" section.
- **See how summary-LLM choice affects answers** → diff `graph_rag_catalog_search_executed_mistral.ipynb` vs `graph_rag_catalog_search_executed_claude.ipynb`.

## File-on-disk dependencies (relative to `rag/`)

- `rag_catalog_search.ipynb` reads `../catalogs/*.pdf`, writes `chroma_db/` (collection name `hardware_catalogs`).
- The three GraphRAG notebooks read `../catalogs/*.pdf` and share `extractions.json`, `chroma_db_graph/` (collections `graph_rag_chunks` + `graph_rag_communities`), and `knowledge_graph.html`.

All of these runtime artifacts are gitignored — they are rebuilt by running the notebooks.

## Running

The Jupyter kernel's working directory must be this `notebooks/` directory for the relative paths above to resolve. The repo's `.vscode/settings.json` sets `"jupyter.notebookFileRoot": "${fileDirname}"` so a freshly started kernel under VS Code lands here automatically; if you change that setting you must reload the VS Code window before it takes effect.

Required services for a full GraphRAG run:

- **Ollama** on `http://localhost:11434` with `nomic-embed-text` pulled (used for all embeddings).
- **Anthropic API key** in `../.env` as `ANTHROPIC_API_KEY` (used wherever a provider is set to `anthropic`).
