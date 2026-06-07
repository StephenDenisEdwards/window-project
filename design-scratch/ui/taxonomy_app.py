"""Taxonomy verification UI — list every product type/section and show, on the actual
catalog page, the bounding box of the banner it was identified from. Built for verification:
click a section -> see exactly where on the page it came from.

Run from repo root:  python design-scratch/ui/taxonomy_app.py  -> http://localhost:8001
"""
from __future__ import annotations

import io
import json
import os
import sys

import fitz  # pymupdf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

HERE = os.path.dirname(__file__)
BUILD = os.path.join(HERE, "..", "build")
sys.path.insert(0, BUILD)
import thin_pipeline as tp  # noqa: E402  (only for the SOURCES registry — no DB build)

TAX = json.load(io.open(os.path.join(HERE, "..", "taxonomy.json"), encoding="utf-8"))
SOURCES = tp.SOURCES
app = FastAPI(title="Taxonomy verifier")
_CACHE: dict = {}


@app.get("/api/taxonomy")
def api_taxonomy():
    return {"sections": TAX, "sources": SOURCES}


@app.get("/page/{source}/{page}.png")
def page_png(source: str, page: int):
    key = (source, page)
    if key not in _CACHE:
        src = SOURCES.get(source)
        if not src:
            raise HTTPException(404, "unknown source")
        doc = fitz.open(src["pdf"])
        if not (1 <= page <= doc.page_count):
            raise HTTPException(404, "page out of range")
        _CACHE[key] = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    return Response(_CACHE[key], media_type="image/png")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(HERE, "static", "taxonomy.html"))


if __name__ == "__main__":
    print(f"Taxonomy verifier: {len(TAX)} sections -> http://localhost:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001)
