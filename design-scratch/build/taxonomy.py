"""Build a product-type taxonomy across all catalogs — the trustworthy backbone.

Uses only the RELIABLE signal (all-caps section banners + a SKU-token count), NOT the
fragile per-cell table parsing. For each catalog it groups consecutive pages by section
banner and maps each section to a product_type + family + brand, with its page range and an
approximate SKU count.

Emits design-scratch/taxonomy.json and design-scratch/taxonomy.md (both committed).
Run from repo root: python design-scratch/build/taxonomy.py
"""
from __future__ import annotations

import io
import json
import os
import re

import fitz  # pymupdf

CATALOGS = [
    ("wurth_b", "catalogs/wurth-baer-section-b-concealed-hinges.pdf", "Würth Baer — Section B (Concealed Hinges)"),
    ("wurth_c", "catalogs/Wurth_Baer_Section_C.pdf", "Würth Baer — Section C (Lift Systems & Semi-Concealed)"),
    ("grass_tiomos", "catalogs/grass-tiomos-catalog.pdf", "Grass TIOMOS (manufacturer)"),
    ("grass_nexis", "catalogs/grass-nexis-catalog.pdf", "Grass NEXIS (manufacturer)"),
]
OUT_JSON = os.path.join(os.path.dirname(__file__), "..", "taxonomy.json")
OUT_MD = os.path.join(os.path.dirname(__file__), "..", "taxonomy.md")
BOILER = ("WURTH", "BAER SUPPLY", "WWW.", "800-289", "GRASSUSA", "SUBJECT TO TECHNICAL",
          "FIND IT FAST", "SCAN", "ORDERING", "TABLE OF CONTENTS", "IMPORTANT NOTE",
          "OUR QUALITY", "OUR EXPERIENCE")


def is_sku(s):
    return (len(s) >= 5 and s.upper() == s and sum(c.isalpha() for c in s) >= 2
            and any(c.isdigit() for c in s) and s.replace("-", "").isalnum())


def banner_of(page):
    for line in page.get_text().splitlines():
        s = re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", "", line)).strip()
        if len(s) < 6 or any(b in s.upper() for b in BOILER):
            continue
        if s == s.upper() and len([w for w in s.split() if len(w) >= 3 and w.isalpha()]) >= 2:
            return s
    return None


def classify(banner):
    """(product_type, family) from the banner keywords."""
    b = banner.lower()
    rules = [
        (("base plate", "baseplate", "mounting plate", "adapter plate", "baseplates"), ("baseplate", "baseplate")),
        (("tip-on", "tipmatic"), ("push_mechanism", "accessory")),
        (("machine", "assembly aid", "overlay chart"), ("hinge_tool", "tool")),
        (("servo-drive", "electrical"), ("lift_accessory", "accessory")),
        (("soft-close device", "soft-close adapter", "restriction clip", "accessor", "assembly hardware"),
         ("hinge_accessory", "accessory")),
        (("aventos", "kinvaro", "wind lift"), ("lift_system", "lift_system")),
        (("flap", "pacta"), ("flap_hinge", "flap_hinge")),
        (("counterbalance",), ("counterbalance_lift", "lift_system")),
        (("lid support", "stay"), ("lid_stay", "lid_stay")),
        (("institutional",), ("institutional_hinge", "institutional_hinge")),
        (("piano",), ("piano_hinge", "piano_hinge")),
        (("soss", "invisible"), ("invisible_hinge", "invisible_hinge")),
        (("3-d adjustable", "3-d"), ("adjustable_3d_hinge", "specialty_hinge")),
        (("wrap", "demountable"), ("wrap_demountable_hinge", "specialty_hinge")),
        (("face mount",), ("face_mount_hinge", "face_mount_hinge")),
        (("full inset",), ("full_inset_hinge", "specialty_hinge")),
        (("pin/knife", "knife"), ("pin_knife_hinge", "specialty_hinge")),
        (("pivot", "butt"), ("pivot_hinge", "pivot_hinge")),
        (("glass door",), ("glass_door_hinge", "glass_door_hinge")),
        (("face frame", "compact"), ("face_frame_hinge", "concealed_hinge")),
        (("euro hinge", "clip", "onyx", "angled", "zero protrusion", "tec", "air hinge",
          "soft-close euro", "self-close"), ("concealed_hinge", "concealed_hinge")),
        (("specialty",), ("specialty_hinge", "concealed_hinge")),
        (("hinge",), ("concealed_hinge", "concealed_hinge")),
    ]
    for keys, out in rules:
        if any(k in b for k in keys):
            return out
    return ("unknown", "unknown")


def brand_of(banner):
    b = banner.upper()
    for name in ("BLUM", "GRASS", "SALICE", "PRO", "SOSS", "YOUNGDALE", "PETER MEIER"):
        if name in b:
            return name.title() if name not in ("SOSS", "PRO") else name.capitalize()
    return None


def sections_for(pdf):
    doc = fitz.open(pdf)
    out, cur, start, sku = [], None, 1, 0
    for i in range(doc.page_count):
        b = banner_of(doc[i])
        n = sum(1 for w in doc[i].get_text().split() if is_sku(w))
        norm = re.sub(r"\s+", " ", b).strip() if b else None
        if norm != cur:
            if cur:
                out.append({"banner": cur, "pages": [start, i], "approx_skus": sku})
            cur, start, sku = norm, i + 1, 0
        sku += n
    if cur:
        out.append({"banner": cur, "pages": [start, doc.page_count], "approx_skus": sku})
    return [s for s in out if s["approx_skus"] > 0 or "ITEMS" in s["banner"]]


def build():
    tax = []
    for code, pdf, label in CATALOGS:
        for s in sections_for(pdf):
            ptype, fam = classify(s["banner"])
            tax.append({"catalog": code, "catalog_label": label, "section": s["banner"],
                        "product_type": ptype, "family": fam, "brand": brand_of(s["banner"]),
                        "pages": s["pages"], "approx_skus": s["approx_skus"]})
    return tax


def write_md(tax):
    lines = ["# Product-type taxonomy (all catalogs)", "",
             "> Built from section banners + SKU-token counts (reliable signal), by",
             "> `build/taxonomy.py`. `approx_skus` is a rough magnitude, not a verified count.", ""]
    by_cat = {}
    for t in tax:
        by_cat.setdefault((t["catalog"], t["catalog_label"]), []).append(t)
    total = 0
    for (code, label), rows in by_cat.items():
        lines += [f"## {label}  (`{code}`)", "",
                  "| pages | section | product_type | family | brand | ~skus |",
                  "|-------|---------|--------------|--------|-------|------:|"]
        for r in rows:
            a, z = r["pages"]
            p = str(a) if a == z else f"{a}–{z}"
            lines.append(f"| {p} | {r['section']} | `{r['product_type']}` | `{r['family']}` | "
                         f"{r['brand'] or '—'} | {r['approx_skus']} |")
            total += r["approx_skus"]
        lines.append("")
    types = sorted(set(t["product_type"] for t in tax))
    lines += ["## Distinct product types", "", ", ".join(f"`{x}`" for x in types), "",
              f"_{len(tax)} sections across {len(by_cat)} catalogs; ~{total} SKU tokens total._"]
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    tax = build()
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tax, f, ensure_ascii=False, indent=2)
    write_md(tax)
    types = sorted(set(t["product_type"] for t in tax))
    print(f"taxonomy: {len(tax)} sections, {len(types)} product types -> taxonomy.json + taxonomy.md")
    print("product types:", ", ".join(types))


if __name__ == "__main__":
    main()
