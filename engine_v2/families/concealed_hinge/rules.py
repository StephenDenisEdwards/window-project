"""Constraint rules for concealed hinges.

Each rule has the generic signature:
    (primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult

Rules cast to concrete types internally.
"""

from engine_v2.core.models import Product, Requirements, RuleCategory, RuleResult
from engine_v2.families.concealed_hinge.models import (
    CabinetPosition,
    Hinge,
    HingeRequirements,
    Plate,
)


def check_brand_lock(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    if not req.brand_lock:
        return RuleResult(
            rule_id="R001",
            rule_name="brand_lock",
            passed=True,
            detail="Brand lock not required — cross-brand combinations allowed",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    h, p = Hinge.model_validate(primary.model_dump()), Plate.model_validate(secondary.model_dump())
    passed = h.brand == p.brand
    return RuleResult(
        rule_id="R001",
        rule_name="brand_lock",
        passed=passed,
        detail=f"Hinge brand {h.brand} {'==' if passed else '!='} plate brand {p.brand}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge_brand": h.brand, "plate_brand": p.brand},
        remediation=None if passed else f"Select a {h.brand} plate or a {p.brand} hinge",
    )


def check_series_compat(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h, p = Hinge.model_validate(primary.model_dump()), Plate.model_validate(secondary.model_dump())
    compat_values = [s.value if hasattr(s, "value") else s for s in p.compatible_hinge_series]
    passed = h.series.value in compat_values
    return RuleResult(
        rule_id="R002",
        rule_name="series_compatibility",
        passed=passed,
        detail=f"Hinge series {h.series.value} {'in' if passed else 'not in'} plate compatible series {compat_values}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge_series": h.series.value, "plate_compatible": compat_values},
        remediation=None if passed else f"Select a plate compatible with {h.series.value} hinges",
    )


def check_cabinet_type(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    passed = h.cabinet_type == r.cabinet_type
    return RuleResult(
        rule_id="R003",
        rule_name="cabinet_type",
        passed=passed,
        detail=f"Hinge cabinet type {h.cabinet_type.value} {'matches' if passed else 'does not match'} required {r.cabinet_type.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge": h.cabinet_type.value, "required": r.cabinet_type.value},
        remediation=None if passed else f"Select a {r.cabinet_type.value} hinge",
    )


def check_overlay_range(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    p = Plate.model_validate(secondary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    passed = p.overlay_min_mm <= r.desired_overlay_mm <= p.overlay_max_mm
    return RuleResult(
        rule_id="R004",
        rule_name="overlay_range",
        passed=passed,
        detail=f"Desired overlay {r.desired_overlay_mm}mm {'within' if passed else 'outside'} plate range [{p.overlay_min_mm}-{p.overlay_max_mm}mm]",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"desired": r.desired_overlay_mm, "min": p.overlay_min_mm, "max": p.overlay_max_mm},
        remediation=None if passed else f"Select a plate with overlay range covering {r.desired_overlay_mm}mm",
    )


def check_door_thickness(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    passed = h.door_thickness_range_mm.contains(r.door_thickness_mm)
    return RuleResult(
        rule_id="R006",
        rule_name="door_thickness",
        passed=passed,
        detail=f"Door {r.door_thickness_mm}mm {'within' if passed else 'outside'} hinge range [{h.door_thickness_range_mm.min}-{h.door_thickness_range_mm.max}mm]",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"door": r.door_thickness_mm, "min": h.door_thickness_range_mm.min, "max": h.door_thickness_range_mm.max},
        remediation=None if passed else f"Door thickness must be {h.door_thickness_range_mm.min}-{h.door_thickness_range_mm.max}mm for this hinge",
    )


def check_weight(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    num_hinges = derived.get("hinges_per_door", 2)
    total_capacity = h.max_door_weight_kg * num_hinges
    passed = r.door_weight_kg <= total_capacity
    return RuleResult(
        rule_id="R007",
        rule_name="weight_capacity",
        passed=passed,
        detail=f"Door {r.door_weight_kg}kg {'<=' if passed else '>'} capacity {total_capacity}kg ({num_hinges} hinges x {h.max_door_weight_kg}kg)",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"door_weight": r.door_weight_kg, "capacity": total_capacity, "hinges": num_hinges},
        remediation=None if passed else f"Door is {r.door_weight_kg - total_capacity:.1f}kg over capacity. Use a higher-rated hinge or lighter door.",
    )


def check_boring_pattern(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    passed = h.boring_pattern_mm == r.boring_pattern_mm
    return RuleResult(
        rule_id="R009",
        rule_name="boring_pattern",
        passed=passed,
        detail=f"Hinge boring {h.boring_pattern_mm}mm {'==' if passed else '!='} required {r.boring_pattern_mm}mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge": h.boring_pattern_mm, "required": r.boring_pattern_mm},
        remediation=None if passed else f"Select a hinge with {r.boring_pattern_mm}mm boring pattern",
    )


def check_corner_angle(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    if r.cabinet_position == CabinetPosition.STANDARD:
        return RuleResult(
            rule_id="R013",
            rule_name="corner_cabinet_angle",
            passed=True,
            detail="Not a corner cabinet — rule skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    min_angle = 155 if r.cabinet_position == CabinetPosition.CORNER else 165
    passed = h.opening_angle_deg >= min_angle
    return RuleResult(
        rule_id="R013",
        rule_name="corner_cabinet_angle",
        passed=passed,
        detail=f"Hinge {h.opening_angle_deg}° {'>=' if passed else '<'} required {min_angle}° for {r.cabinet_position.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge_angle": h.opening_angle_deg, "min_required": min_angle},
        remediation=None if passed else f"Corner/blind corner requires >= {min_angle}° hinge",
    )


def check_mounting_method(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    p = Plate.model_validate(secondary.model_dump())
    passed = h.mounting_method == p.mounting_method
    return RuleResult(
        rule_id="R014",
        rule_name="mounting_method",
        passed=passed,
        detail=f"Hinge mount {h.mounting_method.value} {'==' if passed else '!='} plate mount {p.mounting_method.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"hinge": h.mounting_method.value, "plate": p.mounting_method.value},
        remediation=None if passed else f"Select a plate with {h.mounting_method.value} mounting",
    )


def check_soft_close(primary: Product, secondary: Product | None, req: Requirements, derived: dict) -> RuleResult:
    h = Hinge.model_validate(primary.model_dump())
    r = HingeRequirements.model_validate(req.model_dump())
    if not r.soft_close:
        return RuleResult(
            rule_id="PREF",
            rule_name="soft_close",
            passed=True,
            detail="Soft-close not requested",
            category=RuleCategory.PREFERENCE,
        )
    passed = h.soft_close
    return RuleResult(
        rule_id="PREF",
        rule_name="soft_close",
        passed=passed,
        detail=f"Soft-close {'available' if passed else 'not available'} on this hinge",
        category=RuleCategory.PREFERENCE,
        remediation=None if passed else "This hinge does not have soft-close. Consider a BLUMOTION or Tiomos variant.",
    )


RULES = [
    check_brand_lock,
    check_series_compat,
    check_cabinet_type,
    check_overlay_range,
    check_door_thickness,
    check_weight,
    check_boring_pattern,
    check_corner_angle,
    check_mounting_method,
    check_soft_close,
]
