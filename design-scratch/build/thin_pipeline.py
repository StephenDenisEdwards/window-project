"""First thin end-to-end build: catalogs -> product records -> answer eval items.

Composes the validated spikes into a minimal product DB and runs a handful of
eval_set.md items end to end:

  extract (B1 table parse, reused from table_extract_spike)        -> product nodes
  + reference table (B2 chart read, reused from chart_extract_spike) -> hinges_per_door
  + GF->F join key + light normalization                            -> tiny DB
  + a small query layer                                             -> answer eval items

Scope is deliberately thin: Würth Section B pages B-6 (Blum), B-45 (Grass TIOMOS),
B-100 (Salice baseplates) + the Grass TIOMOS p47 load chart. Prototype; lives in
design-scratch/build/. Run from repo root:  python design-scratch/build/thin_pipeline.py
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import sys

import fitz  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spikes"))
import table_extract_spike as tx   # noqa: E402  (B1 extraction)
import chart_extract_spike as cx   # noqa: E402  (B2 chart read)
import image_extract_spike as ix   # noqa: E402  (product photos)

SECTION_B = list(range(1, 105))   # all of Section B (104 pp), not a 3-page slice
DB_PATH = os.path.join(os.path.dirname(__file__), "product_db.json")

# Resolve a record's `_source` code -> the actual catalog PDF (makes the DB self-describing:
# record._source -> SOURCES[code].pdf, + _page + _bbox = a renderable (catalog, page, region)).
SOURCES = {
    "wurth_b": {"pdf": "catalogs/wurth-baer-section-b-concealed-hinges.pdf",
                "label": "Würth Baer — Section B (Concealed Hinges)", "page_label": "B-{n}"},
    "wurth_c": {"pdf": "catalogs/Wurth_Baer_Section_C.pdf",
                "label": "Würth Baer — Section C (Lift Systems & Semi-Concealed)", "page_label": "C-{n}"},
    "grass_tiomos": {"pdf": "catalogs/grass-tiomos-catalog.pdf",
                     "label": "Grass TIOMOS", "page_label": "p{n}"},
    "grass_nexis": {"pdf": "catalogs/grass-nexis-catalog.pdf",
                    "label": "Grass NEXIS", "page_label": "p{n}"},
}


# --- normalization / join ---

def manufacturer_pn(pn):
    return pn[2:] if pn.startswith("GF") else pn          # GFF028... -> F028...


def part_core(pn):
    return re.sub(r"\D", "", manufacturer_pn(pn))         # numeric join key


def overlay_class(rec):
    if rec.get("overlay_class"):
        return rec["overlay_class"]
    sub = (rec.get("_subgroup") or "").lower()             # TIOMOS: overlay is a sub-group
    if "half" in sub:
        return "half"
    if "inset" in sub:
        return "inset"
    if "overlay" in sub:
        return "full"
    return None


def norm_enum(v):
    return v.lower().replace("-", "_").replace(" ", "_") if isinstance(v, str) else v


def citation(rec):
    src, pg = rec.get("_source"), rec.get("_page")
    return f"{src}:B-{pg}" if src == "wurth_b" else f"{src}:p{pg}"


# --- extract + build ---

def derive_brand_series(banner):
    """Bucket-B fill: brand/series are in the all-caps banner the router already reads."""
    b = (banner or "").upper()
    brand = ("Blum" if "BLUM" in b else "Grass" if "GRASS" in b
             else "Salice" if "SALICE" in b else "Pro" if b.startswith("PRO") else None)
    series = ("CLIP top BLUMOTION" if "BLUMOTION" in b
              else "TIOMOS" if "TIOMOS" in b
              else "NEXIS" if "NEXIS" in b else None)
    return brand, series


def page_prose(page_no):
    """Bucket-B fill: light pass over the page's prose bullets (not table cells)."""
    t = fitz.open(tx.PDF)[page_no - 1].get_text()
    info = {}
    m = re.search(r"door thickness(?:es)?\s+up to[^()]*\((\d+)\s*mm\)", t, re.I)
    if m:
        info["max_door_thickness_mm"] = int(m.group(1))
    certs = [c for c in ("ANSI", "BIFMA", "KCMA", "BHMA") if c in t]
    if certs:
        info["certifications"] = certs
    return info


