"""Constraint rules for concealed hinges — N-candidate signature.

Each rule: (candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult

All 14 rules from engine_v1/rules.py ported to the N-candidate interface.
Products are accessed by role name: candidates["hinge"], candidates["plate"].
"""

from __future__ import annotations

from engine_v2.core.models import Product, Requirements, RuleCategory, RuleResult
from engine_v2.families.concealed_hinge.models import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    Hinge,
    HingeRequirements,
    MountingMethod,
    Plate,
)


# --- Lookup tables (same as v1) ---

APP_TO_OVERLAY_KEY = {
    ApplicationType.FULL_OVERLAY: "full",
    ApplicationType.HALF_OVERLAY: "half",
    ApplicationType.INSET: "inset",
    ApplicationType.OVERLAY: "full",
}

MOUNTING_METHOD_COMPAT = {
    MountingMethod.SCREW_ON: {MountingMethod.SCREW_ON, MountingMethod.EURO_SCREW, MountingMethod.SYSTEM_SCREW},
    MountingMethod.DOWEL: {MountingMethod.DOWEL, MountingMethod.SYSTEM_SCREW},
}

DEFAULT_HEIGHT_THRESHOLDS = [(889, 2), (1400, 3), (1800, 4)]


def hinges_per_door(door_height_mm: float) -> int:
    for max_height, count in DEFAULT_HEIGHT_THRESHOLDS:
        if door_height_mm <= max_height:
            return count
    return 5


# --- Helpers to extract typed products/requirements ---

def _hinge(candidates: dict[str, Product]) -> Hinge:
    return Hinge.model_validate(candidates["hinge"].model_dump())


def _plate(candidates: dict[str, Product]) -> Plate:
    return Plate.model_validate(candidates["plate"].model_dump())


def _req(req: Requirements) -> HingeRequirements:
    return HingeRequirements.model_validate(req.model_dump())


# --- Rules ---


