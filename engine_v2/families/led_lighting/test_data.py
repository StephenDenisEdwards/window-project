"""Shared test data for LED lighting tests.

Loaded from sample-data/ JSON files. Re-exports named products so existing
test imports continue to work unchanged.
"""

from pathlib import Path

from engine_v2.families.led_lighting.loader import load_from_json

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample-data"

ALL_BARS, ALL_DRIVERS, ALL_DIMMERS = load_from_json(DATA_DIR)

# Named exports for tests that reference specific products
BAR_12V_5W = next(b for b in ALL_BARS if b.sku == "LED-BAR-12V-5W")
BAR_12V_10W = next(b for b in ALL_BARS if b.sku == "LED-BAR-12V-10W")
BAR_24V_15W = next(b for b in ALL_BARS if b.sku == "LED-BAR-24V-15W")
BAR_24V_8W_DIM = next(b for b in ALL_BARS if b.sku == "LED-BAR-24V-8W")
BAR_12V_LONG = next(b for b in ALL_BARS if b.sku == "LED-BAR-12V-LONG")

DRV_12V_30W = next(d for d in ALL_DRIVERS if d.sku == "DRV-12V-30W")
DRV_12V_15W_NODIM = next(d for d in ALL_DRIVERS if d.sku == "DRV-12V-15W-ND")
DRV_24V_60W = next(d for d in ALL_DRIVERS if d.sku == "DRV-24V-60W")
DRV_24V_20W = next(d for d in ALL_DRIVERS if d.sku == "DRV-24V-20W")

DIM_TRAILING_150W = next(d for d in ALL_DIMMERS if d.sku == "DIM-TE-150W")
DIM_0_10V_200W = next(d for d in ALL_DIMMERS if d.sku == "DIM-010V-200W")
DIM_TRAILING_SMALL = next(d for d in ALL_DIMMERS if d.sku == "DIM-TE-25W")
DIM_LEADING = next(d for d in ALL_DIMMERS if d.sku == "DIM-LE-100W")
