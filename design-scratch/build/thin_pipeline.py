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

SECTION_B = [6, 45, 100]
DB_PATH = os.path.join(os.path.dirname(__file__), "product_db.json")


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


def cam_from_title(title):
    t = (title or "").lower()
    return "single_cam" if "single cam" in t else "two_cam" if "two cam" in t else None


def series_from_title(title):
    return "CLIP top BLUMOTION" if "BLUMOTION" in (title or "").upper() else None


def overlay_mm(text):
    m = re.search(r"\((\d+)\s*mm\)", text or "")   # e.g. "...Up to 7/8\" (22mm) Overlay"
    return int(m.group(1)) if m else None


def extract_page(page_no):
    out = []
    for b in tx.parse_page(page_no):
        emit = tx.EMIT.get(b["family"])
        if not emit:
            continue
        brand, series = derive_brand_series(b["banner"])
        title = b.get("title")
        wing = "WING" in (b["banner"] or "").upper()
        cam = cam_from_title(title)
        for cells, sub in b["rows"]:
            for r in emit(cells, b["cols"], sub, page_no):
                if brand:
                    r["brand"] = brand
                if r["family"] == "concealed_hinge":
                    s = series or series_from_title(title)      # Blum series is in the title
                    if s:
                        r["series"] = s
                    om = overlay_mm(r.get("_subgroup"))          # TIOMOS: overlay-mm in sub-group
                    if om:
                        r["overlay_max_mm"] = om
                if r["family"] == "baseplate":
                    if wing:
                        r["plate_style"] = "wing"
                    if cam:                                       # single/two cam from the title
                        r["cam_adjustment"] = cam
                out.append(r)
    return out


def build_db():
    products, quarantine = {}, []
    for p in SECTION_B:
        prose = page_prose(p)
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
            if r["family"] == "accessory" and r.get("accessory_type") == "restriction_clip":
                # NB: catalog writes degrees as º (U+00BA, ordinal indicator), not ° (U+00B0)
                # — so match the number, not the degree glyph. (Tier-A unicode normalization.)
                m = re.search(r"(\d+)", r.get("description", ""))
                if m:
                    r["restricts_angle_to_deg"] = int(m.group(1))
            products[pn] = r
    return {"products": products, "reference": {"hinges_per_door": cx.VISION},
            "quarantine": quarantine}


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
            "quarantine": doc.get("quarantine", [])}


# --- gap report (the §2.4 gaps queue) ---

GAP_PATH = os.path.join(os.path.dirname(__file__), "gap_report.json")

# fields the catalog genuinely does not carry -> 'absent' (sourcing / should-decline)
ABSENT_IN_CATALOG = {
    "concealed_hinge": ["max_door_weight_kg", "price_usd"],
    "baseplate": ["price_usd"],
    "accessory": ["price_usd"],
}
# fields that are on the page (extract when present) -> empty ones are 'extraction' gaps
EXPECTED = {
    "concealed_hinge": ["brand", "series", "opening_angle_deg", "overlay_class", "overlay_max_mm",
                        "fixing", "closing_type", "boring_pattern_mm", "max_door_thickness_mm",
                        "cup_depth_mm", "certifications", "application", "max_door_weight_kg", "price_usd"],
    "baseplate": ["brand", "series", "height_mm", "plate_style", "fixing_type", "material",
                  "cam_adjustment", "compatible_hinge_series", "price_usd"],
    "accessory": ["brand", "accessory_type", "for_series", "restricts_angle_to_deg", "color", "price_usd"],
}


def generate_gap_report(db, path=GAP_PATH):
    gaps = []
    for pn, r in db["products"].items():
        fam = r["family"]
        absent = set(ABSENT_IN_CATALOG.get(fam, []))
        for f in EXPECTED.get(fam, []):
            if r.get(f) in (None, "", []):
                gaps.append({
                    "part_number": pn, "family": fam, "field": f,
                    "kind": "absent" if f in absent else "extraction",
                    "cite": citation(r),
                })
    # low-confidence reference-table cells
    if db["reference"]["hinges_per_door"].get("_verify"):
        gaps.append({"part_number": None, "family": "reference:hinges_per_door",
                     "field": "_cells_best_effort", "kind": "low_confidence",
                     "cite": "grass_tiomos:p47"})
    by_kind = collections.Counter(g["kind"] for g in gaps)
    by_field = collections.Counter(f"{g['family']}.{g['field']}" for g in gaps)
    doc = {"meta": {"total_gaps": len(gaps), "by_kind": dict(by_kind)},
           "gaps": gaps}
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path, by_kind, by_field


# --- query layer ---

def get(db, pn):
    return db["products"].get(pn)


def find(db, **flt):
    out = []
    for r in db["products"].values():
        if all((str(r.get(k)).lower() == str(v).lower()) for k, v in flt.items()):
            out.append(r)
    return out


def hinges_for(db, height_mm, weight_kg):
    for c in db["reference"]["hinges_per_door"]["_cells_best_effort"]:
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
    ok = bool(r) and r["manufacturer_pn"] == "F028138341228" and r["part_number_core"] == "028138341228"
    check("EX2", ok, f"{citation(r)} | mfr_pn={r and r['manufacturer_pn']}")

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
    res = find(db, family="concealed_hinge", overlay_class="full",
               fixing="screw_on", boring_pattern_mm="45mm", overlay_max_mm=22)
    skus = [x["part_number"] for x in res]
    check("SF3", skus == ["GFF028138519228"], f"matches={skus}  (now unambiguous via overlay_max_mm)")

    # CC2 — completeness: 0mm Salice SINGLE-CAM stamped wing baseplates by fixing
    res = find(db, family="baseplate", height_mm=0, material="stamped_steel", cam_adjustment="single_cam")
    by_fix = {x["fixing_type"]: x["part_number"] for x in res}
    ok = by_fix.get("wood_screw") == "UBBAV3L09F" and by_fix.get("premounted_euro_screw") == "UBBAVGL09F16" \
        and by_fix.get("split_dowel") == "UBBAV4L09F16"
    check("CC2", ok, f"{by_fix}  (cam_adjustment now disambiguates V vs R series)")

    # WF1 — weight feasibility from the load chart
    n = hinges_for(db, 1500, 11)
    check("WF1", n == 3, f"1500mm/11kg -> {n} hinges  (B2 low-confidence cell read)")

    # SD1 — should-decline: no per-hinge weight rating in the corpus
    r = get(db, "BP71B3580")
    ok = bool(r) and "max_door_weight_kg" not in r          # correct = decline
    check("SD1", ok, "no per-hinge kg field present -> correctly declines (honesty)")

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
    print("THIN END-TO-END BUILD — Würth Section B (B-6, B-45, B-100) + Grass p47 chart")
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

    gpath, by_kind, by_field = generate_gap_report(db)
    print(f"\n  gap report -> {os.path.relpath(gpath)}  ({sum(by_kind.values())} gaps)")
    print(f"    by kind: {dict(by_kind)}")
    print("    top extraction gaps:")
    for name, n in by_field.most_common(8):
        if name.endswith(".price_usd") or ".max_door_weight_kg" in name:
            continue
        print(f"      {name:<40} {n}")


if __name__ == "__main__":
    main()
