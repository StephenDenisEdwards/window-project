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

def _extract_rule_info(config, product_lists, example_data):
    """Call each rule with example data to extract rule ID, name, category, docstring, and source."""
    import inspect
    dummy_candidates = {role: products[0] for role, products in product_lists.items()}
    dummy_req = config.requirements_type.model_validate(example_data)
    derived = config.derived_values(dummy_req) if config.derived_values else {}

    rules_info = []
    for rule_fn in config.rules:
        doc = (rule_fn.__doc__ or "").strip()
        try:
            source = inspect.getsource(rule_fn)
        except (OSError, TypeError):
            source = ""
        try:
            result = rule_fn(dummy_candidates, dummy_req, derived)
            rules_info.append({
                "rule_id": result.rule_id,
                "rule_name": result.rule_name,
                "category": result.category.value,
                "description": doc,
                "source": source,
            })
        except Exception:
            rules_info.append({
                "rule_id": "?",
                "rule_name": rule_fn.__name__,
                "category": "unknown",
                "description": doc,
                "source": source,
            })
    return rules_info

EXAMPLES = {
    "concealed_hinge": [
        {
            "name": "Standard kitchen — Blum, full overlay",
            "data": {
                "cabinet_type": "frameless", "door_thickness_mm": 19, "door_height_mm": 720,
                "door_weight_kg": 5.2, "application": "full_overlay", "desired_overlay_mm": 16,
                "boring_pattern_mm": 45, "soft_close": True, "preferred_brand": "Blum",
            },
        },
        {
            "name": "Corner cabinet — wide-angle hinge needed",
            "data": {
                "cabinet_type": "frameless", "door_thickness_mm": 19, "door_height_mm": 800,
                "door_weight_kg": 4.0, "application": "full_overlay", "desired_overlay_mm": 16,
                "boring_pattern_mm": 45, "soft_close": True, "cabinet_position": "corner",
            },
        },
        {
            "name": "Tall pantry — 1600mm, heavy, Grass",
            "data": {
                "cabinet_type": "frameless", "door_thickness_mm": 22, "door_height_mm": 1600,
                "door_weight_kg": 14.0, "application": "full_overlay", "desired_overlay_mm": 16,
                "boring_pattern_mm": 45, "soft_close": True, "preferred_brand": "Grass",
            },
        },
        {
            "name": "Adjacent doors — half overlay, shared partition",
            "data": {
                "cabinet_type": "frameless", "door_thickness_mm": 19, "door_height_mm": 720,
                "door_weight_kg": 4.0, "application": "half_overlay", "desired_overlay_mm": 6,
                "boring_pattern_mm": 45, "soft_close": True, "preferred_brand": "Blum",
                "has_adjacent_door": True, "adjacent_door_overlay_mm": 6, "partition_thickness_mm": 19,
            },
        },
        {
            "name": "IMPOSSIBLE — heavy corner door (Blum, 12kg)",
            "data": {
                "cabinet_type": "frameless", "door_thickness_mm": 22, "door_height_mm": 800,
                "door_weight_kg": 12.0, "application": "full_overlay", "desired_overlay_mm": 16,
                "boring_pattern_mm": 45, "soft_close": True, "cabinet_position": "corner",
                "preferred_brand": "Blum",
            },
        },
        {
            "name": "All brands — no preference, no soft-close",
            "data": {
                "cabinet_type": "frameless", "door_thickness_mm": 19, "door_height_mm": 720,
                "door_weight_kg": 5.0, "application": "full_overlay", "desired_overlay_mm": 16,
                "boring_pattern_mm": 45, "soft_close": False,
            },
        },
    ],
    "drawer_slide": [
        {
            "name": "Standard kitchen drawer",
            "data": {"cabinet_depth_mm": 550, "drawer_weight_kg": 15.0},
        },
        {
            "name": "Heavy-duty — 42kg load",
            "data": {"cabinet_depth_mm": 550, "drawer_weight_kg": 42.0},
        },
        {
            "name": "Blum undermount, soft-close, full extension",
            "data": {
                "cabinet_depth_mm": 550, "drawer_weight_kg": 20.0,
                "extension_type": "full", "mount_type": "undermount",
                "soft_close": True, "preferred_brand": "Blum",
            },
        },
        {
            "name": "IMPOSSIBLE — cabinet too shallow",
            "data": {"cabinet_depth_mm": 300, "drawer_weight_kg": 5.0},
        },
    ],
    "led_lighting": [
        {
            "name": "600mm cabinet with dimming",
            "data": {"cabinet_length_mm": 600, "dimming_required": True, "min_lumen_output": 300},
        },
        {
            "name": "Large cabinet, no dimming",
            "data": {"cabinet_length_mm": 900, "dimming_required": False},
        },
        {
            "name": "High brightness, dimming required",
            "data": {"cabinet_length_mm": 800, "dimming_required": True, "min_lumen_output": 1000},
        },
        {
            "name": "IMPOSSIBLE — cabinet too small (200mm)",
            "data": {"cabinet_length_mm": 200, "dimming_required": True, "min_lumen_output": 300},
        },
    ],
}

FAMILY_META = {
    "concealed_hinge": {
        "name": "concealed_hinge",
        "title": "Concealed Hinges",
        "description": "Hinge + mounting plate pairs (N=2). 53 hinges, 55 plates, 14 rules.",
        "roles": ["hinge", "plate"],
        "catalog_size": f"{len(hinges)} hinges x {len(plates)} plates",
        "rules_count": len(HINGE_N_CONFIG.rules),
        "rules": _extract_rule_info(HINGE_N_CONFIG, {"hinge": hinges, "plate": plates}, EXAMPLES["concealed_hinge"][0]["data"]),
        "schema": HINGE_N_CONFIG.requirements_type.model_json_schema(),
    },
    "drawer_slide": {
        "name": "drawer_slide",
        "title": "Drawer Slides",
        "description": "Single-product family (N=1). 4 slides, 8 rules.",
        "roles": ["slide"],
        "catalog_size": f"{len(slides)} slides",
        "rules_count": len(SLIDE_N_CONFIG.rules),
        "rules": _extract_rule_info(SLIDE_N_CONFIG, {"slide": slides}, EXAMPLES["drawer_slide"][0]["data"]),
        "schema": SLIDE_N_CONFIG.requirements_type.model_json_schema(),
    },
    "led_lighting": {
        "name": "led_lighting",
        "title": "LED Lighting",
        "description": "Light bar + driver + dimmer triples (N=3). 5 bars, 4 drivers, 4 dimmers, 9 rules.",
        "roles": ["light_bar", "driver", "dimmer"],
        "catalog_size": f"{len(bars)} bars x {len(drivers)} drivers x {len(dimmers)} dimmers",
        "rules_count": len(LED_N_CONFIG.rules),
        "rules": _extract_rule_info(LED_N_CONFIG, {"light_bar": bars, "driver": drivers, "dimmer": dimmers}, EXAMPLES["led_lighting"][0]["data"]),
        "schema": LED_N_CONFIG.requirements_type.model_json_schema(),
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


@app.get("/api/examples/{family}")
def get_examples(family: str):
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
