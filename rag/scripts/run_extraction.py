"""Run or resume entity extraction over all catalogue PDFs.

Usage:
    python -m rag.scripts.run_extraction              # Resume from cache
    python -m rag.scripts.run_extraction --force      # Re-extract from scratch

Thin wrapper: delegates to `rag.pipeline.entities.extract_all`.
"""
from __future__ import annotations

import sys

from rag.pipeline.config import load_config
from rag.pipeline.entities import extract_all
from rag.pipeline.extract import build_chunks


def main() -> None:
    force = "--force" in sys.argv
    cfg = load_config()

    print("Building chunks from PDFs...")
    chunks = build_chunks(
        cfg.catalog_dir,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        max_pages_per_pdf=cfg.max_pages_per_pdf,
    )
    print(f"Total chunks: {len(chunks)}")

    extract_all(
        chunks,
        cache_path=cfg.extractions_path,
        provider=cfg.extraction_provider,
        model=cfg.extraction_model,
        force=force,
    )


if __name__ == "__main__":
    main()