def page_hinge_angle(page_no):
    """TIOMOS/NEXIS opening angle lives in the page heading ('110° Tiomos … Hinges'),
    not a table column. Guarded to the series name so it ignores the restriction-clip '85°'."""
    t = fitz.open(tx.PDF)[page_no - 1].get_text()
    m = re.search(r"(\d{2,3})\s*[°º]\s*(?:Tiomos|Nexis)", t, re.I)
    return int(m.group(1)) if m else None


def baseplate_compat(page_no):
    """Parse 'compatible with all Salice hinges Series F and Series B' -> ['Series B','Series F'].
    Page-level: fine here because the page is single-brand and both blocks share compatibility."""
    t = fitz.open(tx.PDF)[page_no - 1].get_text()
    letters = sorted(set(re.findall(r"[Ss]eries\s+([A-Z])\b", t)))
    return [f"Series {x}" for x in letters]


def cam_from_title(title):
    t = (title or "").lower()
    return "single_cam" if "single cam" in t else "two_cam" if "two cam" in t else None


def series_from_title(title):
    return "CLIP top BLUMOTION" if "BLUMOTION" in (title or "").upper() else None


def overlay_mm(text):
    m = re.search(r"\((\d+)\s*mm\)", text or "")   # e.g. "...Up to 7/8\" (22mm) Overlay"
    return int(m.group(1)) if m else None


def overlay_mm_from_bullets(bullets):
    for b in bullets or []:                         # e.g. "• For door overlays up to 22mm"
        m = re.search(r"overlays?\s+up to\s+(\d+)\s*mm", b, re.I)
        if m:
            return int(m.group(1))
    return None


def extract_page(page_no):
    out = []
    blocks = tx.parse_page(page_no)
    images = ix.link_images(tx.PDF, page_no, blocks, "wurth_b")   # block_index -> photo
    for bi, b in enumerate(blocks):
        emit = tx.EMIT.get(b["family"])
        if not emit:
            continue
        brand, series = derive_brand_series(b["banner"])
        title = b.get("title")
        wing = "WING" in (b["banner"] or "").upper()
        cam = cam_from_title(title)
        img = images.get(bi)                          # representative block photo (or None)
        for cells, sub, bbox in b["rows"]:
            for r in emit(cells, b["cols"], sub, page_no, bbox):
                if brand:
                    r["brand"] = brand
                if r["family"] == "concealed_hinge":
                    s = series or series_from_title(title)      # Blum series is in the title
                    if s:
                        r["series"] = s
                    # overlay-mm: TIOMOS in the sub-group; Blum in this block's own bullet
                    om = overlay_mm(r.get("_subgroup")) or overlay_mm_from_bullets(b.get("bullets"))
                    r["_overlay_on_page"] = om is not None       # block-level: stated for this block?
                    if om:
                        r["overlay_max_mm"] = om
                if r["family"] == "baseplate":
                    if wing:
                        r["plate_style"] = "wing"
                    if cam:                                       # single/two cam from the title
                        r["cam_adjustment"] = cam
                if img:
                    r["_image"] = img                             # block-level representative photo
                out.append(r)
    return out


def build_db():
    products, quarantine = {}, []
    for p in SECTION_B:
        prose = page_prose(p)
        bp_series = baseplate_compat(p)
        hinge_angle = page_hinge_angle(p)
        for r in extract_page(p):
            pn = r.get("part_number")
            if not pn:                                     # identity gap -> quarantine
                quarantine.append(r)
                continue
            r["part_number_core"] = part_core(pn)
            r["manufacturer_pn"] = manufacturer_pn(pn)
            r["overlay_class"] = overlay_class(r)
            if "_material" in r:
                r["material"] = norm_enum(r["_material"])
            if r["family"] == "concealed_hinge":           # page-level prose facts
                for k, v in prose.items():
                    r.setdefault(k, v)
                if r.get("opening_angle_deg") is None and hinge_angle:  # TIOMOS angle from heading
                    r["opening_angle_deg"] = hinge_angle
            if r["family"] == "baseplate" and bp_series:
                r.setdefault("compatible_hinge_series", bp_series)
            if r["family"] == "accessory" and r.get("accessory_type") == "restriction_clip":
                # NB: catalog writes degrees as º (U+00BA, ordinal indicator), not ° (U+00B0)
                # — so match the number, not the degree glyph. (Tier-A unicode normalization.)
                m = re.search(r"(\d+)", r.get("description", ""))
                if m:
                    r["restricts_angle_to_deg"] = int(m.group(1))
            products[pn] = r
    charts = {f"{c['brand']}/{c['series']}": c for c in cx.CHARTS}  # TIOMOS + NEXIS
    return {"products": products, "reference": {"hinges_per_door": charts},
            "quarantine": quarantine, "sources": SOURCES}


