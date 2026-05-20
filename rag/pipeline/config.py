"""RAG pipeline configuration — single source of truth for providers, models, paths, and runtime knobs.

Replaces the Setup & Configuration cells in the notebooks.
Paths are anchored to the `rag/` package directory so they resolve correctly
regardless of the caller's current working directory.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_RAG_ROOT = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class RagConfig:
    extraction_provider: str = "anthropic"
    extraction_model: str = "claude-sonnet-4-20250514"
    summary_provider: str = "anthropic"
    summary_model: str = "claude-sonnet-4-20250514"
    answer_provider: str = "anthropic"
    answer_model: str = "claude-sonnet-4-20250514"
    embed_model: str = "nomic-embed-text"

    max_pages_per_pdf: int | None = None
    force_re_extract: bool = False
    chunk_size: int = 800
    chunk_overlap: int = 100

    catalog_dir: Path = field(default_factory=lambda: (_RAG_ROOT.parent / "catalogs").resolve())
    chroma_persist_dir: Path = field(default_factory=lambda: _RAG_ROOT / "chroma_db_graph")
    graph_persist_path: Path = field(default_factory=lambda: _RAG_ROOT / "knowledge_graph.json")
    extractions_path: Path = field(default_factory=lambda: _RAG_ROOT / "extractions.json")

    ollama_base_url: str = "http://localhost:11434"


def load_config(env_path: Path | None = None) -> RagConfig:
    """Load environment from `.env` and return a `RagConfig`.

    `env_path` defaults to `rag/.env`. The lookup is cwd-independent.
    """
    if env_path is None:
        env_path = _RAG_ROOT / ".env"
    load_dotenv(env_path)
    return RagConfig()


def have_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
