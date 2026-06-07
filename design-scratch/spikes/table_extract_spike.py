"""Spike stage 3: multi-row header naming + per-block family routing.

Builds on row_bind_spike.py. Adds the two refinements that stage 2 surfaced:
  - MULTI-ROW HEADER NAMING: when the binding header row has duplicate labels
    (e.g. Salice "Plate Height | Item# | Item# | Item#"), compose real column
    names from the label row(s) stacked above it (Wood Screw / Euro Screw /
    Dowel), bound by x-position.
  - PER-BLOCK FAMILY ROUTING: classify each table block as concealed_hinge /
    baseplate / accessory from its columns + banner/divider context, and route
    to the matching emitter — so an "Accessory Items" sub-table on a hinge page
    is no longer parsed as a hinge.
  - bonus: callout-letter cleanup (strip leading single-letter diagram keys like
    "A AA203351" -> "AA203351"); baseplate matrices explode to one product per
    non-empty cell.

Catalog sources
  Würth Baer Supply — Section B, Concealed Hinges (distributor catalog)
  catalogs/wurth-baer-section-b-concealed-hinges.pdf  (104 pp; PDF page N == printed "B-N")
  Pages exercised:
    B-6   — Blum Soft-Close Euro Hinges       -> concealed_hinge (overlay = column)
    B-45  — Grass TIOMOS Soft-Close + bits     -> concealed_hinge + accessory routing
    B-100 — Salice Wing Baseplates             -> baseplate, multi-row header naming

Throwaway spike. Run: python design-scratch/spikes/table_extract_spike.py
"""
from __future__ import annotations

import re
import fitz  # pymupdf

PDF = "catalogs/wurth-baer-section-b-concealed-hinges.pdf"


# --- shared helpers (from stage 1/2) ---

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
        if y0 < ph * 0.05 or y1 > ph * 0.95:
            continue
        if len(s) == 1 and s.isalpha() and s.isupper() and (x0 < pw * 0.06 or x0 > pw * 0.94):
            continue
        out.append((x0, y0, x1, y1, s))
    return out


def to_rows(words, y_tol=3.0):
    """Cluster words into rows. Returns (rows, bboxes): rows[i] is a list of (x0,x1,s)
    cells (sorted L->R); bboxes[i] is the row's (x0,y0,x1,y1) box in PDF points."""
    words = sorted(words, key=lambda r: (r[1] + r[3]) / 2)
    rows, bboxes, cur, full, cy = [], [], [], [], None

    def flush():
        rows.append(sorted(cur, key=lambda c: c[0]))
        bboxes.append((min(w[0] for w in full), min(w[1] for w in full),
                       max(w[2] for w in full), max(w[3] for w in full)))

    for x0, y0, x1, y1, s in words:
        mid = (y0 + y1) / 2
        if cy is None or abs(mid - cy) <= y_tol:
            cur.append((x0, x1, s)); full.append((x0, y0, x1, y1))
            cy = mid if cy is None else (cy + mid) / 2
        else:
            flush(); cur, full, cy = [(x0, x1, s)], [(x0, y0, x1, y1)], mid
    if cur:
        flush()
    return rows, bboxes


def row_text(row):
    return " ".join(c[2] for c in row)


def is_header(row):
    # token "item"/"item#" but NOT "items" (e.g. the "Accessory Items" divider)
    return any(c[2].lower().rstrip("#.:") == "item" for c in row)


def header_columns(row, gap=14):
    groups, cur = [], [row[0]]
    for c in row[1:]:
        if c[0] - cur[-1][1] <= gap:
            cur.append(c)
        else:
            groups.append(cur)
            cur = [c]
    groups.append(cur)
    cols = []
    for g in groups:
        lo, hi = min(c[0] for c in g), max(c[1] for c in g)
        cols.append({"label": " ".join(c[2] for c in g), "lo": lo, "hi": hi, "c": (lo + hi) / 2})
    return cols


def col_index(cx, cols):
    centers = [c["c"] for c in cols]
    bounds = [(centers[i] + centers[i + 1]) / 2 for i in range(len(cols) - 1)]
    idx = 0
    while idx < len(bounds) and cx > bounds[idx]:
        idx += 1
    return idx


def bin_row(row, cols):
    buckets = [[] for _ in cols]
    for x0, x1, s in row:
        buckets[col_index((x0 + x1) / 2, cols)].append(s)
    return buckets


