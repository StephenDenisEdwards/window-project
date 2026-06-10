# `rag/` — Catalogue RAG / GraphRAG Prototype

The catalogue search layer of `window-project`. Indexes the project's hardware product catalogs into a ChromaDB vector database and answers natural language queries using both standard vector RAG and GraphRAG (knowledge graph-enhanced retrieval), with configurable model providers per pipeline operation.

> Originally the standalone repo `micro-x-rag`; merged into `window-project` on 2026-05-05. See [ADR-003: Conversational via Micro-X MCP](../documentation/docs/architecture/decisions/ADR-003-conversational-via-microx-mcp.md) for how this layer relates to the deterministic constraint engine.

## What You Can Do

- Ask natural language questions about hardware product catalogs
- Find compatible products across multiple catalogs
- Get thematic overviews of product categories and their relationships
- Compare hinge systems, mounting plates, and accessories across manufacturers
- Explore a knowledge graph of extracted entities and relationships

## Key Features

- **Standard RAG** — vector search over chunked catalog text
- **GraphRAG** — knowledge graph-enhanced retrieval with community summaries
- **Configurable providers** — each operation (extraction, summaries, answers, embeddings) has its own provider and model setting
- **Multi-provider support** — Anthropic Claude (cloud) and Ollama (local) for chat; Ollama and Voyage AI for embeddings
- **Extraction caching** — entity extraction results saved to disk, avoiding repeated API calls
- **Interactive visualization** — knowledge graph rendered as an interactive HTML page

## Notebooks

### 1. Standard RAG — `rag_catalog_search.ipynb`

Classic vector-search RAG pipeline:

1. **Extract** text from PDF catalogs using PyMuPDF
2. **Chunk** pages into overlapping segments with sentence-boundary awareness
3. **Embed** chunks locally with Ollama `nomic-embed-text`
4. **Store** embeddings and metadata in ChromaDB
5. **Retrieve** the most relevant catalog sections via semantic search
6. **Generate** answers with source citations using Claude or Ollama

### 2. GraphRAG — `graph_rag_catalog_search.ipynb`

Knowledge graph-enhanced RAG that goes beyond simple vector search:

1. **Extract entities & relationships** from chunks using an LLM
2. **Build a knowledge graph** with NetworkX (products, specs, features, and their connections)
3. **Detect communities** using the Louvain algorithm for thematic clustering
4. **Generate community summaries** for high-level understanding
5. **Retrieve via graph traversal + vector search + community summaries** for richer context
6. **Compare** Standard RAG vs GraphRAG on different query types

| Query Type | Standard RAG | GraphRAG |
|-----------|-------------|----------|
| Specific fact lookup | Good | Good |
| Multi-hop reasoning | Weak | Strong |
| Global/thematic questions | Weak | Strong |
| Cross-document synthesis | Weak | Strong |

## Prerequisites

