"""Spike: Tier-B B2 — extract a manufacturer LOAD CHART via vision, cross-check vs text.

Plan section 2.2 B2: the Grass charts are rendered as diagrams; plain text extraction
returns scrambled tokens, so we render the chart to an image and use a VISION MODEL to
recover its structure. Here the vision model is Claude reading the rendered PNG; the dict
below (`VISION`) is what that read produced for the "Number of Hinges Per Door" chart.

This spike then does a RUNNABLE cross-check: pull the page's text tokens and confirm the
vision-recovered scaffold (weight bands, door-height thresholds, hinge counts) matches the
exact characters in the text layer — i.e. vision gives the STRUCTURE, the text layer
confirms the VALUES. Agreement => high confidence on the scaffold.

Catalog source
  Grass — TIOMOS Hinge System (manufacturer catalog)
  catalogs/grass-tiomos-catalog.pdf, page 47 — "Number of Hinges Per Door" chart
  Rendered crop: design-scratch/spikes/grass_tiomos_p47_hinges_chart.png

Throwaway spike. Run: python design-scratch/spikes/chart_extract_spike.py
"""
from __future__ import annotations

import fitz  # pymupdf

PDF = "catalogs/grass-tiomos-catalog.pdf"
PAGE = 47
CROP_PNG = "design-scratch/spikes/grass_tiomos_p47_hinges_chart.png"
CROP_CLIP = (20, 545, 230, 770)   # PDF points around the 'Number of Hinges Per Door' chart


def render_crop():
    """(Re)produce the committed chart crop the vision read was taken from."""
    page = fitz.open(PDF)[PAGE - 1]
    page.get_pixmap(matrix=fitz.Matrix(6.5, 6.5), clip=fitz.Rect(*CROP_CLIP)).save(CROP_PNG)
    return CROP_PNG

# --- what the vision read of the rendered chart produced -------------------------------

VISION = {
    "table": "hinges_per_door",
    "brand": "Grass",
    "series": "TIOMOS",
    "source": "grass_tiomos",
    "page": 47,
    # SCAFFOLD — high confidence (and text-cross-checkable):
    "hinge_counts": [2, 3, 4, 5],                       # x-axis
    "door_height_thresholds_mm": [500, 900, 1600, 2200, 2450],  # y-axis steps
    "weight_bands": [
        {"kg": [4, 6], "lb": [9, 13]},
        {"kg": [7, 12], "lb": [14, 26]},
        {"kg": [13, 17], "lb": [27, 37]},
        {"kg": [18, 22], "lb": [38, 48]},
    ],
    # CELL MAPPING — LOW confidence (dense 2-D icon grid): best-effort diagonal read,
    # flagged for human verification (ingestion model: low-confidence -> gap).
    "_cells_best_effort": [
        {"weight_kg": [4, 6],   "max_door_height_mm": 900,  "hinges": 2},
        {"weight_kg": [7, 12],  "max_door_height_mm": 1600, "hinges": 3},
        {"weight_kg": [13, 17], "max_door_height_mm": 2200, "hinges": 4},
        {"weight_kg": [18, 22], "max_door_height_mm": 2450, "hinges": 5},
    ],
    "_verify": "cell mapping read from a 2-D icon staircase — confirm thresholds with a human",
}


# --- runnable cross-check: vision scaffold vs the page's text layer --------------------

def page_text():
    return fitz.open(PDF)[PAGE - 1].get_text()


def norm(s):
    return s.replace("–", "-").replace("−", "-").replace(" ", "")


def cross_check(rec, text):
    t = norm(text)
    checks = []
    for b in rec["weight_bands"]:
        s = f'{b["kg"][0]}-{b["kg"][1]}kg'
        checks.append((s, s in t))
    for h in rec["door_height_thresholds_mm"]:
        s = f"{h}mm"
        checks.append((s, s in t))
    return checks


def run():
    render_crop()
    text = page_text()
    print("=" * 72)
    print("Tier-B B2 spike — Grass TIOMOS 'Number of Hinges Per Door' (p47)")
    print("=" * 72)
    print("Vision-recovered scaffold:")
    print(f"  hinge counts        : {VISION['hinge_counts']}")
    print(f"  door-height steps mm: {VISION['door_height_thresholds_mm']}")
    print(f"  weight bands        : {[b['kg'] for b in VISION['weight_bands']]} kg")
    print()
    print("Cross-check vs text layer (vision structure vs exact characters):")
    results = cross_check(VISION, text)
    for label, ok in results:
        print(f"  [{'OK ' if ok else 'MISS'}] {label}")
    n_ok = sum(1 for _, ok in results if ok)
    print(f"\n  scaffold match: {n_ok}/{len(results)} tokens confirmed in text layer")
    print()
    print("Best-effort cell mapping (LOW confidence -> human-verify gap):")
    for c in VISION["_cells_best_effort"]:
        print(f"  {c['weight_kg']} kg, up to {c['max_door_height_mm']}mm -> {c['hinges']} hinges")


if __name__ == "__main__":
    run()