def bind(row, cols):
    buckets = bin_row(row, cols)
    return {cols[i]["label"]: " ".join(buckets[i]) for i in range(len(cols))}


# --- refinement 1: multi-row header naming ---

_FILLER = {"item", "item#", "#", ""}


def name_columns(cols, label_rows):
    """If the binding row has duplicate labels, compose real names from the
    label row(s) above (bound by x-position)."""
    labels = [c["label"] for c in cols]
    if len(set(labels)) == len(labels):
        return cols  # already unique — nothing to do
    composed = [[] for _ in cols]
    for lrow in label_rows:                       # top -> bottom
        for i, words in enumerate(bin_row(lrow, cols)):
            for w in words:
                if w.lower() not in _FILLER and (not composed[i] or composed[i][-1] != w):
                    composed[i].append(w)
    for i, c in enumerate(cols):
        if composed[i]:
            c["label"] = " ".join(composed[i])
        else:
            c["label"] = f"{c['label']} [{i}]"   # keep distinct even if unnamed
    return cols


# --- refinement 2: per-block family routing ---

def classify_block(cols, banner, divider):
    labels = " ".join(c["label"].lower() for c in cols)
    ctx = f"{banner or ''} {divider or ''}".lower()
    hinge = any(k in labels for k in ("opening", "overlay", "boring", "clos"))
    plate = ("height" in labels) or ("plate" in labels)
    descr = "descr" in labels
    if hinge and not plate:
        return "concealed_hinge"
    if plate and not hinge:
        return "baseplate"
    if descr and not hinge and not plate:
        return "accessory"
    if "baseplate" in ctx or "mounting plate" in ctx:
        return "baseplate"
    if any(k in ctx for k in ("accessor", "clip", "bit", "screw", "template", "vix")):
        return "accessory"
    if "hinge" in ctx:
        return "concealed_hinge"
    return "unknown"


# --- value cleanup / emitters ---

def strip_callout(v):
    toks = v.split()
    while toks and len(toks[0]) == 1 and toks[0].isalpha():
        toks.pop(0)
    return " ".join(toks)


def parse_mm(v):
    m = re.search(r"\d+", v or "")
    return int(m.group()) if m else None


def fixing_from_name(name):
    n = name.lower()
    if "wood" in n:
        return "wood_screw"
    if "euro" in n:
        return "premounted_euro_screw"
    if "dowel" in n:
        return "split_dowel"
    return n or None


def emit_hinge(cells, sub, page_no, bbox=None):
    o = {"family": "concealed_hinge", "_page": page_no, "_source": "wurth_b", "_bbox": bbox}
    for label, val in cells.items():
        L = label.lower()
        if "item" in L:
            o["part_number"] = strip_callout(val)
        elif "opening" in L:
            o["opening_angle_deg"] = parse_mm(val)
        elif "overlay" in L:
            o["overlay_class"] = val.lower() or None
        elif "boring" in L:
            o["boring_pattern_mm"] = val or None
        elif "fixing" in L:
            o["fixing"] = val.lower().replace("-", "_") or None
        elif "clos" in L:
            v = val.lower()
            o["closing_type"] = "soft" if "soft" in v else ("self" if "self" in v else (v or None))
    o["_subgroup"] = sub
    return [o]


def emit_baseplate(cells, cols, sub, page_no, bbox=None):
    """Explode a matrix row into one baseplate product per non-empty SKU cell.
    (All share the row bbox; cell-level bbox would be a later refinement.)"""
    height = next((cells[c["label"]] for c in cols if "height" in c["label"].lower()), None)
    out = []
    for c in cols:
        lab = c["label"]
        if "height" in lab.lower():
            continue
        v = cells[lab].strip()
        if not v or v == "-":
            continue
        out.append({
            "family": "baseplate", "_page": page_no, "_source": "wurth_b", "_bbox": bbox,
            "part_number": strip_callout(v),
            "height_mm": parse_mm(height),
            "fixing_type": fixing_from_name(lab),
            "_material": sub,            # NB: stamped/die-cast not in 2.1 baseplate schema yet
        })
    return out


