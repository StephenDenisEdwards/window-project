"""Catalog-DB explorer (UI option C) — FastAPI + a split-pane record <-> catalog viewer.

Serves the thin-build product DB, the gap report, rendered catalog pages, and the extracted
product photos; the frontend (static/index.html) lets you browse products, see each one's
fields + photo + gaps, and highlights the exact source region on the rendered catalog page
using the record's `_source` / `_page` / `_bbox` provenance.

Run from the repo root (catalog paths are relative):
    python design-scratch/ui/app.py
then open http://localhost:8000
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
from pydantic import BaseModel

HERE = os.path.dirname(__file__)
BUILD = os.path.join(HERE, "..", "build")
sys.path.insert(0, BUILD)
import thin_pipeline as tp  # noqa: E402

# Build the DB once at startup (also extracts product images into build/images/).
DB = tp.build_db()
GAP_PATH, _, _ = tp.generate_gap_report(DB)
GAPS = json.load(io.open(GAP_PATH, encoding="utf-8"))["gaps"]

# gaps grouped by part number, for quick per-product lookup
GAPS_BY_PN: dict = {}
for g in GAPS:
    GAPS_BY_PN.setdefault(g["part_number"], []).append(g)

app = FastAPI(title="Catalog DB Explorer")
_PAGE_CACHE: dict = {}


@app.get("/api/db")
def api_db():
    return {"products": DB["products"], "sources": DB["sources"],
            "reference": DB["reference"], "gap_summary": _gap_summary()}


@app.get("/api/gaps/{part_number}")
def api_gaps(part_number: str):
    return GAPS_BY_PN.get(part_number, [])


class Curation(BaseModel):
    part_number: str
    field: str
    value: str


@app.post("/api/curate")
def curate(c: Curation):
    """Persist a human-entered value (durable overlay) and apply it in memory."""
    r = DB["products"].get(c.part_number)
    if r is None:
        raise HTTPException(404, "unknown product")
    tp.save_curation(c.part_number, c.field, c.value)   # write durable curations.json
    r[c.field] = tp._coerce(c.value)
    r.setdefault("_curated", {})[c.field] = {"by": "ui"}
    GAPS_BY_PN[c.part_number] = [g for g in GAPS_BY_PN.get(c.part_number, []) if g["field"] != c.field]
    return {"ok": True, "record": r, "gaps": GAPS_BY_PN[c.part_number]}


def _gap_summary():
    by = {}
    for g in GAPS:
        by[g["kind"]] = by.get(g["kind"], 0) + 1
    return by


@app.get("/page/{source}/{page}.png")
def page_png(source: str, page: int):
    """Render a catalog page to PNG (cached)."""
    key = (source, page)
    if key not in _PAGE_CACHE:
        src = DB["sources"].get(source)
        if not src:
            raise HTTPException(404, f"unknown source {source}")
        doc = fitz.open(src["pdf"])
        if not (1 <= page <= doc.page_count):
            raise HTTPException(404, "page out of range")
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2))  # 144 dpi
        _PAGE_CACHE[key] = pix.tobytes("png")
    return Response(_PAGE_CACHE[key], media_type="image/png")


@app.get("/img/{name}")
def product_img(name: str):
    path = os.path.normpath(os.path.join(BUILD, "images", name))
    if not path.startswith(os.path.normpath(os.path.join(BUILD, "images"))) or not os.path.exists(path):
        raise HTTPException(404, "no such image")
    return FileResponse(path)


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


if __name__ == "__main__":
    print(f"Catalog DB Explorer: {len(DB['products'])} products, "
          f"{sum(_gap_summary().values())} gap fields. -> http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
