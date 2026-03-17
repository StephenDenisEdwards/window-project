"""
Constraint rules for the production hinge engine.

Each rule is a callable: (hinge, plate, requirements, num_hinges) -> RuleResult
Rules are collected in RULES list for the solver to iterate.
"""

from __future__ import annotations

from typing import Callable

from .enums import (
    ApplicationType,
    CabinetPosition,
    CabinetType,
    MountingMethod,
    RuleCategory,
)
from .models import (
    ConcealedHinge,
    Configuration,
    CustomerRequirements,
    MountingPlate,
    RuleResult,
)


# ---------------------------------------------------------------------------
# Application -> overlay key mapping (mirrors PoC)
# ---------------------------------------------------------------------------

APP_TO_OVERLAY_KEY = {
    ApplicationType.FULL_OVERLAY: "full",
    ApplicationType.HALF_OVERLAY: "half",
    ApplicationType.INSET: "inset",
    ApplicationType.OVERLAY: "full",
}

APP_TO_OVERLAY_TYPE = {
    ApplicationType.FULL_OVERLAY: ApplicationType.FULL_OVERLAY,
    ApplicationType.HALF_OVERLAY: ApplicationType.HALF_OVERLAY,
    ApplicationType.INSET: ApplicationType.INSET,
    ApplicationType.OVERLAY: ApplicationType.FULL_OVERLAY,
}

# Mounting method compatibility (same as PoC)
MOUNTING_METHOD_COMPAT = {
    MountingMethod.SCREW_ON: {MountingMethod.SCREW_ON, MountingMethod.EURO_SCREW, MountingMethod.SYSTEM_SCREW},
    MountingMethod.DOWEL: {MountingMethod.DOWEL, MountingMethod.SYSTEM_SCREW},
}


# ---------------------------------------------------------------------------
# Hinge count by door height (R008)
# ---------------------------------------------------------------------------

# Default thresholds (most conservative across Blum/Grass catalogs)
DEFAULT_HEIGHT_THRESHOLDS = [(889, 2), (1400, 3), (1800, 4)]