def check_brand_lock(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R001: Hinge and plate must share the same brand (when brand_lock is enabled)."""
    if not req.brand_lock:
        return RuleResult(
            rule_id="R001", rule_name="brand_lock", passed=True,
            detail="Brand lock not required — cross-brand combinations allowed",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    h, p = _hinge(candidates), _plate(candidates)
    ok = h.brand == p.brand
    return RuleResult(
        rule_id="R001", rule_name="brand_lock", passed=ok,
        detail=f"Hinge brand '{h.brand}' {'==' if ok else '!='} plate brand '{p.brand}'",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge_brand": h.brand, "plate_brand": p.brand},
    )


def check_series_compat(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R002: Plate must list the hinge's series as compatible."""
    h, p = _hinge(candidates), _plate(candidates)
    compat_values = [s.value if hasattr(s, 'value') else s for s in p.compatible_hinge_series]
    ok = h.series.value in compat_values
    return RuleResult(
        rule_id="R002", rule_name="series_compatibility", passed=ok,
        detail=f"Hinge series '{h.series.value}' {'in' if ok else 'not in'} plate compatible series {compat_values}",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_cabinet_type(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R003: Hinge, plate, and requirement must all agree on cabinet type."""
    h, p, r = _hinge(candidates), _plate(candidates), _req(req)
    ok = h.cabinet_type == p.cabinet_type == r.cabinet_type
    return RuleResult(
        rule_id="R003", rule_name="cabinet_type_match", passed=ok,
        detail=f"Cabinet type: hinge={h.cabinet_type.value}, plate={p.cabinet_type.value}, required={r.cabinet_type.value}",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_overlay_range(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R004: Desired overlay must be within the plate's achievable range."""
    p, r = _plate(candidates), _req(req)
    app_key = APP_TO_OVERLAY_KEY.get(r.application, r.application)
    overlay_spec = p.overlay_range_mm.get(app_key)

    if overlay_spec is None or overlay_spec is False:
        return RuleResult(
            rule_id="R004", rule_name="overlay_in_range", passed=False,
            detail=f"Plate {p.sku} does not support {r.application.value} application",
            category=RuleCategory.HARD_CONSTRAINT,
            remediation=f"Select a plate that supports {r.application.value}",
        )
    if overlay_spec is True:  # inset
        return RuleResult(
            rule_id="R004", rule_name="overlay_in_range", passed=True,
            detail=f"Inset supported by plate {p.sku}",
            category=RuleCategory.HARD_CONSTRAINT,
        )

    lo, hi = overlay_spec
    ok = lo <= r.desired_overlay_mm <= hi
    return RuleResult(
        rule_id="R004", rule_name="overlay_in_range", passed=ok,
        detail=f"Desired overlay {r.desired_overlay_mm}mm vs plate range [{lo}-{hi}]mm for {r.application.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"desired": r.desired_overlay_mm, "min": lo, "max": hi},
        remediation=f"Adjust overlay to be within [{lo}-{hi}]mm" if not ok else None,
    )


def check_inset_support(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R005: If application is inset, the plate must support it."""
    r = _req(req)
    if r.application != ApplicationType.INSET:
        return RuleResult(
            rule_id="R005", rule_name="inset_support", passed=True,
            detail="Not an inset application — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    p = _plate(candidates)
    ok = p.overlay_range_mm.get("inset", False) is not False
    return RuleResult(
        rule_id="R005", rule_name="inset_support", passed=ok,
        detail=f"Plate {p.sku} {'supports' if ok else 'does not support'} inset",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_door_thickness(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R006: Door thickness within hinge's supported range."""
    h, r = _hinge(candidates), _req(req)
    ok = h.door_thickness_range_mm.contains(r.door_thickness_mm)
    return RuleResult(
        rule_id="R006", rule_name="door_thickness_range", passed=ok,
        detail=f"Door {r.door_thickness_mm}mm vs hinge range [{h.door_thickness_range_mm.min}-{h.door_thickness_range_mm.max}]mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"actual": r.door_thickness_mm, "min": h.door_thickness_range_mm.min, "max": h.door_thickness_range_mm.max},
        remediation="Choose a hinge rated for this door thickness" if not ok else None,
    )


def check_weight(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R007: Door weight vs hinge capacity x number of hinges."""
    h, r = _hinge(candidates), _req(req)
    num_hinges = derived.get("hinges_per_door", 2)
    capacity = h.max_door_weight_kg * num_hinges
    ok = r.door_weight_kg <= capacity
    return RuleResult(
        rule_id="R007", rule_name="door_weight_limit", passed=ok,
        detail=f"Door {r.door_weight_kg}kg vs capacity {h.max_door_weight_kg}kg x {num_hinges} = {capacity}kg",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"door_weight": r.door_weight_kg, "per_hinge": h.max_door_weight_kg, "num_hinges": num_hinges, "capacity": capacity},
        remediation="Consider more hinges or a higher-capacity hinge" if not ok else None,
    )


def check_boring_pattern(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R009: Boring pattern must match."""
    h, r = _hinge(candidates), _req(req)
    ok = h.boring_pattern_mm == r.boring_pattern_mm
    return RuleResult(
        rule_id="R009", rule_name="boring_pattern_match", passed=ok,
        detail=f"Hinge boring {h.boring_pattern_mm}mm vs required {r.boring_pattern_mm}mm",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_corner_angle(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R013: Corner cabinets need >= 155 degree opening."""
    h, r = _hinge(candidates), _req(req)
    if r.cabinet_position != CabinetPosition.CORNER:
        return RuleResult(
            rule_id="R013", rule_name="corner_cabinet_angle", passed=True,
            detail="Not a corner cabinet — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    ok = h.opening_angle_deg >= 155
    return RuleResult(
        rule_id="R013", rule_name="corner_cabinet_angle", passed=ok,
        detail=f"Corner cabinet needs >=155°, hinge is {h.opening_angle_deg}°",
        category=RuleCategory.HARD_CONSTRAINT,
        remediation="Select a wide-angle hinge (155°+) for corner cabinets" if not ok else None,
    )


def check_adjacent_clearance(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R012: Combined overlay of adjacent doors must not exceed partition thickness."""
    r = _req(req)
    if not r.has_adjacent_door:
        return RuleResult(
            rule_id="R012", rule_name="adjacent_door_clearance", passed=True,
            detail="No adjacent door — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    combined = r.desired_overlay_mm + r.adjacent_door_overlay_mm
    ok = combined <= r.partition_thickness_mm
    return RuleResult(
        rule_id="R012", rule_name="adjacent_door_clearance", passed=ok,
        detail=f"Combined overlay {combined}mm vs partition {r.partition_thickness_mm}mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"combined_overlay": combined, "partition": r.partition_thickness_mm},
    )


def check_face_frame_overlay(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R011: Face frame overlay constraint."""
    p, r = _plate(candidates), _req(req)
    if r.cabinet_type != CabinetType.FACE_FRAME:
        return RuleResult(
            rule_id="R011", rule_name="face_frame_overlay", passed=True,
            detail="Not face frame — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    limit = r.face_frame_width_mm - 3
    ok = r.desired_overlay_mm <= limit
    return RuleResult(
        rule_id="R011", rule_name="face_frame_overlay", passed=ok,
        detail=f"Overlay {r.desired_overlay_mm}mm vs face frame limit {limit}mm (frame {r.face_frame_width_mm}mm - 3)",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_mounting_method(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R014: Hinge and plate mounting methods must be compatible."""
    h, p = _hinge(candidates), _plate(candidates)
    allowed = MOUNTING_METHOD_COMPAT.get(h.mounting_method, {h.mounting_method})
    ok = p.mounting_method in allowed
    return RuleResult(
        rule_id="R014", rule_name="mounting_method_match", passed=ok,
        detail=f"Hinge mounting '{h.mounting_method.value}' vs plate '{p.mounting_method.value}'",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_cup_depth(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """R015: Door thickness must be at least cup_depth_mm + 2mm."""
    h, r = _hinge(candidates), _req(req)
    if h.cup_depth_mm is None:
        return RuleResult(
            rule_id="R015", rule_name="cup_depth_door_thickness", passed=True,
            detail="Cup depth not specified — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    min_thickness = h.cup_depth_mm + 2
    ok = r.door_thickness_mm >= min_thickness
    return RuleResult(
        rule_id="R015", rule_name="cup_depth_door_thickness", passed=ok,
        detail=f"Door {r.door_thickness_mm}mm vs min {min_thickness}mm (cup depth {h.cup_depth_mm}mm + 2mm)",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"door_thickness": r.door_thickness_mm, "min_required": min_thickness, "cup_depth": h.cup_depth_mm},
    )


def check_soft_close(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """PREF: Soft-close preference (not a hard constraint)."""
    h, r = _hinge(candidates), _req(req)
    if not r.soft_close:
        return RuleResult(
            rule_id="PREF", rule_name="soft_close_preference", passed=True,
            detail="Soft-close not required — any hinge OK",
            category=RuleCategory.PREFERENCE,
        )
    ok = h.soft_close
    return RuleResult(
        rule_id="PREF", rule_name="soft_close_preference", passed=ok,
        detail=f"Soft-close required: hinge {'has' if ok else 'lacks'} soft-close",
        category=RuleCategory.PREFERENCE,
    )


# --- Rule registry (same order as v1) ---

RULES = [
    check_brand_lock,        # R001
    check_series_compat,     # R002
    check_cabinet_type,      # R003
    check_overlay_range,     # R004
    check_inset_support,     # R005
    check_door_thickness,    # R006
    check_weight,            # R007
    check_boring_pattern,    # R009
    check_corner_angle,      # R013
    check_adjacent_clearance,  # R012
    check_face_frame_overlay,  # R011
    check_mounting_method,   # R014
    check_cup_depth,         # R015
    check_soft_close,        # PREF
]
