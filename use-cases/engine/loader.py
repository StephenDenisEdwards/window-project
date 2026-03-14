"""
Data loading adapters: PoC JSON -> production models.
"""

from __future__ import annotations

import json
from pathlib import Path

from .enums import (
    ApplicationType,
    CabinetType,
    HingeSeries,
    MountingMethod,
    PlateMaterial,
    PlateType,
    ProductFamily,
)
from .models import (
    ConcealedHinge,
    CustomerRequirements,
    DistributorSKU,
    MountingPlate,
    OverlayEntry,
    OverlayTable,
    Range,
)


def _convert_overlay_range(overlay_range_mm: dict) -> OverlayTable:
    """Convert PoC simplified overlay ranges to OverlayTable format.

    Input format: {"full": [14, 20], "half": [3, 9], "inset": true}
    Output: OverlayTable with synthetic entries spanning the range.
    """
    entries: dict[ApplicationType, list[OverlayEntry]] = {}

    for key, value in overlay_range_mm.items():
        if key == "full":
            app = ApplicationType.FULL_OVERLAY
        elif key == "half":
            app = ApplicationType.HALF_OVERLAY
        elif key == "inset":
            app = ApplicationType.INSET
        else:
            continue

        if value is True:
            # Inset supported - create a synthetic entry with 0 overlay
            entries[app] = [
                OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=5.0, overlay_mm=0),
            ]
        elif value is False or value is None:
            # Not supported - don't add entries
            continue
        elif isinstance(value, list) and len(value) == 2:
            lo, hi = value
            # Create synthetic min/max entries to preserve the range
            entry_list = [
                OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=3.0, overlay_mm=float(lo)),
            ]
            if lo != hi:
                entry_list.append(
                    OverlayEntry(base_plate_height_mm=0, drilling_distance_mm=7.0, overlay_mm=float(hi)),
                )
            entries[app] = entry_list

    return OverlayTable(entries=entries)


def _parse_mounting_method(value: str) -> MountingMethod:
    return MountingMethod(value)


def _parse_hinge_series(value: str) -> HingeSeries:
    return HingeSeries(value)


def _parse_plate_material(value: str | None) -> PlateMaterial | None:
    if value is None:
        return None
    return PlateMaterial(value)


def load_from_json(data_dir: Path) -> tuple[list[ConcealedHinge], list[MountingPlate]]:
    """Load the existing PoC JSON files and convert to production models."""
    with open(data_dir / "hinges.json") as f:
        raw_hinges = json.load(f)
    with open(data_dir / "mounting_plates.json") as f:
        raw_plates = json.load(f)

    hinges = []
    for h in raw_hinges:
        hinge = ConcealedHinge(
            manufacturer_part=h.get("manufacturer_part", h["sku"]),
            manufacturer=h["brand"],
            product_family=ProductFamily.CONCEALED_HINGE,
            distributor_skus=[
                DistributorSKU(
                    sku=h["sku"],
                    brand=h["brand"],
                    price_usd=h.get("price_usd"),
                )
            ],
            series=HingeSeries(h["series"]),
            application=ApplicationType(h["application"]),
            opening_angle_deg=h["opening_angle_deg"],
            cup_diameter_mm=float(h["cup_diameter_mm"]),
            cup_depth_mm=h.get("cup_depth_mm"),
            boring_pattern_mm=h["boring_pattern_mm"],
            crank_mm=float(h["crank_mm"]),
            door_thickness_range_mm=Range(
                min=float(h["door_thickness_min_mm"]),
                max=float(h["door_thickness_max_mm"]),
            ),
            max_door_weight_kg=float(h["max_door_weight_kg"]),
            soft_close=h["soft_close"],
            mounting_method=MountingMethod(h["mounting"]),
            cabinet_type=CabinetType(h["cabinet_type"]),
        )
        hinges.append(hinge)

    plates = []
    for p in raw_plates:
        plate = MountingPlate(
            manufacturer_part=p.get("manufacturer_part", p["sku"]),
            manufacturer=p["brand"],
            product_family=ProductFamily.MOUNTING_PLATE,
            distributor_skus=[
                DistributorSKU(
                    sku=p["sku"],
                    brand=p["brand"],
                    price_usd=p.get("price_usd"),
                )
            ],
            series=p["series"],
            plate_type=PlateType(p["type"]),
            mounting_method=MountingMethod(p["mounting_method"]),
            cabinet_type=CabinetType(p["cabinet_type"]),
            plate_height_mm=float(p["plate_height_mm"]),
            compatible_hinge_series=[HingeSeries(s) for s in p["compatible_hinge_series"]],
            overlay_table=_convert_overlay_range(p["overlay_range_mm"]),
            height_adjustment_mm=float(p.get("height_adjustment_mm", 0)),
            depth_adjustment_mm=float(p.get("depth_adjustment_mm", 0)),
            setback_mm=float(p.get("setback_mm", 0)),
            material=_parse_plate_material(p.get("material")),
            fixing_points=p.get("fixing_points") or 0,
        )
        plates.append(plate)

    return hinges, plates
