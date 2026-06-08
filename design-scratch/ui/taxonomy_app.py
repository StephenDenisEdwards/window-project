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
from pydantic import BaseModel

HERE = os.path.dirname(__file__)
BUILD = os.path.join(HERE, "..", "build")
sys.path.insert(0, BUILD)
import thin_pipeline as tp  # noqa: E402  (only for the SOURCES registry — no DB build)

_TAXDOC = json.load(io.open(os.path.join(HERE, "..", "taxonomy.json"), encoding="utf-8"))
# flatten the grouped taxonomy.json back to a section list (each section keeps its product_type)
TAX = [s for g in _TAXDOC["groups"] for t in g["types"] for s in t["sections"]]
SOURCES = tp.SOURCES
app = FastAPI(title="Taxonomy verifier")
_CACHE: dict = {}

# human review overlay — durable, committed, separate from the regenerated taxonomy.json
REVIEW_PATH = os.path.join(BUILD, "taxonomy_review.json")


def _key(catalog, section):
    return f"{catalog}|{section}"


def load_review():
    if os.path.exists(REVIEW_PATH):
        return json.load(io.open(REVIEW_PATH, encoding="utf-8"))
    return {}


def save_review(data):
    with io.open(REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


@app.get("/api/taxonomy")
def api_taxonomy():
    """Hierarchical tree: Sections -> product_type -> sections (those not flagged), and
    Other -> Misc (sections a human flagged as 'not a product type')."""
    rev = load_review()
    secs = [{**s, "review": rev.get(_key(s["catalog"], s["section"]))} for s in TAX]
    products = [s for s in secs if not (s.get("review") and s["review"]["status"] == "not_product")]
    other = [s for s in secs if s.get("review") and s["review"]["status"] == "not_product"]
    by_type: dict = {}
    for s in products:
        by_type.setdefault(s["product_type"], []).append(s)
    sections_group = {"name": "Sections",
                      "types": [{"product_type": pt, "sections": by_type[pt]} for pt in sorted(by_type)]}
    other_group = {"name": "Other", "types": [{"product_type": "Misc", "sections": other}]}
    return {"groups": [sections_group, other_group], "sources": SOURCES,
            "counts": {"products": len(products), "other": len(other)}}


class Review(BaseModel):
    catalog: str
    section: str
    status: str          # "product" (clears the flag) | "not_product"
    note: str = ""


@app.post("/api/review")
def review(r: Review):
    data = load_review()
    k = _key(r.catalog, r.section)
    if r.status == "product":
        data.pop(k, None)                 # un-mark
    else:
        data[k] = {"status": r.status, "note": r.note, "by": "ui"}
    save_review(data)
    return {"ok": True, "review": data.get(k)}


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