# --- persistence (build once, query many) ---

def save_db(db, path=DB_PATH):
    """Write the DB to JSON. Deterministic (sorted keys, no timestamp) so a committed
    file has stable diffs; UTF-8 so units (°, ″) stay readable."""
    doc = {
        "meta": {
            "build": "thin_pipeline",
            "sources": ["wurth_b:B-6", "wurth_b:B-45", "wurth_b:B-100", "grass_tiomos:p47"],
            "product_count": len(db["products"]),
        },
        "sources": db["sources"],
        "products": db["products"],
        "reference_tables": db["reference"],
        "quarantine": db["quarantine"],
    }
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def load_db(path=DB_PATH):
    with io.open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return {"products": doc["products"], "reference": doc["reference_tables"],
            "quarantine": doc.get("quarantine", []), "sources": doc.get("sources", {})}


# --- gap report (the §2.4 gaps queue) ---

GAP_PATH = os.path.join(os.path.dirname(__file__), "gap_report.json")

# Fields the catalog never carries (on ANY page) -> 'absent_in_catalog'.
# NB: there is no per-hinge weight field — the catalog expresses load as the series-level
# hinges-per-door chart (reference table), not a per-hinge kg. See weight_model.md.
ABSENT = {
    "concealed_hinge": {"price_usd"},
    "baseplate": {"price_usd"},
    "accessory": {"price_usd"},
}

# Evidence that a field's data is physically on the page. Lets us split
# 'not_on_page' (evidence missing on this product's page) from
# 'unparsed' (evidence present -> data is there, we just didn't pull it = the real to-do).
EVIDENCE = {
    "cup_depth_mm": r"cup\s*depth",
    "certifications": r"ANSI|BIFMA|KCMA|BHMA",
    "application": r"blind corner|angled|zero protrusion|narrow aluminum",
    "boring_pattern_mm": r"boring",
    "max_door_thickness_mm": r"door thickness",
    "overlay_max_mm": r"overlays?\s+up to\s+\d|\(\d+\s*mm\)",
    "compatible_hinge_series": r"series\s+[a-z]\b|compatible with all",
    "opening_angle_deg": r"\b\d{2,3}\s*[°º]",
    "series": r"BLUMOTION|TIOMOS|NEXIS|CLIP top",
}


def expected_fields(r):
    """Conditional per-record expectations — don't demand fields that don't apply."""
    fam = r["family"]
    if fam == "concealed_hinge":
        # no max_door_weight_kg: load is the series-level hinges-per-door chart, not a
        # per-hinge field (see weight_model.md)
        fields = ["brand", "series", "opening_angle_deg", "overlay_class",
                  "fixing", "closing_type", "boring_pattern_mm", "max_door_thickness_mm",
                  "cup_depth_mm", "certifications", "application", "price_usd"]
        if r.get("overlay_class") == "full":        # only full overlay has a max-overlay-mm
            fields.insert(4, "overlay_max_mm")
        return fields
    if fam == "baseplate":
        return ["brand", "height_mm", "plate_style", "fixing_type", "material",
                "cam_adjustment", "compatible_hinge_series", "price_usd"]
    if fam == "accessory":
        f = ["brand", "accessory_type", "description", "price_usd"]
        if r.get("accessory_type") == "restriction_clip":   # only clips have a restriction angle
            f.append("restricts_angle_to_deg")
        return f
    return []


_PAGE_TEXT = {}


def _page_text(source, page):
    if source != "wurth_b" or page is None:
        return ""
    if page not in _PAGE_TEXT:
        _PAGE_TEXT[page] = fitz.open(tx.PDF)[page - 1].get_text()
    return _PAGE_TEXT[page]


