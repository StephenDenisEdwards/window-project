"""Spike: Tier-B B2 — extract manufacturer LOAD CHARTS via vision, cross-check vs text.

Plan section 2.2 B2: the Grass charts are rendered as diagrams; plain text extraction
returns scrambled tokens, so we render each chart to an image and use a VISION MODEL to
recover its structure (here the vision model is Claude reading the rendered PNG; the
`VISION*` dicts are what those reads produced). A runnable cross-check then confirms the
recovered scaffold against the page's text layer.

Two charts (note: DIFFERENT UNITS between the two Grass lines):
  - Grass TIOMOS p47 'Number of Hinges Per Door'  — millimetres / kilograms
  - Grass NEXIS  p8  'Number of Hinges per Door'  — INCHES / POUNDS

Catalog sources
  catalogs/grass-tiomos-catalog.pdf p47 -> design-scratch/spikes/grass_tiomos_p47_hinges_chart.png
  catalogs/grass-nexis-catalog.pdf  p8  -> design-scratch/spikes/grass_nexis_p8_hinges_chart.png

Throwaway spike. Run: python design-scratch/spikes/chart_extract_spike.py
"""
from __future__ import annotations

import fitz  # pymupdf

# --- TIOMOS chart (mm / kg) -----------------------------------------------------------

VISION = {
    "table": "hinges_per_door", "brand": "Grass", "series": "TIOMOS",
    "source": "grass_tiomos", "pdf": "catalogs/grass-tiomos-catalog.pdf", "page": 47,
    "units": "mm/kg",
    "crop_png": "design-scratch/spikes/grass_tiomos_p47_hinges_chart.png",
    "crop_clip": (20, 545, 230, 770), "crop_zoom": 6.5,
    "hinge_counts": [2, 3, 4, 5],
    "door_height_thresholds_mm": [500, 900, 1600, 2200, 2450],
    "weight_bands": [
        {"kg": [4, 6], "lb": [9, 13]}, {"kg": [7, 12], "lb": [14, 26]},
        {"kg": [13, 17], "lb": [27, 37]}, {"kg": [18, 22], "lb": [38, 48]},
    ],
    # LOW confidence (dense 2-D icon grid) — best-effort, human-verify.
    "_cells_best_effort": [
        {"weight_kg": [4, 6],   "max_door_height_mm": 900,  "hinges": 2},
        {"weight_kg": [7, 12],  "max_door_height_mm": 1600, "hinges": 3},
        {"weight_kg": [13, 17], "max_door_height_mm": 2200, "hinges": 4},
        {"weight_kg": [18, 22], "max_door_height_mm": 2450, "hinges": 5},
    ],
    "_verify": "cell mapping read from a 2-D icon staircase — confirm thresholds with a human",
}

# --- NEXIS chart (INCHES / POUNDS — different units from TIOMOS) -----------------------

VISION_NEXIS = {
    "table": "hinges_per_door", "brand": "Grass", "series": "NEXIS",
    "source": "grass_nexis", "pdf": "catalogs/grass-nexis-catalog.pdf", "page": 8,
    "units": "inches/pounds",
    "crop_png": "design-scratch/spikes/grass_nexis_p8_hinges_chart.png",
    "crop_clip": (285, 210, 585, 380), "crop_zoom": 6.0,
    "hinge_counts": [2, 3, 4, 5],
    "door_height_in": [35, 56, 63, 84, 96],
    "door_height_mm": [889, 1422, 1600, 2134, 2438],     # normalized (in × 25.4)
    "weight_axis_lb": [10, 20, 30, 40, 50, 60],
    "example": "56in x 19lb -> 2 hinges (from page text)",
    # LOW confidence — weight/height cell boundaries approximate; anchored on the page's
    # worked example (56in/19lb -> 2). Human-verify.
    "_cells_best_effort": [
        {"weight_kg": [0, 11],  "max_door_height_mm": 1600, "hinges": 2},
        {"weight_kg": [11, 18], "max_door_height_mm": 1600, "hinges": 3},
        {"weight_kg": [0, 23],  "max_door_height_mm": 2134, "hinges": 4},
        {"weight_kg": [0, 27],  "max_door_height_mm": 2438, "hinges": 5},
    ],
    "_verify": "inches/pounds chart; cell weight/height boundaries approximate — human verify",
}

CHARTS = [VISION, VISION_NEXIS]


# --- render + cross-check -------------------------------------------------------------

def render_crop(chart):
    page = fitz.open(chart["pdf"])[chart["page"] - 1]
    z = chart["crop_zoom"]
    page.get_pixmap(matrix=fitz.Matrix(z, z), clip=fitz.Rect(*chart["crop_clip"])).save(chart["crop_png"])
    return chart["crop_png"]


def _norm(s):
    return (s.replace("–", "-").replace("−", "-").replace("”", '"').replace("“", '"')
            .replace(" ", "").lower())


def check_tokens(chart):
    """Scaffold tokens we expect to find verbatim in the page's text layer."""
    if chart["units"] == "mm/kg":
        toks = [f'{b["kg"][0]}-{b["kg"][1]}kg' for b in chart["weight_bands"]]
        toks += [f'{h}mm' for h in chart["door_height_thresholds_mm"]]
    else:  # inches/pounds
        toks = [f'{h}"' for h in chart["door_height_in"]] + ["pounds"]
    return toks


def cross_check(chart, text):
    t = _norm(text)
    return [(tok, _norm(tok) in t) for tok in check_tokens(chart)]


def run():
    for chart in CHARTS:
        render_crop(chart)
        text = fitz.open(chart["pdf"])[chart["page"] - 1].get_text()
        results = cross_check(chart, text)
        n_ok = sum(1 for _, ok in results if ok)
        print("=" * 72)
        print(f"B2 — {chart['brand']} {chart['series']} 'Number of Hinges per Door' "
              f"(p{chart['page']}, {chart['units']})")
        print("=" * 72)
        print(f"  scaffold cross-check vs text layer: {n_ok}/{len(results)} tokens confirmed")
        for tok, ok in results:
            print(f"    [{'OK ' if ok else 'MISS'}] {tok}".encode('ascii', 'replace').decode())
        print("  best-effort cells (LOW confidence -> human-verify gap):")
        for c in chart["_cells_best_effort"]:
            print(f"    {c['weight_kg']} kg, up to {c['max_door_height_mm']}mm -> {c['hinges']} hinges")
        print()


if __name__ == "__main__":
    run()
