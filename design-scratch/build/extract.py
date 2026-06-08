"""Clean, validated extraction of ONE product type: Blum CLIP / CLIP-top euro hinges.

The decisive trust test: extract real records *behind a validation gate* so nothing garbage
is emitted, with per-row provenance (source/page/bbox) so every product is verifiable against
the page. Scope: the Blum euro-hinge sections in Würth Section B (the cleanest tables) —
NOT the whole catalog. If this can't be made clean, the positional parser is the wrong tool.

Run from repo root: python design-scratch/build/extract.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spikes"))
import table_extract_spike as tx  # noqa: E402

PAGES = [6, 7, 10, 11, 12, 13]            # Blum CLIP / CLIP-top euro hinge sections (Section B)
OUT = os.path.join(os.path.dirname(__file__), "products_blum_cliptop.json")

OVERLAYS = {"full", "half", "inset"}
FIXINGS = {"screw_on", "dowel", "inserta", "expando"}
CLOSINGS = {"soft", "self", "free"}


def clean_sku(pn):
    """Validation gate: a Blum hinge SKU is uppercase, no spaces, BP-prefixed, no prose."""
    return bool(pn) and pn == pn.upper() and " " not in pn and bool(re.fullmatch(r"BP[0-9A-Z\-]{4,14}", pn))


def series_of(title):
    t = (title or "").upper()
    if "BLUMOTION" in t:
        return "CLIP top BLUMOTION"
    if "CLIP TOP" in t:
        return "CLIP top"
    if "CLIP" in t:
        return "CLIP"
    return None


def extract():
    products, quarantine = [], []
    for p in PAGES:
        for b in tx.parse_page(p):
            if b["family"] != "concealed_hinge" or "BLUM" not in (b["banner"] or "").upper():
                continue
            series = series_of(b.get("title"))
            for cells, sub, bbox in b["rows"]:
                rec = tx.emit_hinge(cells, sub, p, bbox)[0]
                pn = rec.get("part_number")
                if not clean_sku(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue                       # GATE: garbage never emitted
                ov = rec.get("overlay_class")
                prod = {
                    "part_number": pn, "brand": "Blum", "family": "hinge",
                    "product_type": "concealed_hinge", "series": series,
                    "opening_angle_deg": rec.get("opening_angle_deg"),
                    "overlay_class": ov if ov in OVERLAYS else None,
                    "fixing": rec.get("fixing") if rec.get("fixing") in FIXINGS else None,
                    "closing_type": rec.get("closing_type") if rec.get("closing_type") in CLOSINGS else None,
                    "_source": "wurth_b", "_page": p, "_bbox": bbox,
                }
                if ov and ov not in OVERLAYS:
                    prod["overlay_raw"] = ov            # preserve real-but-non-enum values (e.g. "diagonal 45º")
                products.append(prod)
    return products, quarantine


def main():
    products, q = extract()
    json.dump({"product_type": "concealed_hinge", "brand": "Blum", "line": "CLIP / CLIP-top",
               "pages": PAGES, "products": products, "quarantined": len(q)},
              io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
    n = len(products)
    print(f"Blum CLIP / CLIP-top euro hinges: {n} clean products, {len(q)} quarantined (failed gate)")
    print("field coverage:")
    for f in ("series", "opening_angle_deg", "overlay_class", "fixing", "closing_type"):
        c = sum(1 for r in products if r.get(f) not in (None, ""))
        print(f"  {f:<18} {c}/{n}")
    print("sample:")
    for r in products[:8]:
        print(f"   {r['part_number']:<12} {r['series']} {r['opening_angle_deg']}° "
              f"{r['overlay_class']}/{r['fixing']}/{r['closing_type']}".encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
