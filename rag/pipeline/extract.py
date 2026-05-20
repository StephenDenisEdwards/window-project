"""PDF extraction and chunking. Pure functions, no LLM or network calls.

Canonical chunker for the pipeline. Chunk IDs are deterministic
(`{pdf_stem}_p{page}_c{idx}`) so extractions persist meaningfully
across reruns and can be joined to vector-store rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(slots=True)
class Chunk:
    id: str
    text: str
    source: str
    page: int
    chunk_index: int

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": {
                "source": self.source,
                "page": self.page,
                "chunk_index": self.chunk_index,
            },
        }


def extract_pdf_pages(pdf_path: Path, max_pages: int | None = None) -> list[dict]:
    """Extract text per page from `pdf_path`. Pages with <50 chars are dropped."""
    documents = []
    doc = fitz.open(str(pdf_path))
    num_pages = min(len(doc), max_pages) if max_pages else len(doc)
    for page_num in range(num_pages):
        page = doc[page_num]
        text = page.get_text()
        if text and len(text.strip()) > 50:
            documents.append({
                "page": page_num + 1,
                "text": text,
                "source": pdf_path.name,
            })
    doc.close()
    return documents


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into fixed-size overlapping windows."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def build_chunks(
    catalog_dir: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    max_pages_per_pdf: int | None = None,
    min_chunk_chars: int = 50,
) -> list[Chunk]:
    """Iterate PDFs in `catalog_dir`, return a flat list of `Chunk` objects.

    Chunks shorter than `min_chunk_chars` (after `.strip()`) are skipped.
    """
    chunks: list[Chunk] = []
    for pdf_path in sorted(catalog_dir.glob("*.pdf")):
        pages = extract_pdf_pages(pdf_path, max_pages=max_pages_per_pdf)
        for page in pages:
            for i, raw in enumerate(chunk_text(page["text"], chunk_size, chunk_overlap)):
                if len(raw.strip()) < min_chunk_chars:
                    continue
                chunks.append(
                    Chunk(
                        id=f"{pdf_path.stem}_p{page['page']}_c{i}",
                        text=raw,
                        source=page["source"],
                        page=page["page"],
                        chunk_index=i,
                    )
                )
    return chunks
