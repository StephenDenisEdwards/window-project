"""Load sample-data/ JSON into v2 concealed hinge models."""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    CabinetType,
    Hinge,
    HingeSeries,
    MountingMethod,
    Plate,
    PlateType,
    Range,
)


def load_from_json(data_dir: Path) -> tuple[list[Hinge], list[Plate]]:
    """Load hinges and plates from the sample-data JSON files."""
    with open(data_dir / "hinges.json") as f:
        raw_hinges = json.load(f)
    with open(data_dir / "mounting_plates.json") as f:
        raw_plates = json.load(f)

    hinges = []
    for h in raw_hinges:
        hinges.append(Hinge(
            sku=h["sku"],
            brand=h["brand"],
            price_usd=h.get("price_usd"),
            series=HingeSeries(h["series"]),
            application=h["application"],
            opening_angle_deg=h["opening_angle_deg"],
            boring_pattern_mm=h["boring_pattern_mm"],
            door_thickness_range_mm=Range(
                min=float(h["door_thickness_min_mm"]),
                max=float(h["door_thickness_max_mm"]),
            ),
            max_door_weight_kg=float(h["max_door_weight_kg"]),
            soft_close=h["soft_close"],
            mounting_method=MountingMethod(h["mounting"]),
            cabinet_type=CabinetType(h["cabinet_type"]),
            cup_depth_mm=h.get("cup_depth_mm"),
        ))

    plates = []
    for p in raw_plates:
        plates.append(Plate(
            sku=p["sku"],
            brand=p["brand"],
            price_usd=p.get("price_usd"),
            series=p["series"],
            compatible_hinge_series=[HingeSeries(s) for s in p["compatible_hinge_series"]],
            mounting_method=MountingMethod(p["mounting_method"]),
            cabinet_type=CabinetType(p["cabinet_type"]),
            plate_type=PlateType(p["type"]),
            overlay_range_mm=p["overlay_range_mm"],
        ))

    return hinges, plates