- **Python 3.11+**
- **Ollama** running locally ([ollama.com](https://ollama.com))
- **Anthropic API key** (set in `.env`)

### Ollama Models

```bash
ollama pull nomic-embed-text   # embeddings (required)
```

## Setup

The RAG layer shares the repo's root `requirements.txt` and the root `catalogs/` PDFs. From the repo root:

```bash
cp rag/.env.example rag/.env   # Add your API keys
pip install -r requirements.txt
```

Then launch the notebooks from `rag/notebooks/` (see Usage below).

## Configuration

All model configuration is in the GraphRAG notebook's **first code cell** (Setup & Configuration). Each operation has its own provider (`"anthropic"` or `"ollama"`) and model:

| Operation | Provider | Model | Purpose |
|-----------|----------|-------|---------|
| Extraction | `anthropic` | `claude-sonnet-4-20250514` | Entity & relationship extraction |
| Summaries | `anthropic` | `claude-sonnet-4-20250514` | Community summary generation |
| Answers | `anthropic` | `claude-sonnet-4-20250514` | Final answer generation |
| Embeddings | `ollama` | `nomic-embed-text` | Vector embeddings |

To use a different model for any operation, change its provider and model in the config cell. For example, to use a local model for summaries:

```python
SUMMARY_PROVIDER = "ollama"
SUMMARY_MODEL    = "mistral:7b"
```

Pipeline settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_PAGES_PER_PDF` | `None` (all) | Limit pages per PDF for faster runs |
| `FORCE_RE_EXTRACT` | `False` | Set `True` to re-run extraction (ignores cache) |
| `CHUNK_SIZE` | `800` | Characters per text chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |

## Usage

From the repo root:

```bash
jupyter notebook rag/notebooks/rag_catalog_search.ipynb
jupyter notebook rag/notebooks/graph_rag_catalog_search.ipynb
```

**Standard RAG** — run cells in order. First run takes a few minutes for PDF ingestion.

**GraphRAG** — run cells in order. Entity extraction is cached to `extractions.json`. To re-run community summaries with a different model without re-extracting, just change `SUMMARY_PROVIDER` / `SUMMARY_MODEL` and re-run from the top with `FORCE_RE_EXTRACT = False`.

## Project Structure

```
window-project/
├── catalogs/                               # Source PDF product catalogs (shared)
├── requirements.txt                        # Python dependencies (shared)
└── rag/                                    # ← this subproject
    ├── notebooks/                          # Jupyter notebooks (main workflow)
    │   ├── rag_catalog_search.ipynb        # Standard RAG
    │   ├── graph_rag_catalog_search.ipynb  # GraphRAG (main notebook)
    │   ├── graph_rag_catalog_search_executed_mistral.ipynb  # Executed with mistral:7b summaries
    │   └── graph_rag_catalog_search_executed_claude.ipynb   # Executed with Claude summaries
    ├── scripts/                            # Standalone utility scripts
    │   └── run_extraction.py               # Resumable entity extraction (Claude API)
    ├── docs/                               # RAG-specific docs (engine-wide docs in ../documentation/)
    │   ├── architecture/decisions/         # RAG-side ADRs
    │   ├── design/                         # Design notes, comparisons, analysis
    │   ├── guides/                         # Stubs / pointers to canonical guides
    │   └── planning/                       # Roadmaps and improvement plans
    ├── .env.example                        # Environment variable template (copy to rag/.env)
    ├── CLAUDE.md                           # AI assistant context for the rag/ subtree
    ├── CONTRIBUTING.md                     # RAG-specific contribution notes
    ├── CHANGELOG.md                        # Version history (inherited from micro-x-rag)
    └── README.md                           # This file
```

Generated artifacts (gitignored, all under `rag/`):
- `chroma_db/` / `chroma_db_graph/` — persisted vector stores
- `extractions.json` — cached LLM entity extractions
- `knowledge_graph.html` — interactive graph visualization

## Catalogs Included

| File | Description |
|------|-------------|
| `Wurth_Baer_Section_C.pdf` | Wurth Baer Section C — specialty hinges, lid supports |
| `wurth-baer-section-b-concealed-hinges.pdf` | Wurth Baer Section B — concealed hinges |
| `grass-tiomos-catalog.pdf` | Grass Tiomos hinge system |
| `grass-nexis-catalog.pdf` | Grass Nexis hinge system |
| `blum-tandem-plus-blumotion.pdf` | Blum TANDEM plus BLUMOTION concealed drawer runners |

## Documentation

| Document | Description |
|----------|-------------|
| [GraphRAG Notebook Guide](docs/design/graphrag-notebook-guide.md) | Step-by-step explanation of every notebook cell |
| [GraphRAG vs Standard RAG](docs/design/graphrag-vs-standard-rag.md) | Comparison with test results and model upgrade analysis |
| [Graph Analysis](docs/design/graph-rag-analysis.md) | Knowledge graph quality metrics and improvement tracking |
| [Improvement Roadmap](docs/planning/graphrag-improvement-roadmap.md) | Prioritized improvement plan |
| [Deterministic Compatibility](docs/design/deterministic-compatibility-integration.md) | Design for integrating a compatibility service |
| [Hybrid Long-Context](docs/design/hybrid-long-context-approach.md) | Combining long context with structured data layers |
| [ADR-001: Configurable Providers](docs/architecture/decisions/ADR-001-configurable-providers.md) | Provider/model per operation architecture decision |
