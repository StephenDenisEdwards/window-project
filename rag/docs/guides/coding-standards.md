# Coding Standards

The canonical coding standards for this repo live at [`documentation/docs/guides/coding-standards.md`](../../../documentation/docs/guides/coding-standards.md). All Python code in `rag/` follows that document.

This stub is kept as a pointer because earlier versions of the `rag/` subtree (when it was the standalone `micro-x-rag` repo) shipped a duplicate copy. The duplicate has been removed to prevent drift; treat the canonical doc as the single source of truth.

## RAG-specific addendum

The following conventions apply only inside `rag/` and are *additive* to the canonical standards:

- **No hardcoded model names.** All provider/model references must use the configurable `*_PROVIDER` / `*_MODEL` variables in the notebook's Setup & Configuration cell.
- **Cache extraction results.** `extractions.json` is the resumability checkpoint for `scripts/run_extraction.py` and the GraphRAG notebook; never bypass it without setting `FORCE_RE_EXTRACT = True`.
- **PDFs come from `../catalogs/`.** Notebooks live two levels deep, so the path is `../../catalogs/`. The script `scripts/run_extraction.py` resolves this via `Path(__file__).parent.parent.parent / "catalogs"`.
