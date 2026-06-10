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

import fitz  # pymupdf — TEC pages need positional (word-level) reading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spikes"))
import table_extract_spike as tx  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "products.json")   # the single product database

# page -> taxonomy section (wurth_b), so a product's `section` always links to a taxonomy node
# (parse_page's per-block banner can diverge, e.g. a 'CLIP top BLUMOTION' divider read as a banner)
_TAXJSON = json.load(io.open(os.path.join(os.path.dirname(__file__), "..", "taxonomy.json"), encoding="utf-8"))
_SECTION_BY_PAGE = {}
for _g in _TAXJSON["groups"]:
    if _g["name"] == "Sections":
        for _t in _g["types"]:
            for _s in _t["sections"]:
                if _s["catalog"] == "wurth_b":
                    for _pg in range(_s["pages"][0], _s["pages"][1] + 1):
                        _SECTION_BY_PAGE[_pg] = _s["section"]


def _section_for(page):
    return _SECTION_BY_PAGE.get(page)


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


def extract_blum_euro():
    """Blum euro hinges with the standard Item#/Opening/Overlay/Fixing/Close table — CLIP/CLIP-top
    (6,7,10-13) plus zero-protrusion (8), blind-corner/aluminium (9) and bi-fold/blind-corner
    specialty (14,15). Guard on the Opening column so the angled (Degree) and Onyx (Description)
    tables on these pages are left to their own extractors."""
    pages = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    products, quarantine = [], []
    for p in pages:
        for b in tx.parse_page(p):
            if b["family"] != "concealed_hinge" or "BLUM" not in (b["banner"] or "").upper():
                continue
            if not any("opening" in c["label"].lower() for c in (b.get("cols") or [])):
                continue                               # standard euro hinge table only
            for cells, sub, bbox in b["rows"]:
                rec = tx.emit_hinge(cells, sub, p, bbox)[0]
                pn = rec.get("part_number")
                if not clean_sku(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue                       # GATE: garbage never emitted
                ov = rec.get("overlay_class")
                prod = {
                    "part_number": pn, "brand": "Blum", "family": "hinge",
                    "product_type": "concealed_hinge", "section": _section_for(p) or b["banner"],
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


TEC_SKU = re.compile(r"GF\d{4,7}[A-Z]?-1[456]")   # TEC hinge: GF<digits><opt letter>-14/15/16 (-42 = accessory)


def _mount_of(label):
    l = (label or "").lower()
    return "wrap_around" if "wrap" in l else "face_mount" if "face" in l else "side_mount" if "side" in l else None


def _fixing_tec(v):
    v = (v or "").lower()
    return "dowel" if "dowel" in v else "screw_on" if "screw" in v else None


def extract_grass_tec():
    """Grass TEC hinges — Section B p82-88. These are side-by-side dual tables: the cell parser
    keys cells by header name, so the duplicated columns collide and the right-column SKUs are
    LOST (e.g. B-85: 25 in the page, 7 in cells). So read positionally instead: each block's
    `cols` give exact x-bands; recover every SKU from the word layer within those bands and bind
    overlay/fixing/mount/closing/angle. Column-triplet blocks only -> 2-col accessory blocks
    (restriction clip, spacer, screws) skip automatically. Closing comes from the column header
    when it names it (B-84 face-mount Soft/Self columns), else from the banner."""
    pages = [82, 83, 84, 85, 86, 87, 88]
    products, quarantine = [], []
    doc = fitz.open(tx.PDF)
    blocks_by_page = {p: tx.parse_page(p) for p in pages}
    section_ang = {}                                       # 'NNN Opening Angle' header is section-wide
    for bl in blocks_by_page.values():
        for bb in bl:
            m = re.search(r"(\d{2,3})\s*[°º?]?\s*opening", (bb.get("title") or "").lower())
            if m:
                section_ang.setdefault(bb["banner"], int(m.group(1)))
    for p in pages:
        page = doc[p - 1]
        W, H = page.rect.width, page.rect.height
        words = [w for w in page.get_text("words") if w[4].strip()]
        for b in blocks_by_page[p]:
            cols = b.get("cols") or []
            if b["family"] != "concealed_hinge" or "TEC" not in (b["banner"] or "").upper() \
                    or len(cols) < 3 or len(cols) % 3 != 0:
                continue                                   # hinge column-triplet tables only
            ys = [(r[2][1], r[2][3]) for r in b["rows"] if r[2]]
            if not ys:
                continue
            y0 = min(a for a, _ in ys) * H - 8
            y1 = max(z for _, z in ys) * H + 8
            ang = section_ang.get(b["banner"])
            close_banner = _close_tiomos(b["banner"])      # SOFT/SELF/FREE from the banner
            win = [w for w in words if y0 <= (w[1] + w[3]) / 2 <= y1]

            def near(col, yc):                              # value word in col's x-band at row yc
                best = None
                for w in win:
                    if col["lo"] - 22 <= (w[0] + w[2]) / 2 <= col["hi"] + 22 and abs((w[1] + w[3]) / 2 - yc) <= 5:
                        d = abs((w[1] + w[3]) / 2 - yc)
                        if best is None or d < best[0]:
                            best = (d, w[4])
                return best[1] if best else None

            for g in range(len(cols) // 3):
                c0, c1, c2 = cols[3 * g], cols[3 * g + 1], cols[3 * g + 2]
                mount = _mount_of(c0["label"])
                bm = re.search(r"(\d{2})\s*mm", (c0["label"] + " " + c1["label"]).lower())
                boring = int(bm.group(1)) if bm else None
                close_hdr = _close_tiomos(c2["label"])     # B-84: closing is in the column header
                for w in win:
                    if not TEC_SKU.fullmatch(w[4]) or not (c0["lo"] - 22 <= (w[0] + w[2]) / 2 <= c0["hi"] + 22):
                        continue
                    yc = (w[1] + w[3]) / 2
                    fx = near(c2, yc)
                    products.append({
                        "part_number": w[4], "brand": "Grass", "family": "hinge",
                        "product_type": "concealed_hinge", "section": b["banner"], "series": "TEC",
                        "mount_type": mount, "boring_pattern_mm": boring,
                        "overlay_in": (near(c1, yc) or "").strip() or None,
                        "fixing": _fixing_tec(fx), "fixing_raw": (fx or "").strip() or None,
                        "closing_type": close_hdr or close_banner,
                        "opening_angle_deg": ang,
                        "_source": "wurth_b", "_page": p,
                        "_bbox": [round(w[0] / W, 4), round(w[1] / H, 4), round(w[2] / W, 4), round(w[3] / H, 4)],
                    })
    return products, quarantine


SALICE_SKU = re.compile(r"UBBA[0-9A-Z]{4,12}")


def clean_salice(pn):
    """Validation gate for Salice baseplate SKUs: UBBA + 4-12 alnum, no prose."""
    return bool(pn) and pn == pn.upper() and " " not in pn and bool(SALICE_SKU.fullmatch(pn))


def _salice_material(sub):
    s = (sub or "").lower()
    return "die_cast_steel" if "die" in s else "stamped_steel" if "stamp" in s else None


def _adjustment(t):
    t = (t or "").lower()
    return "two_cam" if "two cam" in t else "single_cam" if "single cam" in t else None


def extract_salice_baseplate():
    """Salice baseplates — Section B p100-101. Two shapes:
    B-100 (wing) is a SKU MATRIX: each row has a Plate Height then one SKU per attachment column
    (Wood / Pre-Mounted Euro / Expanding Dowels) -> explode to one product per non-empty cell,
    fixing from the column header, material from the sub-group, adjustment from the title.
    B-101 (face frame) is a simple Plate Height/Adjustment/Application/Item# table.
    Gates on a Height column (excludes the drill-bit Item#/Description block)."""
    pages = [100, 101]
    products, quarantine = [], []
    for p in pages:
        for b in tx.parse_page(p):
            if b["family"] != "baseplate" or "SALICE" not in (b["banner"] or "").upper():
                continue
            labels = [c["label"] for c in (b.get("cols") or [])]
            height_col = next((l for l in labels if "height" in l.lower()), None)
            if not height_col:                          # excludes the Item#/Description drill block
                continue
            item_col = next((l for l in labels if "item" in l.lower()), None)
            adj_title = _adjustment(b.get("title"))
            for cells, sub, bbox in b["rows"]:
                material = _salice_material(sub)
                height = _height_mm(cells.get(height_col))
                if item_col:                            # SIMPLE (B-101): one SKU per row
                    emit = [(tx.strip_callout(cells.get(item_col, "") or ""), None)]
                    adjustment = _adjustment(_cell(cells, "adjust")) or adj_title
                    application = (_cell(cells, "applicat") or "").strip().lower() or None
                else:                                   # MATRIX (B-100): one SKU per attachment column
                    emit = [(tx.strip_callout(cells.get(l, "") or ""), l) for l in labels if l != height_col]
                    adjustment, application = adj_title, None
                for pn, fixing_hdr in emit:
                    if not clean_salice(pn):
                        if pn and pn not in ("", "-"):
                            quarantine.append({"page": p, "raw": pn, "bbox": bbox})
                        continue                        # empty matrix cells are absent products, not errors
                    products.append({
                        "part_number": pn, "brand": "Salice", "family": "baseplate",
                        "product_type": "baseplate", "section": b["banner"],
                        "height_mm": height, "material": material,
                        "adjustment": adjustment, "application": application,
                        "fixing_type": _fixing_baseplate(fixing_hdr) if fixing_hdr else None,
                        "fixing_raw": fixing_hdr,
                        "_source": "wurth_b", "_page": p, "_bbox": bbox,
                    })
    return products, quarantine


def _tiomos_specialty_titles(page):
    """Recover the full multi-line table headers positionally (parse_page truncates them).
    Returns [(y_norm, variant, opening_angle)] — variant joins the 'Tiomos ...' line with its
    wrapped continuation; angle from the 'NNN° opening angle' bullet, else the title number."""
    H = page.rect.height
    lines = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if t:
                lines.append((ln["bbox"][1], t))
    lines.sort(key=lambda x: x[0])
    anchors = [i for i, (y, t) in enumerate(lines) if t.lower().startswith("tiomos")]
    out = []
    for k, i in enumerate(anchors):
        y = lines[i][0]
        end = lines[anchors[k + 1]][0] if k + 1 < len(anchors) else 1e9
        parts, lasty = [lines[i][1]], y
        for yy, tt in lines[i + 1:]:                        # join wrapped continuation lines
            if yy >= end or yy - lasty > 20 or len(parts) >= 3 or not (tt[0].isalnum() or tt[0] == "("):
                break
            parts.append(tt)
            lasty = yy
        variant = re.sub(r"\s+", " ", re.sub(r"[^\x20-\x7e]", " ", " ".join(parts))).strip()
        variant = " ".join(w for w in variant.split()    # drop stray single-letter diagram callouts (A,B,C..)
                           if not (len(w) == 1 and w.isalpha() and w.isupper()))
        ang = None
        for yy, tt in lines:
            if y <= yy < end:
                m = re.search(r"(\d{2,3})\s*[°º?]\s*opening", re.sub(r"[^\x20-\x7e]", " ", tt).lower())
                if m:
                    ang = int(m.group(1))
                    break
        if ang is None:
            m = re.search(r"tiomos\s+(?:m\d+\s+)?(\d{2,3})", variant.lower())
            ang = int(m.group(1)) if m else None
        out.append((y / H, variant, ang))
    return out


def extract_grass_tiomos_specialty():
    """Grass TIOMOS specialty hinges — Section B p53-58 (blind-corner, angle-corner, pie-cut,
    thick/thin-door). Same clean single-column shape as the TIOMOS euro hinges (Item#/Boring/
    Fixing/Close); gate on the Boring column (excludes the cover-cap Finish/Box-Qty + spacer
    Description blocks). The specialty sub-type + opening angle live in multi-line headers that
    parse_page truncates, so recover them positionally (_tiomos_specialty_titles) and assign by
    each row's y-position."""
    pages = range(53, 59)
    products, quarantine = [], []
    doc = fitz.open(tx.PDF)
    for p in pages:
        titles = _tiomos_specialty_titles(doc[p - 1])
        for b in tx.parse_page(p):
            if b["family"] != "concealed_hinge" or "TIOMOS" not in (b["banner"] or "").upper():
                continue
            labels = [c["label"].lower() for c in (b.get("cols") or [])]
            if not any("boring" in l for l in labels):     # hinge tables only
                continue
            for cells, sub, bbox in b["rows"]:
                pn = tx.strip_callout(cells.get("Item #", "") or "")
                if not clean_gff(pn):
                    quarantine.append({"page": p, "raw": cells, "bbox": bbox})
                    continue
                variant, ang = None, None                  # header whose y is just above this row
                for ty, var, ta in titles:
                    if ty <= bbox[1] + 0.001 and (variant is None or ty > best_y):
                        variant, ang, best_y = var, ta, ty
                fx_raw = (_cell(cells, "fixing") or "").strip() or None
                prod = {
                    "part_number": pn, "brand": "Grass", "family": "hinge",
                    "product_type": "concealed_hinge", "section": b["banner"], "series": "TIOMOS",
                    "variant": variant,                    # full specialty header (recovered positionally)
                    "overlay_class": None,                 # specialty: not a simple full/half/inset class
                    "boring_pattern": (_cell(cells, "boring") or "").strip() or None,
                    "fixing": _fixing_tiomos(fx_raw),
                    "closing_type": _close_tiomos(_cell(cells, "clos")),
                    "opening_angle_deg": ang,
                    "_source": "wurth_b", "_page": p, "_bbox": bbox,
                }
                if fx_raw and prod["fixing"] is None:
                    prod["fixing_raw"] = fx_raw
                products.append(prod)
    return products, quarantine


PRO_SKU = re.compile(r"DSPRO-[0-9A-Z]+")


def clean_pro(pn):
    """Validation gate for Pro baseplate SKUs: DSPRO-<alnum>, no prose."""
    return bool(pn) and pn == pn.upper() and " " not in pn and bool(PRO_SKU.fullmatch(pn))


def _pro_material(sub):
    s = (sub or "").lower()
    return "die_cast_steel" if ("diecast" in s or "die-cast" in s) else "steel" if "steel" in s else None


def extract_pro_baseplate():
    """Pro (house-brand) euro hinge baseplates — Section B p3. Simple Item#/Height/Fixing Type
    table with a plate-style sub-group (the face-frame sub-groups also encode Steel/Diecast).
    DSPRO- SKUs with callout letters to strip; gate on the Height column (excludes the drill block)."""
    products, quarantine = [], []
    for b in tx.parse_page(3):
        if b["family"] != "baseplate" or "PRO EURO" not in (b["banner"] or "").upper():
            continue
        labels = " ".join(c["label"].lower() for c in (b.get("cols") or []))
        if "height" not in labels:                      # excludes the Item#/Description drill block
            continue
        for cells, sub, bbox in b["rows"]:
            pn = tx.strip_callout(cells.get("Item #", "") or "")
            if not clean_pro(pn):
                quarantine.append({"page": 3, "raw": cells, "bbox": bbox})
                continue
            fx_raw = (_cell(cells, "fixing") or "").strip() or None
            products.append({
                "part_number": pn, "brand": "Pro", "family": "baseplate",
                "product_type": "baseplate", "section": b["banner"], "plate_style": sub,
                "height_mm": _height_mm(_cell(cells, "height")),
                "fixing_type": _fixing_baseplate(fx_raw), "fixing_raw": fx_raw,
                "material": _pro_material(sub),
                "_source": "wurth_b", "_page": 3, "_bbox": bbox,
            })
    return products, quarantine


NEXIS_SKU = re.compile(r"GF\d+\.\d+\.\d+\.\d+")        # NEXIS SKUs are dot-separated (parser can't read them)
_BORING = re.compile(r"^\d+(?:/\d+)?mm$")


def _nexis_close(t):
    t = t.lower()
    return "self" if "self-close" in t else "free" if "free-swing" in t else "soft" if "soft-close" in t else None


def _nexis_fixing(t):
    t = t.lower()
    return "dowel" if "dowel" in t else "impresso" if "impresso" in t else \
        "screw_on" if "screw-on" in t or "screw on" in t else None


def extract_grass_nexis():
    """Grass NEXIS hinges — Section B p67-70. NEXIS SKUs are dot-separated (GF138.322.73.0015),
    which parse_page's is_sku rejects, so it returns 0 rows. Read positionally instead: find each
    NEXIS SKU in the word layer and read its row (boring / fixing / close / box-qty). The gate is
    'has a boring pattern AND a close type' -> the box-qty-only accessory rows (GF514./GF641.
    cover caps & clips) are skipped. Opening angle comes from the section header (NNN° Hinges),
    assigned by row y-position."""
    products, quarantine = [], []
    doc = fitz.open(tx.PDF)
    for p in range(67, 71):
        page = doc[p - 1]
        W, H = page.rect.width, page.rect.height
        banner = next((b["banner"] for b in tx.parse_page(p)), "GRASS NEXIS SELF-CLOSE AND FREE SWING EURO HINGES")
        angles, overlays = [], []                      # (y_norm, angle) ; (y_norm, overlay_class, cranking)
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                t = re.sub(r"[^\x20-\x7e]", " ", "".join(s["text"] for s in ln["spans"])).lower()
                y = ln["bbox"][1] / H
                m = re.search(r"(\d{2,3})\s+hinges", t)            # page header 'NNN Hinges'
                if m and 90 <= int(m.group(1)) <= 180:
                    angles.append((y, int(m.group(1))))
                m2 = re.search(r"opening angle\s+(\d{2,3})", t)    # per-band override (e.g. inset 100)
                if m2 and 80 <= int(m2.group(1)) <= 180:
                    angles.append((y, int(m2.group(1))))
                ov = "full" if "full overlay" in t else "half" if "half overlay" in t \
                    else "inset" if "inset hinge" in t else None
                if ov:
                    cr = re.search(r"cranking\s+([\d.]+)", t)
                    overlays.append((y, ov, cr.group(1) if cr else None))

        def nearest(lst, y0n):                         # the band/header just above this row
            best, by = None, -1.0
            for it in lst:
                if it[0] <= y0n + 0.005 and it[0] > by:
                    best, by = it, it[0]
            return best

        words = [w for w in page.get_text("words") if w[4].strip()]
        for w in words:
            if not NEXIS_SKU.fullmatch(w[4]):
                continue
            yc = (w[1] + w[3]) / 2
            row = [x for x in words if abs((x[1] + x[3]) / 2 - yc) <= 5]
            rowtext = " ".join(x[4] for x in sorted(row, key=lambda x: x[0]))
            boring = next((x[4] for x in row if _BORING.match(x[4])), None)
            close = _nexis_close(rowtext)
            if not boring or not close:                # box-qty-only rows are accessories, not hinges
                continue
            y0n = w[1] / H
            a = nearest(angles, y0n)
            o = nearest(overlays, y0n)
            qty = next((x[4] for x in row if x[4].isdigit() and len(x[4]) >= 2), None)
            products.append({
                "part_number": w[4], "brand": "Grass", "family": "hinge",
                "product_type": "concealed_hinge", "section": banner, "series": "NEXIS",
                "overlay_class": o[1] if o else None, "cranking": o[2] if o else None,
                "boring_pattern": boring, "fixing": _nexis_fixing(rowtext), "closing_type": close,
                "opening_angle_deg": a[1] if a else None, "box_qty": int(qty) if qty else None,
                "_source": "wurth_b", "_page": p,
                "_bbox": [round(w[0] / W, 4), round(w[1] / H, 4), round(w[2] / W, 4), round(w[3] / H, 4)],
            })
    return products, quarantine


# add a new product type here once its extractor is written & verified
EXTRACTORS = [
    ("blum_euro", extract_blum_euro),
    ("blum_baseplate", extract_blum_baseplate),
    ("grass_tiomos", extract_grass_tiomos),
    ("grass_tiomos_baseplate", extract_grass_tiomos_baseplate),
    ("grass_tec", extract_grass_tec),
    ("salice_baseplate", extract_salice_baseplate),
    ("grass_tiomos_specialty", extract_grass_tiomos_specialty),
    ("pro_baseplate", extract_pro_baseplate),
    ("grass_nexis", extract_grass_nexis),
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