def classify_gap(field, fam, page_text):
    if field in ABSENT.get(fam, set()):
        return "absent_in_catalog"          # the source never has it
    pat = EVIDENCE.get(field)
    if pat is None:
        return "unparsed"                    # structural field that should have been filled
    return "unparsed" if re.search(pat, page_text, re.I) else "not_on_page"


def generate_gap_report(db, path=GAP_PATH):
    gaps = []
    for pn, r in db["products"].items():
        pt = _page_text(r.get("_source"), r.get("_page"))
        for f in expected_fields(r):
            if r.get(f) in (None, "", []):
                if f == "overlay_max_mm":            # block-aware: did this block state it?
                    kind = "unparsed" if r.get("_overlay_on_page") else "not_on_page"
                else:
                    kind = classify_gap(f, r["family"], pt)
                gaps.append({"part_number": pn, "family": r["family"], "field": f,
                             "kind": kind, "cite": citation(r)})
    for key, chart in db["reference"]["hinges_per_door"].items():
        if chart.get("_verify"):
            gaps.append({"part_number": None, "family": f"reference:hinges_per_door[{key}]",
                         "field": "_cells_best_effort", "kind": "low_confidence",
                         "cite": f"{chart['source']}:p{chart['page']}"})
    by_kind = collections.Counter(g["kind"] for g in gaps)
    actionable = collections.Counter(
        f"{g['family']}.{g['field']}" for g in gaps if g["kind"] == "unparsed")
    doc = {"meta": {"total_gaps": len(gaps), "by_kind": dict(by_kind),
                    "actionable_unparsed": sum(by_kind[k] for k in ["unparsed"])},
           "gaps": gaps}
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path, by_kind, actionable


# --- query layer ---

def get(db, pn):
    return db["products"].get(pn)


def find(db, **flt):
    out = []
    for r in db["products"].values():
        if all((str(r.get(k)).lower() == str(v).lower()) for k, v in flt.items()):
            out.append(r)
    return out


def hinges_for(db, height_mm, weight_kg, brand="Grass", series="TIOMOS"):
    chart = db["reference"]["hinges_per_door"].get(f"{brand}/{series}")
    if not chart:
        return None                       # no chart extracted for this series yet
    for c in chart["_cells_best_effort"]:
        lo, hi = c["weight_kg"]
        if lo <= weight_kg <= hi and height_mm <= c["max_door_height_mm"]:
            return c["hinges"]
    return None


# --- eval runner (a slice of eval_set.md) ---

