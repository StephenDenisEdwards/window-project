"""Validated product extraction -> ONE product database (products.json).

The decisive trust test: extract real records *behind a validation gate* so nothing garbage
is emitted, with per-row provenance (source/page/bbox) so every product is verifiable against
the page. Each extractor contributes records tagged with product_type + section; main() runs
them all and writes a single products.json. Add a new type = add an extractor to EXTRACTORS.

Run from repo root: python design-scratch/build/extract.py
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spikes"))
import table_extract_spike as tx  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "products.json")   # the single product database

OVERLAYS = {"full", "half", "inset"}
FIXINGS = {"screw_on", "dowel", "inserta", "expando"}
CLOSINGS = {"soft", "self", "free"}


def clean_sku(pn):
    """Validation gate: a Blum hinge SKU is uppercase, no spaces, BP-prefixed, no prose."""
    return bool(pn) and pn == pn.upper() and " " not in pn and bool(re.fullmatch(r"BP[0-9A-Z\-]{4,14}", pn))


def _series_of(title):
    t = (title or "").upper()
    if "BLUMOTION" in t:
        return "CLIP top BLUMOTION"
    if "CLIP TOP" in t:
        return "CLIP top"
    if "CLIP" in t:
        return "CLIP"
    return None


def extract_blum_cliptop():
    """Blum CLIP / CLIP-top euro hinges — the cleanest Section B tables (pages 6,7,10-13)."""
    pages = [6, 7, 10, 11, 12, 13]
    products, quarantine = [], []
    for p in pages:
        for b in tx.parse_page(p):
            if b["family"] != "concealed_hinge" or "BLUM" not in (b["banner"] or "").upper():
                continue
            for cells, sub, bbox in b["rows"]:
                rec = tx.emit_hinge(cells, sub, p, bbox)[0]
                pn = rec.get("part_number")
                if not clean_sku(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue                       # GATE: garbage never emitted
                ov = rec.get("overlay_class")
                prod = {
                    "part_number": pn, "brand": "Blum", "family": "hinge",
                    "product_type": "concealed_hinge", "section": b["banner"],
                    "series": _series_of(b.get("title")),
                    "opening_angle_deg": rec.get("opening_angle_deg"),
                    "overlay_class": ov if ov in OVERLAYS else None,
                    "fixing": rec.get("fixing") if rec.get("fixing") in FIXINGS else None,
                    "closing_type": rec.get("closing_type") if rec.get("closing_type") in CLOSINGS else None,
                    "_source": "wurth_b", "_page": p, "_bbox": bbox,
                }
                if ov and ov not in OVERLAYS:
                    prod["overlay_raw"] = ov        # preserve real-but-non-enum values (e.g. "diagonal 45º")
                products.append(prod)
    return products, quarantine


# add a new product type here once its extractor is written & verified
EXTRACTORS = [
    ("blum_cliptop", extract_blum_cliptop),
]


def build():
    products, quarantined = [], 0
    for name, fn in EXTRACTORS:
        recs, q = fn()
        products += recs
        quarantined += len(q)
    return products, quarantined


def main():
    products, quarantined = build()
    json.dump({"products": products, "quarantined": quarantined},
              io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
    by = collections.Counter((r["product_type"], r["section"]) for r in products)
    print(f"products.json: {len(products)} products, {quarantined} quarantined")
    for (pt, sec), n in sorted(by.items()):
        print(f"  {pt} > {sec}: {n}".encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
