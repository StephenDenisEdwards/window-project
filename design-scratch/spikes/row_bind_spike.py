"""Spike stage 2: segmentation + x-position column binding + schema records.

Builds on row_reconstruct_spike.py. Adds:
  - block segmentation: split a page into table blocks on header rows ("Item ...")
  - column binding by x-position: assign each data cell to a column by its x-centre
    (so a genuinely BLANK cell is detected, not collapsed away)
  - sub-group capture: mixed-case dividers between header and data (e.g.
    "Full Overlay Hinges (Cranking 00)") carried onto each record
  - schema-shaped emission for the concealed_hinge family (plan section 2.1)

Catalog sources
  Würth Baer Supply — Section B, Concealed Hinges (distributor catalog)
  catalogs/wurth-baer-section-b-concealed-hinges.pdf  (104 pp; PDF page N == printed "B-N")
  Pages exercised:
    B-6   — Blum Soft-Close Euro Hinges (CLIP top BLUMOTION) — overlay is a COLUMN
    B-45  — Grass TIOMOS Soft-Close Euro Hinges — overlay is a SUB-GROUP divider
    B-100 — Salice Wing Baseplates — dense SKU matrix with blank cells

Throwaway spike. Run: python design-scratch/spikes/row_bind_spike.py
"""
from __future__ import annotations

import re
import fitz  # pymupdf

PDF = "catalogs/wurth-baer-section-b-concealed-hinges.pdf"


def is_sku(s: str) -> bool:
    return (
        len(s) >= 5
        and s.upper() == s
        and sum(c.isalpha() for c in s) >= 2
        and any(c.isdigit() for c in s)
        and s.replace("-", "").isalnum()
    )


def clean_words(page):
    ph, pw = page.rect.height, page.rect.width
    out = []
    for x0, y0, x1, y1, w, *_ in page.get_text("words"):
        s = w.strip()
        if not s:
            continue
        if y0 < ph * 0.05 or y1 > ph * 0.95:          # running header/footer band
            continue
        if len(s) == 1 and s.isalpha() and s.isupper() and (x0 < pw * 0.06 or x0 > pw * 0.94):
            continue                                   # A-Y index rail
        out.append((x0, y0, x1, y1, s))
    return out


def to_rows(words, y_tol=3.0):
    words = sorted(words, key=lambda r: (r[1] + r[3]) / 2)
    rows, cur, cy = [], [], None
    for x0, y0, x1, y1, s in words:
        mid = (y0 + y1) / 2
        if cy is None or abs(mid - cy) <= y_tol:
            cur.append((x0, x1, s))
            cy = mid if cy is None else (cy + mid) / 2
        else:
            rows.append(sorted(cur, key=lambda c: c[0]))
            cur, cy = [(x0, x1, s)], mid
    if cur:
        rows.append(sorted(cur, key=lambda c: c[0]))
    return rows


def is_header(row) -> bool:
    return any(c[2].lower().startswith("item") for c in row)


def header_columns(row, gap=14):
    """Merge adjacent header words into column labels by x-gap; suffix duplicates."""
    groups, cur = [], [row[0]]
    for c in row[1:]:
        if c[0] - cur[-1][1] <= gap:
            cur.append(c)
        else:
            groups.append(cur)
            cur = [c]
    groups.append(cur)
    cols, seen = [], {}
    for g in groups:
        label = " ".join(c[2] for c in g)
        seen[label] = seen.get(label, 0) + 1
        if seen[label] > 1:
            label = f"{label} [{seen[label]}]"
        lo, hi = min(c[0] for c in g), max(c[1] for c in g)
        cols.append({"label": label, "lo": lo, "hi": hi, "c": (lo + hi) / 2})
    return cols


def bind(row, cols):
    centers = [c["c"] for c in cols]
    bounds = [(centers[i] + centers[i + 1]) / 2 for i in range(len(cols) - 1)]
    cells = {c["label"]: [] for c in cols}
    for x0, x1, s in row:
        cx = (x0 + x1) / 2
        idx = 0
        while idx < len(bounds) and cx > bounds[idx]:
            idx += 1
        cells[cols[idx]["label"]].append(s)
    return {k: " ".join(v) for k, v in cells.items()}


def extract_blocks(page):
    rows = to_rows(clean_words(page))
    records, cols, sub = [], None, None
    for r in rows:
        if is_header(r):
            cols, sub = header_columns(r), None
            continue
        if cols is None:
            continue
        if any(is_sku(c[2]) for c in r):
            rec = bind(r, cols)
            rec["_subgroup"] = sub
            records.append(rec)
        else:
            txt = " ".join(c[2] for c in r)
            if txt and txt != txt.upper():            # mixed-case divider, not a banner
                sub = txt
    return records


# --- schema-shaped emission for concealed_hinge (plan 2.1) ---

def norm_hinge(rec, page_no):
    o = {"_page": page_no, "_source": "wurth_b"}
    for label, val in rec.items():
        if label.startswith("_"):
            continue
        L = label.lower()
        if "item" in L:
            o["part_number"] = val
        elif "opening" in L:
            m = re.search(r"\d+", val)
            o["opening_angle_deg"] = int(m.group()) if m else None
        elif "overlay" in L:
            o["overlay_class"] = val.lower() or None
        elif "boring" in L:
            o["boring_pattern_mm"] = val or None
        elif "fixing" in L:
            o["fixing"] = val.lower().replace("-", "_") or None
        elif "clos" in L:
            v = val.lower()
            o["closing_type"] = "soft" if "soft" in v else ("self" if "self" in v else (v or None))
    o["_subgroup"] = rec.get("_subgroup")
    return o


def run(page_no, label, as_hinge=True):
    page = fitz.open(PDF)[page_no - 1]
    recs = extract_blocks(page)
    print("=" * 80)
    print(f"PAGE {page_no} — {label}  ({len(recs)} data rows bound)")
    print("=" * 80)
    for r in recs:
        out = norm_hinge(r, page_no) if as_hinge else r
        s = " | ".join(f"{k}={v!r}" for k, v in out.items())
        print(s.encode("ascii", "replace").decode())
    print()


if __name__ == "__main__":
    run(6, "Blum soft-close euro hinges — overlay is a COLUMN")
    run(45, "Grass TIOMOS soft-close — overlay is a SUB-GROUP, not a column")
    run(100, "Salice wing baseplates — dense matrix, blank cells", as_hinge=False)
