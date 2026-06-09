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


def _height_mm(v):
    m = re.search(r"\d+(?:\.\d+)?", v or "")
    if not m:
        return None
    f = float(m.group())
    return int(f) if f == int(f) else f


def _material(v):
    v = (v or "").lower()
    if "die-cast" in v or "die cast" in v:
        return "zinc_die_cast"
    if "stamped" in v:
        return "stamped_steel"
    return None


def _fixing_baseplate(v):
    v = (v or "").lower()
    for key, out in (("expando", "expando"), ("inserta", "inserta"), ("dowel", "dowel"),
                     ("truss", "truss_head_screw"), ("system screw", "system_screw"),
                     ("pre-mounted", "system_screw"), ("premounted", "system_screw"),
                     ("wood", "wood_screw"), ("euro", "euro_screw")):   # bare 'Euro Screws' (loose); pre-mounted handled above
        if key in v:
            return out
    return None


def extract_blum_baseplate():
    """Blum CLIP mounting plates — Section B pages 19-21 (Item#/Height/Fixing/Material columns).
    Strips diagram-callout letters from the Item# cell; the gate drops the drill-bit sub-block.
    Column semantics differ for the B-20 face-frame sub-table (variant text lands in the Fixing
    column) — preserved as fixing_raw rather than coerced or dropped."""
    pages = [19, 20, 21]
    products, quarantine = [], []
    for p in pages:
        for b in tx.parse_page(p):
            if b["family"] != "baseplate" or "BLUM" not in (b["banner"] or "").upper():
                continue
            for cells, sub, bbox in b["rows"]:
                pn = tx.strip_callout(cells.get("Item #", "") or "")
                if not clean_sku(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue                       # GATE: only clean BP baseplate SKUs
                fx_raw = (cells.get("Fixing Type") or "").strip() or None
                mat_raw = (cells.get("Material") or "").strip() or None
                prod = {
                    "part_number": pn, "brand": "Blum", "family": "baseplate",
                    "product_type": "baseplate", "section": b["banner"], "series": "CLIP",
                    "plate_style": sub,
                    "height_mm": _height_mm(cells.get("Height")),
                    "fixing_type": _fixing_baseplate(fx_raw),
                    "material": _material(mat_raw),
                    "inset_recess_in": (cells.get("Inset Recess") or "").strip() or None,
                    "_source": "wurth_b", "_page": p, "_bbox": bbox,
                }
                if fx_raw and prod["fixing_type"] is None:
                    prod["fixing_raw"] = fx_raw     # preserve real-but-unmapped values
                if mat_raw and prod["material"] is None:
                    prod["material_raw"] = mat_raw
                products.append(prod)
    return products, quarantine


def clean_gff(pn):
    """Validation gate for Grass TIOMOS hinge SKUs: GFF + 8-16 digits, no prose."""
    return bool(pn) and pn == pn.upper() and " " not in pn and bool(re.fullmatch(r"GFF[0-9]{8,16}", pn))


def _cell(cells, sub):
    """Fetch a cell value by header substring (handles header variants e.g.
    'Close Type' vs 'Closing Type', 'Fixing' vs 'Fixing Type')."""
    for k, v in cells.items():
        if sub in k.lower():
            return v
    return None


def _overlay_tiomos(sub):
    s = (sub or "").lower()
    if "inset" in s:
        return "inset"
    if "half overlay" in s:
        return "half"
    if "overlay" in s:          # 'Full Overlay (Cranking 00)' and 'Overlay (Cranking 03)' are both full-overlay mounting
        return "full"
    return None


def _fixing_tiomos(v):
    v = (v or "").lower()
    if "dowel" in v:
        return "dowel"
    if "screw" in v:
        return "screw_on"
    if "impresso" in v or "press" in v:
        return "impresso"
    return None


def _close_tiomos(v):
    v = (v or "").lower()
    return "soft" if "soft" in v else "self" if "self" in v else "free" if "free" in v else None


def extract_grass_tiomos():
    """Grass TIOMOS euro hinges — Section B p45-52 (soft-close 45-48, self-close 49-52).
    Overlay is in the sub-group banner (with Grass 'cranking' + max-overlay mm), not a column.
    Gates on the hinge table shape (a Close Type column) so the accessory/tool sub-blocks that
    share the GFF prefix (restriction clip, drill bits) are skipped. Opening angle is a
    series/diagram property here, not per-row -> left null and flagged."""
    pages = list(range(45, 53))
    products, quarantine = [], []
    for p in pages:
        for b in tx.parse_page(p):
            if b["family"] != "concealed_hinge" or "TIOMOS" not in (b["banner"] or "").upper():
                continue
            labels = [c["label"].lower() for c in (b.get("cols") or [])]
            if not any("boring" in l for l in labels):   # only the hinge table has a Boring Pattern column;
                continue                                 # skips Finish/Box-Qty + Description sub-blocks
            ang = re.search(r"(\d{2,3})\s*[°º?]", b.get("title") or "")   # 'Tiomos 95° Hinges...' titles
            for cells, sub, bbox in b["rows"]:
                pn = tx.strip_callout(cells.get("Item #", "") or "")
                if not clean_gff(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue                         # GATE: only clean GFF hinge SKUs
                fx_raw = (_cell(cells, "fixing") or "").strip() or None
                cr = re.search(r"cranking\s+([0-9.]+)", (sub or "").lower())
                mo = re.search(r"(\d+)\s*mm", sub or "")
                prod = {
                    "part_number": pn, "brand": "Grass", "family": "hinge",
                    "product_type": "concealed_hinge", "section": b["banner"], "series": "TIOMOS",
                    "overlay_class": _overlay_tiomos(sub),
                    "overlay_raw": sub,                       # full Grass sub-group (carries cranking detail)
                    "cranking": cr.group(1) if cr else None,
                    "max_overlay_mm": int(mo.group(1)) if mo else None,
                    "boring_pattern": (_cell(cells, "boring") or "").strip() or None,
                    "fixing": _fixing_tiomos(fx_raw),
                    "closing_type": _close_tiomos(_cell(cells, "clos")),
                    "opening_angle_deg": int(ang.group(1)) if ang else None,
                    "_source": "wurth_b", "_page": p, "_bbox": bbox,
                }
                if fx_raw and prod["fixing"] is None:
                    prod["fixing_raw"] = fx_raw
                products.append(prod)
    return products, quarantine


def extract_grass_tiomos_baseplate():
    """Grass TIOMOS mounting plates — Section B p60-62 (wing 60, thick/inline 61, face-frame 62).
    Tables: Item#/Height/Fixing Type/# of Fixing Points, GFF058139... SKUs. Each page also has
    drill-bit (Item#/Description) and screw (Length x Gauge...) sub-tables — excluded by gating on
    the Height column (only the baseplate table has it). Callout letters stripped from Item#.
    No Material column in these tables (left null). Fixing text carries extra detail (Euro/with
    Flange), so fixing_raw is always kept alongside the normalized fixing_type."""
    pages = [60, 61, 62]
    products, quarantine = [], []
    for p in pages:
        for b in tx.parse_page(p):
            if b["family"] != "baseplate" or "TIOMOS" not in (b["banner"] or "").upper():
                continue
            labels = " ".join(c["label"].lower() for c in (b.get("cols") or []))
            if "height" not in labels:                 # baseplate table has Height; skips bit/screw tables
                continue
            for cells, sub, bbox in b["rows"]:
                pn = tx.strip_callout(cells.get("Item #", "") or "")
                if not clean_gff(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue                           # GATE: only clean GFF baseplate SKUs
                fx_raw = (_cell(cells, "fixing type") or "").strip() or None
                pts = (_cell(cells, "point") or "").strip()
                products.append({
                    "part_number": pn, "brand": "Grass", "family": "baseplate",
                    "product_type": "baseplate", "section": b["banner"], "series": "TIOMOS",
                    "plate_style": sub,
                    "height_mm": _height_mm(_cell(cells, "height")),
                    "fixing_type": _fixing_baseplate(fx_raw),
                    "fixing_raw": fx_raw,
                    "fixing_points": int(pts) if pts.isdigit() else None,
                    "material": None,                  # not listed in TIOMOS baseplate tables
                    "_source": "wurth_b", "_page": p, "_bbox": bbox,
                })
    return products, quarantine


# add a new product type here once its extractor is written & verified
EXTRACTORS = [
    ("blum_cliptop", extract_blum_cliptop),
    ("blum_baseplate", extract_blum_baseplate),
    ("grass_tiomos", extract_grass_tiomos),
    ("grass_tiomos_baseplate", extract_grass_tiomos_baseplate),
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