def run_eval(db):
    rows = []

    def check(eid, ok, detail):
        rows.append((eid, "PASS" if ok else "FAIL", detail))

    # EX1 — exact lookup (now incl. brand from banner + thickness from prose bullet)
    r = get(db, "BP71B3580")
    ok = bool(r) and r.get("opening_angle_deg") == 110 and r.get("overlay_class") == "full" \
        and r.get("fixing") == "dowel" and r.get("closing_type") == "soft" \
        and r.get("brand") == "Blum" and r.get("max_door_thickness_mm") == 26
    check("EX1", ok, f"{citation(r)} | brand={r and r.get('brand')} "
                     f"thickness={r and r.get('max_door_thickness_mm')}mm")

    # EX2 — cross-source GF->F resolution (derived, no Grass page extracted in thin build)
    r = get(db, "GFF028138341228")
    ok = bool(r) and r["manufacturer_pn"] == "F028138341228" and r["part_number_core"] == "028138341228" \
        and r.get("opening_angle_deg") == 110           # from the page heading, not a column
    check("EX2", ok, f"{citation(r)} | mfr_pn={r and r['manufacturer_pn']} angle={r and r.get('opening_angle_deg')}")

    # EX3 — baseplate lookup
    r = get(db, "UBBAV4L09F16")
    ok = bool(r) and r.get("family") == "baseplate" and r.get("height_mm") == 0 \
        and r.get("fixing_type") == "split_dowel" and r.get("material") == "stamped_steel"
    check("EX3", ok, f"{citation(r)} | {r and (r.get('height_mm'), r.get('fixing_type'), r.get('material'))}")

    # SF1 — spec filter (expect BP71B3580 among matches; 110 vs 110+ is ambiguous)
    res = find(db, family="concealed_hinge", opening_angle_deg=110,
               overlay_class="full", fixing="dowel", closing_type="soft")
    skus = [x["part_number"] for x in res]
    check("SF1", "BP71B3580" in skus, f"matches={skus}  (ambiguous: 110 vs 110+ needs overlay-mm)")

    # SF3 — Grass TIOMOS full overlay, screw-on, 45mm, 22mm overlay (overlay-mm disambiguates)
    res = find(db, family="concealed_hinge", overlay_class="full", fixing="screw_on",
               boring_pattern_mm="45mm", overlay_max_mm=22, opening_angle_deg=110)
    skus = [x["part_number"] for x in res]
    check("SF3", "GFF028138519228" in skus,
          f"matches={skus}  (spec matches >1 across full Section B -> membership check)")

    # CC1 — baseplate compatible with a Series F hinge (uses the newly-parsed field)
    res = [x for x in find(db, family="baseplate", height_mm=0,
                           fixing_type="premounted_euro_screw", cam_adjustment="single_cam")
           if "Series F" in (x.get("compatible_hinge_series") or [])]
    check("CC1", [x["part_number"] for x in res] == ["UBBAVGL09F16"],
          f"{[x['part_number'] for x in res]} compatible_hinge_series checked")

    # CC2 — completeness: 0mm Salice SINGLE-CAM stamped wing baseplates by fixing
    res = find(db, family="baseplate", height_mm=0, material="stamped_steel", cam_adjustment="single_cam")
    by_fix = {x["fixing_type"]: x["part_number"] for x in res}
    ok = by_fix.get("wood_screw") == "UBBAV3L09F" and by_fix.get("premounted_euro_screw") == "UBBAVGL09F16" \
        and by_fix.get("split_dowel") == "UBBAV4L09F16"
    check("CC2", ok, f"{by_fix}  (cam_adjustment now disambiguates V vs R series)")

    # WF1 — weight feasibility from the load chart
    n = hinges_for(db, 1500, 11)
    check("WF1", n == 3, f"1500mm/11kg -> {n} hinges  (B2 low-confidence cell read)")

    # WF3 — Nexis weight feasibility (its chart is in inches/pounds; page example 56in/19lb)
    n = hinges_for(db, 1422, 9, series="NEXIS")   # 56in / ~19lb
    check("WF3", n == 2, f"NEXIS 1422mm/9kg -> {n} hinges  (matches the p8 worked example)")

    # SD1 — should-decline: no per-hinge weight rating in the corpus
    r = get(db, "BP71B3580")
    ok = bool(r) and "max_door_weight_kg" not in r          # correct = decline
    check("SD1", ok, "no per-hinge kg field present -> correctly declines (honesty)")

    # SD3 — should-decline: no Blum hinges-per-door chart in our catalogs (sourcing gap)
    n = hinges_for(db, 2000, 25, brand="Blum", series="CLIP top BLUMOTION")
    check("SD3", n is None, "no Blum chart -> hinges_for returns None -> correctly declines")

    return rows


def main():
    db = build_db()
    path = save_db(db)                 # persist...
    db = load_db(path)                 # ...then query the reloaded file (round-trip)
    prods = db["products"]
    fams = {}
    for r in prods.values():
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    print("=" * 78)
    print("BUILD — Würth Section B (all 104 pp) + Grass TIOMOS p47 & NEXIS p8 charts")
    print("=" * 78)
    print(f"products: {len(prods)}  by family: {fams}  | reference tables: "
          f"{list(db['reference'])}  | quarantined: {len(db['quarantine'])}")
    print(f"saved DB -> {os.path.relpath(path)}  ({os.path.getsize(path)} bytes)")
    print()
    rows = run_eval(db)
    npass = sum(1 for _, s, _ in rows if s == "PASS")
    for eid, status, detail in rows:
        print(f"  [{status}] {eid:<4} {detail}".encode("ascii", "replace").decode())
    print(f"\n  eval: {npass}/{len(rows)} passed")

    gpath, by_kind, actionable = generate_gap_report(db)
    print(f"\n  gap report -> {os.path.relpath(gpath)}  ({sum(by_kind.values())} fields empty)")
    print(f"    by reason: {dict(by_kind)}")
    print(f"    ACTIONABLE (unparsed — on the page, not pulled yet):")
    for name, n in actionable.most_common():
        print(f"      {name:<40} {n}")


if __name__ == "__main__":
    main()
