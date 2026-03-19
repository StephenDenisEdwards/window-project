"""Shared test data for drawer slide tests.

Loaded from sample-data/ JSON files. Re-exports named products so existing
test imports continue to work unchanged.
"""

from pathlib import Path

from engine_v2.families.drawer_slide.loader import load_from_json

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample-data"

ALL_SLIDES = load_from_json(DATA_DIR)

# Named exports for tests that reference specific products
BLUM_SLIDE_FULL = next(s for s in ALL_SLIDES if s.sku == "563H5330B")
GRASS_SLIDE = next(s for s in ALL_SLIDES if s.sku == "DWD-XP-533")
BUDGET_SLIDE = next(s for s in ALL_SLIDES if s.sku == "KV-8400-18")
CENTER_SLIDE = next(s for s in ALL_SLIDES if s.sku == "KV-CM-450")
