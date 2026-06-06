"""Spike: can we rebuild distributor catalog tables into ROWS from positional layout?

Hypothesis (plan section 2.2 B1): plain get_text() linearises tables into scrambled
column streams, but the PDF carries x/y bounding boxes per word — so clustering words by
y (rows) and x (columns) should reconstruct the original table rows.

Catalog sources
  Würth Baer Supply — Section B, Concealed Hinges (distributor catalog)
  catalogs/wurth-baer-section-b-concealed-hinges.pdf  (104 pp; PDF page N == printed "B-N")
  Pages exercised:
    B-6   — Blum Soft-Close Euro Hinges (CLIP top BLUMOTION) — clean grid (baseline)
    B-100 — Salice Wing Baseplates — dense SKU matrix (stress test)

Throwaway spike. Run: python design-scratch/spikes/row_reconstruct_spike.py
"""
from __future__ import annotations

import sys
import fitz  # pymupdf

PDF = "catalogs/wurth-baer-section-b-concealed-hinges.pdf"


def reconstruct(page, y_tol=3.0):
    """Return list of rows; each row = list of (x0, text) sorted left-to-right."""
    words = page.get_text("words")  # (x0,y0,x1,y1, word, block, line, word_no)
    pw = page.rect.width

    kept = []
    for x0, y0, x1, y1, w, *_ in words:
        s = w.strip()
        if not s:
            continue
        # --- boilerplate filters ---
        # A-Y index rail: isolated single uppercase letters near the page margins
        if len(s) == 1 and s.isalpha() and s.isupper() and (x0 < pw * 0.06 or x0 > pw * 0.94):
            continue
        # header/footer text + page-number band
        if any(t in s.upper() for t in ("WURTH", "WWW.", "BAERSUPPLY", "289-2237")):
            continue
        kept.append((x0, y0, x1, y1, s))

    # cluster into rows by y (use vertical midpoint)
    kept.sort(key=lambda r: (r[1] + r[3]) / 2)
    rows = []
    cur, cur_y = [], None
    for x0, y0, x1, y1, s in kept:
        mid = (y0 + y1) / 2
        if cur_y is None or abs(mid - cur_y) <= y_tol:
            cur.append((x0, s))
            cur_y = mid if cur_y is None else (cur_y + mid) / 2
        else:
            rows.append(sorted(cur, key=lambda c: c[0]))
            cur, cur_y = [(x0, s)], mid
    if cur:
        rows.append(sorted(cur, key=lambda c: c[0]))
    return rows


def show(page_no, label):
    page = fitz.open(PDF)[page_no - 1]
    rows = reconstruct(page)
    print("=" * 78)
    print(f"PAGE {page_no} — {label}  ({len(rows)} reconstructed rows)")
    print("=" * 78)
    for r in rows:
        line = "  |  ".join(text for _x, text in r)
        print(line.encode("ascii", "replace").decode())
    print()


if __name__ == "__main__":
    # p6  = Blum soft-close euro hinges  -> clean, regular grid (baseline)
    # p100 = Salice wing baseplates       -> dense SKU matrix (stress test)
    show(6, "Blum soft-close euro hinges (clean grid)")
    show(100, "Salice wing baseplates (dense matrix)")