def hinges_per_door(door_height_mm: float, thresholds: list[tuple[float, int]] | None = None) -> int:
    """R008: hinge count derived from door height. Supports brand-specific thresholds."""
    if thresholds is None:
        thresholds = DEFAULT_HEIGHT_THRESHOLDS
    for max_height, count in thresholds:
        if door_height_mm <= max_height:
            return count
    return 5


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def check_brand_lock(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R001: Hinge and plate must share the same brand (when brand_lock is enabled)."""
    if not req.brand_lock:
        return RuleResult(
            rule_id="R001",
            rule_name="brand_lock",
            passed=True,
            detail="Brand lock not required — cross-brand combinations allowed",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    ok = h.brand == p.brand
    return RuleResult(
        rule_id="R001",
        rule_name="brand_lock",
        passed=ok,
        detail=f"Hinge brand '{h.brand}' {'==' if ok else '!='} plate brand '{p.brand}'",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge_brand": h.brand, "plate_brand": p.brand},
    )


def check_series_compat(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R002: Plate must list the hinge's series as compatible."""
    ok = h.series.value in [s.value if hasattr(s, 'value') else s for s in p.compatible_hinge_series]
    return RuleResult(
        rule_id="R002",
        rule_name="series_compatibility",
        passed=ok,
        detail=f"Hinge series '{h.series.value}' {'in' if ok else 'not in'} plate compatible series {[s.value if hasattr(s, 'value') else s for s in p.compatible_hinge_series]}",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_cabinet_type(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R003: Hinge, plate, and requirement must all agree on cabinet type."""
    ok = h.cabinet_type == p.cabinet_type == req.cabinet_type
    return RuleResult(
        rule_id="R003",
        rule_name="cabinet_type_match",
        passed=ok,
        detail=f"Cabinet type: hinge={h.cabinet_type.value}, plate={p.cabinet_type.value}, required={req.cabinet_type.value}",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_overlay_range(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R004: Desired overlay must be within the plate's achievable range."""
    app_key = APP_TO_OVERLAY_KEY.get(req.application, req.application)
    overlay_spec = p.overlay_range_mm.get(app_key)

    if overlay_spec is None or overlay_spec is False:
        return RuleResult(
            rule_id="R004",
            rule_name="overlay_in_range",
            passed=False,
            detail=f"Plate {p.sku} does not support {req.application.value} application",
            category=RuleCategory.HARD_CONSTRAINT,
            remediation=f"Select a plate that supports {req.application.value}",
        )
    if overlay_spec is True:  # inset
        return RuleResult(
            rule_id="R004",
            rule_name="overlay_in_range",
            passed=True,
            detail=f"Inset supported by plate {p.sku}",
            category=RuleCategory.HARD_CONSTRAINT,
        )

    lo, hi = overlay_spec
    ok = lo <= req.desired_overlay_mm <= hi
    return RuleResult(
        rule_id="R004",
        rule_name="overlay_in_range",
        passed=ok,
        detail=f"Desired overlay {req.desired_overlay_mm}mm vs plate range [{lo}-{hi}]mm for {req.application.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"desired": req.desired_overlay_mm, "min": lo, "max": hi},
        remediation=f"Adjust overlay to be within [{lo}-{hi}]mm" if not ok else None,
    )


def check_inset_support(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R005: If application is inset, the plate must support it."""
    if req.application != ApplicationType.INSET:
        return RuleResult(
            rule_id="R005",
            rule_name="inset_support",
            passed=True,
            detail="Not an inset application — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    ok = p.overlay_range_mm.get("inset", False) is not False
    return RuleResult(
        rule_id="R005",
        rule_name="inset_support",
        passed=ok,
        detail=f"Plate {p.sku} {'supports' if ok else 'does not support'} inset",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_door_thickness(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R006: Door thickness within hinge's supported range."""
    ok = h.door_thickness_range_mm.contains(req.door_thickness_mm)
    return RuleResult(
        rule_id="R006",
        rule_name="door_thickness_range",
        passed=ok,
        detail=f"Door {req.door_thickness_mm}mm vs hinge range [{h.door_thickness_min_mm}-{h.door_thickness_max_mm}]mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"actual": req.door_thickness_mm, "min": h.door_thickness_min_mm, "max": h.door_thickness_max_mm},
        remediation="Choose a hinge rated for this door thickness" if not ok else None,
    )


def check_weight(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R007: Door weight vs hinge capacity x number of hinges. No derating (R010 removed)."""
    capacity = h.max_door_weight_kg * num_hinges
    ok = req.door_weight_kg <= capacity
    detail = (f"Door {req.door_weight_kg}kg vs capacity {h.max_door_weight_kg}kg x {num_hinges} "
              f"= {capacity}kg")
    return RuleResult(
        rule_id="R007",
        rule_name="door_weight_limit",
        passed=ok,
        detail=detail,
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"door_weight": req.door_weight_kg, "per_hinge": h.max_door_weight_kg, "num_hinges": num_hinges, "capacity": capacity},
        remediation="Consider more hinges or a higher-capacity hinge" if not ok else None,
    )


def check_boring_pattern(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R009: Boring pattern must match."""
    ok = h.boring_pattern_mm == req.boring_pattern_mm
    return RuleResult(
        rule_id="R009",
        rule_name="boring_pattern_match",
        passed=ok,
        detail=f"Hinge boring {h.boring_pattern_mm}mm vs required {req.boring_pattern_mm}mm",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_corner_angle(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R013: Corner cabinets need >= 155 degree opening."""
    if req.cabinet_position != CabinetPosition.CORNER:
        return RuleResult(
            rule_id="R013",
            rule_name="corner_cabinet_angle",
            passed=True,
            detail="Not a corner cabinet — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    ok = h.opening_angle_deg >= 155
    return RuleResult(
        rule_id="R013",
        rule_name="corner_cabinet_angle",
        passed=ok,
        detail=f"Corner cabinet needs >=155°, hinge is {h.opening_angle_deg}°",
        category=RuleCategory.HARD_CONSTRAINT,
        remediation="Select a wide-angle hinge (155°+) for corner cabinets" if not ok else None,
    )


def check_adjacent_clearance(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R012: Combined overlay of adjacent doors must not exceed partition thickness."""
    if not req.has_adjacent_door:
        return RuleResult(
            rule_id="R012",
            rule_name="adjacent_door_clearance",
            passed=True,
            detail="No adjacent door — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    combined = req.desired_overlay_mm + req.adjacent_door_overlay_mm
    ok = combined <= req.partition_thickness_mm
    return RuleResult(
        rule_id="R012",
        rule_name="adjacent_door_clearance",
        passed=ok,
        detail=f"Combined overlay {combined}mm vs partition {req.partition_thickness_mm}mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"combined_overlay": combined, "partition": req.partition_thickness_mm},
    )


def check_face_frame_overlay(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R011: Face frame overlay constraint."""
    if p.cabinet_type != CabinetType.FACE_FRAME:
        return RuleResult(
            rule_id="R011",
            rule_name="face_frame_overlay",
            passed=True,
            detail="Not face frame — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    limit = req.face_frame_width_mm - 3
    ok = req.desired_overlay_mm <= limit
    return RuleResult(
        rule_id="R011",
        rule_name="face_frame_overlay",
        passed=ok,
        detail=f"Overlay {req.desired_overlay_mm}mm vs face frame limit {limit}mm (frame {req.face_frame_width_mm}mm - 3)",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_mounting_method(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R014: Hinge and plate mounting methods must be compatible."""
    allowed = MOUNTING_METHOD_COMPAT.get(h.mounting_method, {h.mounting_method})
    ok = p.mounting_method in allowed
    return RuleResult(
        rule_id="R014",
        rule_name="mounting_method_match",
        passed=ok,
        detail=f"Hinge mounting '{h.mounting_method.value}' vs plate '{p.mounting_method.value}'",
        category=RuleCategory.HARD_CONSTRAINT,
    )


def check_cup_depth(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """R015: Door thickness must be at least cup_depth_mm + 2mm."""
    if h.cup_depth_mm is None:
        return RuleResult(
            rule_id="R015",
            rule_name="cup_depth_door_thickness",
            passed=True,
            detail="Cup depth not specified — skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    min_thickness = h.cup_depth_mm + 2
    ok = req.door_thickness_mm >= min_thickness
    return RuleResult(
        rule_id="R015",
        rule_name="cup_depth_door_thickness",
        passed=ok,
        detail=f"Door {req.door_thickness_mm}mm vs min {min_thickness}mm (cup depth {h.cup_depth_mm}mm + 2mm)",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"door_thickness": req.door_thickness_mm, "min_required": min_thickness, "cup_depth": h.cup_depth_mm},
    )


def check_soft_close(h: ConcealedHinge, p: MountingPlate, req: CustomerRequirements, num_hinges: int) -> RuleResult:
    """PREF: Soft-close preference (not a hard constraint)."""
    if not req.soft_close:
        return RuleResult(
            rule_id="PREF",
            rule_name="soft_close_preference",
            passed=True,
            detail="Soft-close not required — any hinge OK",
            category=RuleCategory.PREFERENCE,
        )
    ok = h.soft_close
    return RuleResult(
        rule_id="PREF",
        rule_name="soft_close_preference",
        passed=ok,
        detail=f"Soft-close required: hinge {'has' if ok else 'lacks'} soft-close",
        category=RuleCategory.PREFERENCE,
    )


# ---------------------------------------------------------------------------
# Rule registry — ordered list of all rules
# ---------------------------------------------------------------------------

RuleFn = Callable[[ConcealedHinge, MountingPlate, CustomerRequirements, int], RuleResult]

RULES: list[RuleFn] = [
    check_brand_lock,       # R001
    check_series_compat,    # R002
    check_cabinet_type,     # R003
    check_overlay_range,    # R004
    check_inset_support,    # R005
    check_door_thickness,   # R006
    check_weight,           # R007
    check_boring_pattern,   # R009
    check_corner_angle,     # R013
    check_adjacent_clearance,  # R012
    check_face_frame_overlay,  # R011
    check_mounting_method,  # R014
    check_cup_depth,        # R015
    check_soft_close,       # PREF
]
