"""Constraint rules for drawer slides — N-candidate signature.

Each rule: (candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult

Single-product family: candidates has one key, "slide".
"""

from __future__ import annotations

from engine_v2.core.models import Product, Requirements, RuleCategory, RuleResult
from engine_v2.families.drawer_slide.models import (
    DrawerSlide,
    SlideCloseType,
    SlideMountType,
    SlideRequirements,
)


def _slide(candidates: dict[str, Product]) -> DrawerSlide:
    return DrawerSlide.model_validate(candidates["slide"].model_dump())


def _req(req: Requirements) -> SlideRequirements:
    return SlideRequirements.model_validate(req.model_dump())


def check_load_capacity(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS001: Drawer weight must not exceed slide's load rating."""
    slide, r = _slide(candidates), _req(req)
    passed = r.drawer_weight_kg <= slide.max_load_kg
    return RuleResult(
        rule_id="DS001", rule_name="load_capacity", passed=passed,
        detail=f"Drawer {r.drawer_weight_kg}kg {'<=' if passed else '>'} slide rating {slide.max_load_kg}kg",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"drawer_weight": r.drawer_weight_kg, "slide_rating": slide.max_load_kg},
        remediation=None if passed else f"Drawer is {r.drawer_weight_kg - slide.max_load_kg:.1f}kg over slide rating. Use a heavier-duty slide.",
    )


def check_cabinet_depth(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS002: Cabinet must be deep enough for the slide plus clearance."""
    slide, r = _slide(candidates), _req(req)
    min_depth = slide.slide_length_mm + slide.min_cabinet_depth_mm
    passed = r.cabinet_depth_mm >= min_depth
    return RuleResult(
        rule_id="DS002", rule_name="cabinet_depth", passed=passed,
        detail=f"Cabinet {r.cabinet_depth_mm}mm {'>=' if passed else '<'} required {min_depth}mm (slide {slide.slide_length_mm}mm + {slide.min_cabinet_depth_mm}mm clearance)",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"cabinet_depth": r.cabinet_depth_mm, "required": min_depth, "slide_length": slide.slide_length_mm},
        remediation=None if passed else f"Cabinet is {min_depth - r.cabinet_depth_mm}mm too shallow. Use a shorter slide.",
    )


def check_extension_type(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS003: Slide extension type must match requirement (if specified)."""
    slide, r = _slide(candidates), _req(req)
    if r.extension_type is None:
        return RuleResult(
            rule_id="DS003", rule_name="extension_type", passed=True,
            detail="No extension type preference — any type accepted",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    passed = slide.extension_type == r.extension_type
    return RuleResult(
        rule_id="DS003", rule_name="extension_type", passed=passed,
        detail=f"Slide extension {slide.extension_type.value} {'==' if passed else '!='} required {r.extension_type.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"slide": slide.extension_type.value, "required": r.extension_type.value},
        remediation=None if passed else f"Select a {r.extension_type.value} extension slide",
    )


def check_mount_type(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS004: Slide mount type must match requirement (if specified)."""
    slide, r = _slide(candidates), _req(req)
    if r.mount_type is None:
        return RuleResult(
            rule_id="DS004", rule_name="mount_type", passed=True,
            detail="No mount type preference — any type accepted",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    passed = slide.mount_type == r.mount_type
    return RuleResult(
        rule_id="DS004", rule_name="mount_type", passed=passed,
        detail=f"Slide mount {slide.mount_type.value} {'==' if passed else '!='} required {r.mount_type.value}",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"slide": slide.mount_type.value, "required": r.mount_type.value},
        remediation=None if passed else f"Select a {r.mount_type.value} slide",
    )


def check_undermount_width(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS005: Undermount slides have a max drawer width for stability."""
    slide, r = _slide(candidates), _req(req)
    if slide.mount_type != SlideMountType.UNDERMOUNT or r.drawer_width_mm is None:
        return RuleResult(
            rule_id="DS005", rule_name="undermount_width_limit", passed=True,
            detail="Not an undermount slide or drawer width not specified — rule skipped",
            category=RuleCategory.HARD_CONSTRAINT,
        )
    max_width = 900  # mm — typical undermount limit
    passed = r.drawer_width_mm <= max_width
    return RuleResult(
        rule_id="DS005", rule_name="undermount_width_limit", passed=passed,
        detail=f"Drawer width {r.drawer_width_mm}mm {'<=' if passed else '>'} undermount limit {max_width}mm",
        category=RuleCategory.HARD_CONSTRAINT,
        values_compared={"drawer_width": r.drawer_width_mm, "max": max_width},
        remediation=None if passed else "Drawer too wide for undermount slides. Use side-mount instead.",
    )


def check_disconnect(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS006: Disconnect feature if required."""
    slide, r = _slide(candidates), _req(req)
    if not r.disconnect_required:
        return RuleResult(
            rule_id="DS006", rule_name="disconnect_feature", passed=True,
            detail="Disconnect not required",
            category=RuleCategory.PREFERENCE,
        )
    passed = slide.disconnect_feature
    return RuleResult(
        rule_id="DS006", rule_name="disconnect_feature", passed=passed,
        detail=f"Disconnect feature {'available' if passed else 'not available'}",
        category=RuleCategory.PREFERENCE,
        remediation=None if passed else "This slide does not support tool-free drawer removal",
    )


def check_soft_close(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS007: Soft-close preference."""
    slide, r = _slide(candidates), _req(req)
    if not r.soft_close:
        return RuleResult(
            rule_id="DS007", rule_name="soft_close", passed=True,
            detail="Soft-close not requested",
            category=RuleCategory.PREFERENCE,
        )
    passed = slide.close_type == SlideCloseType.SOFT_CLOSE
    return RuleResult(
        rule_id="DS007", rule_name="soft_close", passed=passed,
        detail=f"Slide close type is {slide.close_type.value} — {'matches' if passed else 'does not match'} soft-close request",
        category=RuleCategory.PREFERENCE,
        remediation=None if passed else "This slide does not have soft-close damping",
    )


def check_push_open(candidates: dict[str, Product], req: Requirements, derived: dict) -> RuleResult:
    """DS008: Push-open preference."""
    slide, r = _slide(candidates), _req(req)
    if not r.push_open:
        return RuleResult(
            rule_id="DS008", rule_name="push_open", passed=True,
            detail="Push-open not requested",
            category=RuleCategory.PREFERENCE,
        )
    passed = slide.close_type == SlideCloseType.PUSH_OPEN
    return RuleResult(
        rule_id="DS008", rule_name="push_open", passed=passed,
        detail=f"Slide close type is {slide.close_type.value} — {'matches' if passed else 'does not match'} push-open request",
        category=RuleCategory.PREFERENCE,
        remediation=None if passed else "This slide does not have push-open (touch-latch)",
    )


RULES = [
    check_load_capacity,      # DS001
    check_cabinet_depth,      # DS002
    check_extension_type,     # DS003
    check_mount_type,         # DS004
    check_undermount_width,   # DS005
    check_disconnect,         # DS006
    check_soft_close,         # DS007
    check_push_open,          # DS008
]
