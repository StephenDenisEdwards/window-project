"""FastAPI demo for the N-candidate constraint solver.

Run: uvicorn demo.app:app --reload
Open: http://localhost:8000
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from engine_v2.core.solver_n import NCandidateSolver
from engine_v2.families.concealed_hinge.config import HINGE_N_CONFIG
from engine_v2.families.concealed_hinge.loader import load_from_json as load_hinges
from engine_v2.families.drawer_slide.config import SLIDE_N_CONFIG
from engine_v2.families.drawer_slide.loader import load_from_json as load_slides
from engine_v2.families.led_lighting.config import LED_N_CONFIG
from engine_v2.families.led_lighting.loader import load_from_json as load_led

# --- Load data and build solvers at startup ---

DATA_DIR = Path(__file__).resolve().parent.parent / "sample-data"

hinges, plates = load_hinges(DATA_DIR)
slides = load_slides(DATA_DIR)
bars, drivers, dimmers = load_led(DATA_DIR)

SOLVERS: dict[str, NCandidateSolver] = {
    "concealed_hinge": NCandidateSolver(
        config=HINGE_N_CONFIG,
        product_lists={"hinge": hinges, "plate": plates},
    ),
    "drawer_slide": NCandidateSolver(
        config=SLIDE_N_CONFIG,
        product_lists={"slide": slides},
    ),
    "led_lighting": NCandidateSolver(
        config=LED_N_CONFIG,
        product_lists={"light_bar": bars, "driver": drivers, "dimmer": dimmers},
    ),
}

FAMILY_META = {
    "concealed_hinge": {
        "name": "concealed_hinge",
        "title": "Concealed Hinges",
        "description": "Hinge + mounting plate pairs (N=2). 53 hinges, 55 plates, 14 rules.",
        "roles": ["hinge", "plate"],
        "catalog_size": f"{len(hinges)} hinges x {len(plates)} plates",
        "rules": len(HINGE_N_CONFIG.rules),
        "schema": HINGE_N_CONFIG.requirements_type.model_json_schema(),
    },
    "drawer_slide": {
        "name": "drawer_slide",
        "title": "Drawer Slides",
        "description": "Single-product family (N=1). 4 slides, 8 rules.",
        "roles": ["slide"],
        "catalog_size": f"{len(slides)} slides",
        "rules": len(SLIDE_N_CONFIG.rules),
        "schema": SLIDE_N_CONFIG.requirements_type.model_json_schema(),
    },
    "led_lighting": {
        "name": "led_lighting",
        "title": "LED Lighting",
        "description": "Light bar + driver + dimmer triples (N=3). 5 bars, 4 drivers, 4 dimmers, 9 rules.",
        "roles": ["light_bar", "driver", "dimmer"],
        "catalog_size": f"{len(bars)} bars x {len(drivers)} drivers x {len(dimmers)} dimmers",
        "rules": len(LED_N_CONFIG.rules),
        "schema": LED_N_CONFIG.requirements_type.model_json_schema(),
    },
}

EXAMPLES = {
    "concealed_hinge": {
        "cabinet_type": "frameless",
        "door_thickness_mm": 19,
        "door_height_mm": 720,
        "door_weight_kg": 5.2,
        "application": "full_overlay",
        "desired_overlay_mm": 16,
        "boring_pattern_mm": 45,
        "soft_close": True,
        "preferred_brand": "Blum",
    },
    "drawer_slide": {
        "cabinet_depth_mm": 550,
        "drawer_weight_kg": 15.0,
    },
    "led_lighting": {
        "cabinet_length_mm": 600,
        "dimming_required": True,
        "min_lumen_output": 300,
    },
}

# --- FastAPI app ---

app = FastAPI(title="Cabinet Hardware Constraint Engine")


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/families")
def get_families():
    return list(FAMILY_META.values())


@app.get("/api/example/{family}")
def get_example(family: str):
    if family not in EXAMPLES:
        raise HTTPException(404, f"Unknown family: {family}")
    return EXAMPLES[family]


@app.post("/api/solve/{family}")
def solve(family: str, body: dict):
    if family not in SOLVERS:
        raise HTTPException(404, f"Unknown family: {family}")

    solver = SOLVERS[family]
    config = solver.config

    try:
        req = config.requirements_type.model_validate(body)
    except Exception as e:
        raise HTTPException(422, str(e))

    return solver.solve_with_explanation(req)