def emit_accessory(cells, sub, page_no, bbox=None):
    pn = desc = ""
    for label, val in cells.items():
        L = label.lower()
        if "item" in L:
            pn = strip_callout(val)
        elif "descr" in L:
            desc = val
    d = desc.lower()
    atype = ("drill_bit" if "bit" in d else "restriction_clip" if ("clip" in d or "angle" in d)
             else "hinge_screw" if "screw" in d else "template" if "template" in d else None)
    return [{"family": "accessory", "_page": page_no, "_source": "wurth_b", "_bbox": bbox,
             "part_number": pn, "accessory_type": atype, "description": desc, "_subgroup": sub}]


# --- block-oriented page parse ---

def classify_row(row):
    if is_header(row):
        return "header"
    if any(is_sku(c[2]) for c in row):
        return "data"
    if len(row) == 1 and len(row[0][2]) == 1 and row[0][2].isalpha():
        return "skip"                                  # stray single-letter diagram callout
    txt = row_text(row)
    if txt and txt == txt.upper() and len(txt) > 3:
        return "banner"
    if row and row[0][2] in ("•", "·"):
        return "bullet"
    return "label"


def parse_page(page_no):
    page = fitz.open(PDF)[page_no - 1]
    W, H = page.rect.width, page.rect.height
    rows, bboxes = to_rows(clean_words(page))
    # normalize each row's bbox to 0..1 fractions of the page (render-size independent)
    nbox = [(round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4))
            for b in bboxes]
    cls = [classify_row(r) for r in rows]
    blocks, banner = [], None
    i, n = 0, len(rows)
    while i < n:
        c = cls[i]
        if c == "banner":
            banner = row_text(rows[i]); i += 1; continue
        if c == "header":
            # column-label rows = contiguous 'label' rows immediately ABOVE this header
            # (backward-look avoids one block's loop swallowing the next block's labels)
            k, labs = i - 1, []
            while k >= 0 and cls[k] == "label":
                labs.append(rows[k]); k -= 1
            label_rows = list(reversed(labs))[-2:]
            cols = name_columns(header_columns(rows[i]), label_rows)
            # block title = nearest descriptive label above the column-label run (skip bullets)
            t = k
            while t >= 0 and cls[t] in ("bullet", "skip"):
                t -= 1
            title = row_text(rows[t]) if (t >= 0 and cls[t] == "label") else None
            # block bullets = bullet lines above this header, up to the previous block boundary
            bk, bullets = i - 1, []
            while bk >= 0 and cls[bk] not in ("header", "banner", "data"):
                if cls[bk] == "bullet":
                    bullets.append(row_text(rows[bk]))
                bk -= 1
            bullets = list(reversed(bullets))
            j, sub, recs = i + 1, None, []
            while j < n and cls[j] not in ("header", "banner"):
                if cls[j] == "data":
                    recs.append((bind(rows[j], cols), sub, nbox[j]))   # cells, sub, row bbox
                elif cls[j] == "label":
                    sub = row_text(rows[j])
                j += 1
            fam = classify_block(cols, banner, recs[0][1] if recs else None)
            blocks.append({"family": fam, "banner": banner, "title": title, "bullets": bullets,
                           "columns": [c["label"] for c in cols], "cols": cols, "rows": recs})
            i = j; continue
        i += 1
    return blocks


EMIT = {"concealed_hinge": lambda cells, cols, sub, p, bbox=None: emit_hinge(cells, sub, p, bbox),
        "baseplate": lambda cells, cols, sub, p, bbox=None: emit_baseplate(cells, cols, sub, p, bbox),
        "accessory": lambda cells, cols, sub, p, bbox=None: emit_accessory(cells, sub, p, bbox)}


def run(page_no, label):
    print("=" * 84)
    print(f"PAGE {page_no} — {label}")
    print("=" * 84)
    for b in parse_page(page_no):
        if not b["rows"]:
            continue
        print(f"  [block] family={b['family']!r}  banner={b['banner']!r}")
        print(f"          columns={b['columns']}")
        emit = EMIT.get(b["family"])
        if not emit:
            print(f"          (no emitter for family {b['family']!r})")
            continue
        for cells, sub, bbox in b["rows"]:
            for rec in emit(cells, b["cols"], sub, page_no, bbox):
                s = " | ".join(f"{k}={v!r}" for k, v in rec.items() if k != "_bbox")
                print("      " + s.encode("ascii", "replace").decode())
        print()


if __name__ == "__main__":
    run(6, "Blum soft-close euro hinges")
    run(45, "Grass TIOMOS soft-close + accessory sub-tables")
    run(100, "Salice wing baseplates (multi-row header)")
