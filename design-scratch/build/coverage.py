"""Stock-take: cross-reference the taxonomy (every section in every catalog) against what
products.json actually contains, so we can see what's extracted vs remaining.

Run from repo root: python design-scratch/build/coverage.py
(needs products.json — run extract.py first.)
"""
from __future__ import annotations

import collections
import io
import json
import os

HERE = os.path.dirname(__file__)
TAX = json.load(io.open(os.path.join(HERE, "..", "taxonomy.json"), encoding="utf-8"))
PRODUCTS = json.load(io.open(os.path.join(HERE, "products.json"), encoding="utf-8"))["products"]
ISSUES = json.load(io.open(os.path.join(HERE, "extraction_issues.json"), encoding="utf-8"))["issues"]

CATLABEL = {"wurth_b": "Würth Baer — Section B (Concealed Hinges)",
            "wurth_c": "Würth Baer — Section C (Lift Systems)",
            "grass_tiomos": "Grass TIOMOS (manufacturer)",
            "grass_nexis": "Grass NEXIS (manufacturer)"}


def main():
    by_section = collections.Counter((p["_source"], p["section"]) for p in PRODUCTS)
    # flatten the taxonomy "Sections" group to (catalog, section, product_type, pages, approx)
    sections = []
    for g in TAX["groups"]:
        if g["name"] != "Sections":
            continue
        for t in g["types"]:
            for s in t["sections"]:
                sections.append(s)

    done_sec = sum(1 for s in sections if by_section.get((s["catalog"], s["section"]), 0) > 0)
    out = []
    out.append("=" * 78)
    out.append(f"COVERAGE — {len(PRODUCTS)} products extracted across "
               f"{done_sec}/{len(sections)} taxonomy sections")
    out.append("=" * 78)

    by_cat = collections.defaultdict(list)
    for s in sections:
        by_cat[s["catalog"]].append(s)
    for cat, rows in by_cat.items():
        rows.sort(key=lambda s: s["pages"][0])
        ext = sum(1 for s in rows if by_section.get((cat, s["section"]), 0) > 0)
        nprod = sum(by_section.get((cat, s["section"]), 0) for s in rows)
        out.append(f"\n{CATLABEL.get(cat, cat)}   [{ext}/{len(rows)} sections, {nprod} products]")
        out.append("-" * 78)
        for s in rows:
            a, z = s["pages"]
            pg = f"B-{a}" if a == z else f"B-{a}-{z}"
            n = by_section.get((cat, s["section"]), 0)
            mark = f"[OK {n:>3}]" if n else "[  --  ]"
            out.append(f"  {mark} {pg:<8} {s['product_type']:<22} {s['section'][:40]}")

    # product-type rollup
    out.append("\n" + "=" * 78)
    out.append("BY PRODUCT TYPE (extracted)")
    out.append("-" * 78)
    pt = collections.Counter(p["product_type"] for p in PRODUCTS)
    for k, v in pt.most_common():
        out.append(f"  {v:>4}  {k}")
    br = collections.Counter(p["brand"] for p in PRODUCTS)
    out.append("\nBY BRAND: " + ", ".join(f"{k} {v}" for k, v in br.most_common()))

    op = [i for i in ISSUES if (i.get("status") or "open") != "resolved"]
    out.append(f"\nISSUES: {len(ISSUES)} total, {len(op)} open"
               + ("" if not op else " -> " + ", ".join(i["id"] for i in op)))
    print("\n".join(out).encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
