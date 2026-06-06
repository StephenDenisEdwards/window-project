"""List all chunks built from `catalogs/*.pdf` with their deterministic IDs.

Pure read-only: chunks PDFs in-process (PyMuPDF) — no Ollama, no API calls,
no ChromaDB. IDs match what `build_store` would key on, so this is the canonical
way to inspect the chunk inventory.

Usage:
    python -m rag.scripts.list_chunks
    python -m rag.scripts.list_chunks --preview          # show a text snippet per chunk
    python -m rag.scripts.list_chunks --source HAFELE     # only chunks whose source contains this
    python -m rag.scripts.list_chunks --max-pages 5       # cap pages per PDF
    python -m rag.scripts.list_chunks --json              # emit JSON instead of a table
"""
from __future__ import annotations

import argparse
import json
import sys

from rag.pipeline.config import load_config
from rag.pipeline.extract import build_chunks


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="List all chunks and their deterministic IDs.")
    p.add_argument("--source", default=None,
                   help="Only list chunks whose source filename contains this substring.")
    p.add_argument("--preview", action="store_true",
                   help="Show a one-line text snippet for each chunk.")
    p.add_argument("--preview-chars", type=int, default=70,
                   help="Snippet length when --preview is set (default: 70).")
    p.add_argument("--max-pages", type=int, default=None,
                   help="Cap pages per PDF (default: all pages).")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON instead of a human-readable table.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    # PDF text carries glyphs (°, ↑, …) the Windows cp1252 console can't encode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = load_config()

    if not cfg.catalog_dir.exists():
        print(f"error: catalogs directory {cfg.catalog_dir} not found.")
        return 2

    chunks = build_chunks(
        cfg.catalog_dir,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        max_pages_per_pdf=args.max_pages if args.max_pages is not None else cfg.max_pages_per_pdf,
    )

    if args.source:
        needle = args.source.lower()
        chunks = [c for c in chunks if needle in c.source.lower()]

    if not chunks:
        print(f"No chunks found in {cfg.catalog_dir}"
              + (f" matching source '{args.source}'." if args.source else "."))
        return 0

    if args.json:
        print(json.dumps([c.as_dict() for c in chunks], indent=2))
        return 0

    id_width = max(len(c.id) for c in chunks)
    for c in chunks:
        line = f"{c.id:<{id_width}}"
        if args.preview:
            snippet = " ".join(c.text.split())[: args.preview_chars]
            line += f"  | {snippet}"
        print(line)

    sources = sorted({c.source for c in chunks})
    print(f"\n{len(chunks)} chunks across {len(sources)} PDF(s): {', '.join(sources)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
