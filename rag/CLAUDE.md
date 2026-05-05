# CLAUDE.md — `rag/` Subproject Context for AI Assistants

This file scopes the **`rag/` subproject** of `window-project`. For repo-wide context (engine, demo, top-level conventions) read `../CLAUDE.md` first.

## Project

**`rag/`** — Catalogue RAG / GraphRAG prototype for `window-project`. Indexes the project's hardware product catalogs (`../catalogs/*.pdf`) into ChromaDB and answers queries using both standard vector search and GraphRAG (knowledge graph-enhanced retrieval). Supports multiple LLM providers (Anthropic Claude, Ollama local models).

Originally developed as the standalone repo `micro-x-rag` (`https://github.com/StephenDenisEdwards/micro-x-rag`); merged into this repo on 2026-05-05 so the deterministic constraint engine and the catalogue search layer live side by side. See [ADR-003](../documentation/docs/architecture/decisions/ADR-003-conversational-via-microx-mcp.md) for how this layer fits the broader architecture.

## Language & Layout

- **Python 3.14** (matching repo top-level); notebook-first workflow
- Package manager: `pip`
- Config: notebook Setup & Configuration cell (provider/model per operation)
- Secrets: `rag/.env` (never commit; root `.gitignore` covers it)
- PDFs read from `../catalogs/` (repo-root `catalogs/`, not a `rag/catalogs/` directory)

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run notebooks
jupyter notebook notebooks/rag_catalog_search.ipynb
jupyter notebook notebooks/graph_rag_catalog_search.ipynb

# Pull required Ollama models
ollama pull nomic-embed-text   # embeddings
ollama pull mistral:7b         # local chat (optional, if using ollama provider)
```

## Architecture Overview

```
PDF Catalogs
    │
    ├─────────────────────────────────────┐
    ▼                                     ▼
Extract text (PyMuPDF)              Embed chunks (nomic-embed-text)
    │                                     │
    ▼                                     ▼
Chunk text (800 chars, 100 overlap) Store in ChromaDB
    │                                     │
    ▼                                     │
Extract entities & relationships    ┌─────┘
(Claude API)                        │
    │                               │
    ▼                               │
Post-process (normalize,            │
deduplicate, filter)                │
    │                               │
    ▼                               │
Build knowledge graph (NetworkX)    │
    │                               │
    ▼                               │
Detect communities (Louvain)        │
    │                               │
    ▼                               │
Summarize communities (LLM)        │
    │                               │
    ▼                               │
Embed summaries in ChromaDB ────────┘
    │
    ▼
Query time: vector search + graph traversal + community summaries → LLM → Answer
```

## Key Files

| File | Purpose |
|------|---------|
| `notebooks/rag_catalog_search.ipynb` | Standard RAG pipeline |
| `notebooks/graph_rag_catalog_search.ipynb` | GraphRAG pipeline (main notebook) |
| `notebooks/graph_rag_catalog_search_executed.ipynb` | Executed GraphRAG with mistral:7b summaries |
| `notebooks/graph_rag_catalog_search_executed_2.ipynb` | Executed GraphRAG with Claude summaries |
| `../catalogs/*.pdf` | Source PDF product catalogs (repo-root, shared with engine) |
| `extractions.json` | Cached entity extraction results (gitignored, lives in `rag/`) |
| `knowledge_graph.html` | Interactive graph visualization (gitignored, lives in `rag/`) |
| `scripts/run_extraction.py` | Resumable extraction script (Claude API) |
| `.env` | API keys (gitignored) |

## Configuration

All model configuration is in the notebook's **first code cell** (Setup & Configuration). Each operation has its own provider and model:

```python
EXTRACTION_PROVIDER = "anthropic"          # "anthropic" or "ollama"
EXTRACTION_MODEL    = "claude-sonnet-4-20250514"

SUMMARY_PROVIDER    = "anthropic"
SUMMARY_MODEL       = "claude-sonnet-4-20250514"

ANSWER_PROVIDER     = "anthropic"
ANSWER_MODEL        = "claude-sonnet-4-20250514"

EMBED_PROVIDER      = "ollama"             # "ollama" or "anthropic"
EMBED_MODEL         = "nomic-embed-text"
```

Pipeline settings:

```python
MAX_PAGES_PER_PDF   = None      # None = all pages
FORCE_RE_EXTRACT    = False     # True = ignore cached extractions
CHUNK_SIZE          = 800
CHUNK_OVERLAP       = 100
```

## Conventions

### Commit Messages

Use conventional prefix style:

| Prefix | Use For |
|--------|---------|
| `feat:` | New features or capabilities |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes only |
| `refactor:` | Code restructuring without behaviour change |
| `chore:` | Build, tooling, dependency updates |
| `test:` | Adding or updating tests |

### Code Style

- Type hints on all public functions
- Docstrings on public classes and non-trivial functions
- No hardcoded model names — all config in the Setup & Configuration cell

### Documentation

- RAG-specific design docs and analysis in `rag/docs/` (this subtree)
- Engine-wide design docs in `../documentation/docs/`
- Keep `rag/README.md` up to date when adding notebooks or changing config
- Keep this `rag/CLAUDE.md` up to date when adding key files or changing RAG-specific conventions
- RAG-side architecture decisions recorded in `rag/docs/architecture/decisions/`; engine-wide ADRs live in `../documentation/docs/architecture/decisions/`

### Critical Rules

- Never commit `.env` or API keys
- Never commit ChromaDB directories or `extractions.json`
- All model references must use the configurable provider/model variables
- Extraction results are cached — set `FORCE_RE_EXTRACT = True` to re-run
